"""Telnyx ↔ PersonaPlex voice bridge.

Telnyx streams L16 (raw PCM16) at 16 kHz over its Media Stream WebSocket.
PersonaPlex streams Opus 24 kHz over its own WebSocket.
This router bridges the two with concurrent send/recv tasks.
"""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.audio_utils import (
    StatefulResampler,
    StreamingDenoiser,
    decode_telnyx_media,
    encode_telnyx_media,
)
from app.services.personaplex_client import PersonaPlexClient
from app.services.recorder import CallRecorder
from app.services import prewarm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/events")
async def voice_events(request: Request):
    """Handle Telnyx Call Control webhook events."""
    body = await request.json()
    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id", "")
    logger.info("Telnyx voice event: %s call=%s", event_type, call_control_id)
    return JSONResponse({"ok": True})


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """Full-duplex bridge: Telnyx media stream ↔ PersonaPlex streaming."""
    print("=== WEBSOCKET HANDLER STARTED ===", flush=True)
    try:
        logger.info("=== WebSocket connection attempt ===")
        await websocket.accept()
        logger.info("=== WebSocket accepted ===")
    except Exception as e:
        print(f"ERROR accepting WebSocket: {e}", flush=True)
        logger.exception("Failed to accept WebSocket")
        return

    stream_id: str | None = None
    call_control_id: str | None = None
    personaplex: PersonaPlexClient | None = None
    recorder: CallRecorder | None = None
    media_chunks_received = 0
    # Telnyx L16 is 8 kHz (standard telephony), PersonaPlex needs 24 kHz
    upsample = StatefulResampler(in_rate=8000, out_rate=24000)
    downsample = StatefulResampler(in_rate=24000, out_rate=8000)
    denoiser = StreamingDenoiser(sample_rate=24000)

    # Latency tracking
    last_user_audio_ts = 0.0
    first_response_logged = False

    async def telnyx_to_personaplex():
        """Read Telnyx media events, convert audio, feed to PersonaPlex."""
        nonlocal stream_id, call_control_id, media_chunks_received, last_user_audio_ts
        try:
            while True:
                raw = await websocket.receive_text()
                t_recv = time.perf_counter()
                event = json.loads(raw)
                etype = event.get("event")

                if etype == "connected":
                    logger.info("Telnyx stream connected")
                    continue

                if etype == "start":
                    start_data = event.get("start", {})
                    stream_id = event.get("stream_id")
                    call_control_id = start_data.get("call_control_id")
                    logger.info(
                        "Telnyx stream started: stream=%s call=%s",
                        stream_id, call_control_id,
                    )
                    continue

                if etype == "media" and stream_id and personaplex:
                    payload = event.get("media", {}).get("payload")
                    if not payload:
                        continue

                    t0 = time.perf_counter()
                    # L16 is already raw PCM16 — just decode base64
                    pcm_16k = decode_telnyx_media(payload)
                    pcm_24k = upsample.resample(pcm_16k)
                    pcm_24k = denoiser.process(pcm_24k)
                    if recorder:
                        recorder.record_user(pcm_24k)
                    personaplex.send_pcm(pcm_24k)
                    t1 = time.perf_counter()

                    last_user_audio_ts = t_recv
                    media_chunks_received += 1

                    if media_chunks_received % 250 == 1:
                        logger.info(
                            f"[LATENCY] Telnyx→PersonaPlex processing: {(t1-t0)*1000:.2f}ms | "
                            f"chunk #{media_chunks_received} ({len(pcm_24k)} bytes)"
                        )
                    continue

                if etype == "stop":
                    logger.info("Telnyx stream stopped")
                    break
        except WebSocketDisconnect:
            logger.info("Telnyx websocket disconnected")

    async def personaplex_to_telnyx():
        """Read PersonaPlex audio, convert, push to Telnyx media stream."""
        nonlocal first_response_logged
        audio_chunks_sent = 0
        try:
            while personaplex and not personaplex.is_closed:
                t0 = time.perf_counter()
                pcm_24k = await personaplex.recv_audio(timeout=0.05)
                if pcm_24k is None or not stream_id:
                    continue
                t_got_audio = time.perf_counter()

                if recorder:
                    recorder.record_agent(pcm_24k)
                # Downsample 24k → 16k, encode as L16 (raw PCM16, already in correct format)
                pcm_16k = downsample.resample(pcm_24k)
                payload = encode_telnyx_media(pcm_16k)
                t_converted = time.perf_counter()

                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "media",
                            "media": {"payload": payload},
                        }
                    )
                )
                t_sent = time.perf_counter()

                audio_chunks_sent += 1

                if last_user_audio_ts > 0 and not first_response_logged:
                    rt = (t_got_audio - last_user_audio_ts) * 1000
                    logger.info(
                        f"[LATENCY] *** First model response: {rt:.0f}ms after last user audio ***"
                    )
                    first_response_logged = True

                if audio_chunks_sent % 250 == 1:
                    logger.info(
                        f"[LATENCY] PersonaPlex→Telnyx: "
                        f"queue_wait={(t_got_audio-t0)*1000:.2f}ms | "
                        f"convert={(t_converted-t_got_audio)*1000:.2f}ms | "
                        f"ws_send={(t_sent-t_converted)*1000:.2f}ms | "
                        f"total={(t_sent-t0)*1000:.2f}ms | "
                        f"chunk #{audio_chunks_sent}"
                    )
        except WebSocketDisconnect:
            logger.info(f"Telnyx WebSocket disconnected after sending {audio_chunks_sent} chunks")
        except Exception:
            logger.exception(f"Error sending audio to Telnyx after {audio_chunks_sent} chunks")

    try:
        t_start = time.perf_counter()

        # Wait for Telnyx start event to get call_control_id
        while call_control_id is None:
            raw = await websocket.receive_text()
            event = json.loads(raw)
            if event.get("event") == "start":
                start_data = event.get("start", {})
                stream_id = event.get("stream_id")
                call_control_id = start_data.get("call_control_id")
                logger.info(
                    "Telnyx stream started: stream=%s call=%s",
                    stream_id, call_control_id,
                )

        # Start recording
        recorder = CallRecorder(call_control_id)

        # Try pre-warmed client first, fall back to fresh connection
        personaplex = await prewarm.retrieve(call_control_id, timeout=10.0)
        if personaplex:
            t_connected = time.perf_counter()
            logger.info(f"[LATENCY] Using pre-warmed PersonaPlex: {(t_connected-t_start)*1000:.0f}ms")
        else:
            logger.info("[LATENCY] No pre-warm, creating fresh PersonaPlex connection...")
            personaplex = PersonaPlexClient.from_env()
            await asyncio.wait_for(personaplex.connect(), timeout=10.0)
            t_connected = time.perf_counter()
            logger.info(f"[LATENCY] Fresh PersonaPlex connection: {(t_connected-t_start)*1000:.0f}ms")

        # Run both directions concurrently; stop when either finishes
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(telnyx_to_personaplex()),
                asyncio.create_task(personaplex_to_telnyx()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except Exception:
        logger.exception("Voice stream error")
    finally:
        if recorder:
            recorder.save_and_transcribe()
        if personaplex:
            await personaplex.close()
