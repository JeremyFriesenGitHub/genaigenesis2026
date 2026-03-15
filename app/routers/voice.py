"""Telnyx ↔ PersonaPlex voice bridge.

Telnyx streams L16 (raw PCM16) at 8 kHz over its Media Stream WebSocket.
PersonaPlex streams Opus 24 kHz over its own WebSocket.
This router bridges the two with concurrent send/recv tasks and a StatefulResampler.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.audio_utils import (
    EchoCanceller,
    StatefulResampler,
    StreamingDenoiser,
    decode_telnyx_media,
    encode_telnyx_media,
)
from app.config import PERSONAPLEX_STREAM_URL, PERSONAPLEX_VOICE, PERSONAPLEX_TEXT_PROMPT, PERSONAPLEX_SEED
from app.services import prewarm

# Import shared state from sms router
from app.routers.sms import call_sessions, sessions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

TELNYX_SAMPLE_RATE = 8000
PERSONAPLEX_SAMPLE_RATE = 24000


def make_stream_twiml(ws_url: str) -> str:
    """Generate TwiML XML to start a media stream to the given WebSocket URL."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{ws_url}" />'
        "</Connect>"
        "</Response>"
    )


@router.post("/events")
async def voice_events(request: Request):
    """Handle Telnyx Call Control webhook events."""
    body = await request.json()
    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id", "")

    logger.info("Telnyx voice event: %s call=%s", event_type, call_control_id)

    if event_type == "call.hangup":
        start_time = payload.get("start_time", "")
        end_time = payload.get("end_time", "")
        duration = _calc_duration(start_time, end_time)
        phone = call_sessions.get(call_control_id)
        logger.info("Call %s ended. Duration: %ss, phone: %s", call_control_id, duration, phone)

        if phone and duration and duration > 20:
            asyncio.create_task(_post_call_search(call_control_id, phone))

    return JSONResponse({"ok": True})


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """Full-duplex bridge: Telnyx media stream ↔ PersonaPlex streaming."""
    await websocket.accept()
    logger.info("Telnyx media stream connected")

    upsample = StatefulResampler(TELNYX_SAMPLE_RATE, PERSONAPLEX_SAMPLE_RATE)
    downsample = StatefulResampler(PERSONAPLEX_SAMPLE_RATE, TELNYX_SAMPLE_RATE)
    echo_canceller = EchoCanceller(sample_rate=TELNYX_SAMPLE_RATE, use_rnnoise=True)

    call_control_id: str | None = None
    client = None

    try:
        # Lazy import to avoid sphn dependency at module load time
        from app.services.personaplex_client import PersonaPlexClient
        # Try to get a pre-warmed client; fall back to fresh connect
        client = PersonaPlexClient(
            server_url=PERSONAPLEX_STREAM_URL,
            voice_prompt=PERSONAPLEX_VOICE,
            text_prompt=PERSONAPLEX_TEXT_PROMPT,
            seed=PERSONAPLEX_SEED,
        )
        await client.connect()

        # Shared recorder reference — set by recv loop once call_control_id is known
        recorder_ref: list = [None]

        recv_task = asyncio.create_task(
            _telnyx_recv_loop(websocket, client, upsample, echo_canceller, recorder_ref)
        )
        send_task = asyncio.create_task(
            _personaplex_send_loop(websocket, client, downsample, echo_canceller, recorder_ref)
        )

        done, pending = await asyncio.wait(
            [recv_task, send_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        for task in done:
            if not task.cancelled() and task.exception():
                logger.error("Voice task exception: %s", task.exception())

    except WebSocketDisconnect:
        logger.info("Telnyx WebSocket disconnected")
    except Exception:
        logger.exception("Voice stream error")
    finally:
        if client:
            await client.close()
        logger.info("Voice stream session ended (call_control_id=%s)", call_control_id)


async def _telnyx_recv_loop(
    websocket: WebSocket,
    client,
    upsample: StatefulResampler,
    echo_canceller: EchoCanceller,
    recorder_ref: list,
) -> None:
    """Receive audio from Telnyx, AEC + denoise, upsample, and forward to PersonaPlex."""
    call_control_id: str | None = None
    recorder = None
    chunks = 0

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            event = message.get("event", "")

            if event == "connected":
                logger.info("Telnyx stream connected event")
                continue

            if event == "start":
                meta = message.get("start", {})
                call_control_id = meta.get("callControlId") or meta.get("call_control_id")
                logger.info("Telnyx stream started, call_control_id=%s", call_control_id)
                if call_control_id:
                    from app.services.recorder import CallRecorder
                    recorder = CallRecorder(call_id=call_control_id, sample_rate=TELNYX_SAMPLE_RATE)
                    recorder_ref[0] = recorder
                continue

            if event == "stop":
                logger.info("Telnyx stream stop event")
                if recorder:
                    recorder.save_and_transcribe()
                break

            if event == "media":
                payload_b64 = message.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                pcm_8k = decode_telnyx_media(payload_b64)
                chunks += 1

                if recorder:
                    recorder.record_user(pcm_8k)

                # AEC + RNNoise at 8 kHz (removes echo and background noise)
                pcm_8k = echo_canceller.process(pcm_8k)

                # Upsample 8 kHz → 24 kHz
                pcm_24k = upsample.resample(pcm_8k)
                client.send_pcm(pcm_24k)

    except WebSocketDisconnect:
        logger.info("Telnyx recv: WebSocket disconnected after %d chunks", chunks)
        if recorder:
            recorder.save_and_transcribe()
    except Exception:
        logger.exception("Telnyx recv error")


async def _personaplex_send_loop(
    websocket: WebSocket,
    client,
    downsample: StatefulResampler,
    echo_canceller: EchoCanceller,
    recorder_ref: list,
) -> None:
    """Receive audio from PersonaPlex, downsample, feed AEC reference, and send to Telnyx."""
    sends = 0
    try:
        while not client.is_closed:
            pcm_24k = await client.recv_audio(timeout=0.05)
            if pcm_24k is None:
                continue

            # Downsample 24 kHz → 8 kHz for Telnyx
            pcm_8k = downsample.resample(pcm_24k)

            # Feed agent audio as AEC reference (what the caller's speaker plays)
            echo_canceller.feed_reference(pcm_8k)

            # Record agent side
            if recorder_ref[0]:
                recorder_ref[0].record_agent(pcm_8k)

            payload_b64 = encode_telnyx_media(pcm_8k)

            await websocket.send_json({
                "event": "media",
                "media": {"payload": payload_b64},
            })
            sends += 1

    except WebSocketDisconnect:
        logger.info("PersonaPlex send: WebSocket disconnected after %d sends", sends)
    except Exception:
        logger.exception("PersonaPlex send error")


async def _post_call_search(call_control_id: str, phone: str) -> None:
    """Wait for transcript file, then fire pipeline webhook or run locally."""
    import os
    from pathlib import Path
    from app.config import RECORDINGS_DIR

    transcript_path = Path(RECORDINGS_DIR) / f"{call_control_id}.txt"
    # Poll up to 60s for transcript (faster-whisper takes a few seconds)
    for _ in range(120):
        if transcript_path.exists():
            break
        await asyncio.sleep(0.5)
    else:
        logger.warning("Transcript not found for call %s after 60s", call_control_id)
        return

    transcript = transcript_path.read_text().strip()
    if not transcript:
        logger.warning("Empty transcript for call %s — skipping pipeline", call_control_id)
        return

    sessions[phone]["state"] = "searching"

    pipeline_url = os.environ.get("PIPELINE_WEBHOOK_URL", "")
    if pipeline_url:
        import httpx
        try:
            resp = httpx.post(
                pipeline_url,
                json={"phone": phone, "transcript": transcript},
                timeout=15.0,
            )
            resp.raise_for_status()
            logger.info("Transcript POSTed to pipeline webhook for %s", phone)
        except Exception:
            logger.exception("Failed to POST transcript to pipeline webhook for %s", phone)
    else:
        from app.services.search_pipeline import run_search
        await run_search(phone, transcript=transcript)


def _calc_duration(start_time: str, end_time: str) -> float | None:
    """Parse ISO 8601 timestamps and return duration in seconds."""
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        t0 = datetime.strptime(start_time, fmt).replace(tzinfo=timezone.utc)
        t1 = datetime.strptime(end_time, fmt).replace(tzinfo=timezone.utc)
        return (t1 - t0).total_seconds()
    except Exception:
        return None
