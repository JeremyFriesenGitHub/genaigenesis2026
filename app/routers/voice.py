"""Twilio ↔ PersonaPlex voice bridge.

Twilio streams mulaw at 8 kHz over its Media Stream WebSocket.
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
    StatefulResampler,
    decode_twilio_media,
    encode_twilio_media,
)
from app.config import PERSONAPLEX_STREAM_URL, PERSONAPLEX_VOICE, PERSONAPLEX_TEXT_PROMPT, PERSONAPLEX_SEED

# Import shared state from sms router
from app.routers.sms import call_sessions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

TWILIO_SAMPLE_RATE = 8000
PERSONAPLEX_SAMPLE_RATE = 24000


@router.post("/events")
async def voice_events(request: Request):
    """Handle Twilio call status callback events."""
    form = await request.form()
    call_status = form.get("CallStatus", "")
    call_sid = form.get("CallSid", "")

    logger.info("Twilio voice event: CallStatus=%s CallSid=%s", call_status, call_sid)

    if call_status == "completed":
        phone = call_sessions.get(call_sid)
        if phone:
            asyncio.create_task(_post_call_cleanup(call_sid, phone))

    return JSONResponse({"ok": True})


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """Full-duplex bridge: Twilio media stream ↔ PersonaPlex streaming."""
    await websocket.accept()
    logger.info("Twilio media stream connected")

    upsample = StatefulResampler(TWILIO_SAMPLE_RATE, PERSONAPLEX_SAMPLE_RATE)
    downsample = StatefulResampler(PERSONAPLEX_SAMPLE_RATE, TWILIO_SAMPLE_RATE)

    call_sid: str | None = None
    client = None

    try:
        from app.services.personaplex_client import PersonaPlexClient
        client = PersonaPlexClient(
            server_url=PERSONAPLEX_STREAM_URL,
            voice_prompt=PERSONAPLEX_VOICE,
            text_prompt=PERSONAPLEX_TEXT_PROMPT,
            seed=PERSONAPLEX_SEED,
        )
        await client.connect()

        # Shared recorder reference — set by recv loop once call_sid is known
        recorder_ref: list = [None]

        recv_task = asyncio.create_task(
            _twilio_recv_loop(websocket, client, upsample, recorder_ref)
        )
        send_task = asyncio.create_task(
            _personaplex_send_loop(websocket, client, downsample, recorder_ref)
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
        logger.info("Twilio WebSocket disconnected")
    except Exception:
        logger.exception("Voice stream error")
    finally:
        if client:
            await client.close()
        logger.info("Voice stream session ended (call_sid=%s)", call_sid)


async def _twilio_recv_loop(
    websocket: WebSocket,
    client,
    upsample: StatefulResampler,
    recorder_ref: list,
) -> None:
    """Receive audio from Twilio, upsample, and forward to PersonaPlex."""
    call_sid: str | None = None
    recorder = None
    chunks = 0

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            event = message.get("event", "")

            if event == "connected":
                logger.info("Twilio stream connected event")
                continue

            if event == "start":
                meta = message.get("start", {})
                call_sid = meta.get("callSid") or meta.get("call_sid")
                logger.info("Twilio stream started, call_sid=%s", call_sid)
                if call_sid:
                    from app.services.recorder import CallRecorder
                    recorder = CallRecorder(call_id=call_sid, sample_rate=TWILIO_SAMPLE_RATE)
                    recorder_ref[0] = recorder
                continue

            if event == "stop":
                logger.info("Twilio stream stop event")
                if recorder:
                    recorder.save_and_transcribe()
                break

            if event == "media":
                payload_b64 = message.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                # decode_twilio_media: base64 decode + mulaw → PCM16
                pcm_8k = decode_twilio_media(payload_b64)
                chunks += 1

                if recorder:
                    recorder.record_user(pcm_8k)

                # Upsample 8 kHz → 24 kHz
                pcm_24k = upsample.resample(pcm_8k)
                client.send_pcm(pcm_24k)

    except WebSocketDisconnect:
        logger.info("Twilio recv: WebSocket disconnected after %d chunks", chunks)
        if recorder:
            recorder.save_and_transcribe()
    except Exception:
        logger.exception("Twilio recv error")


async def _personaplex_send_loop(
    websocket: WebSocket,
    client,
    downsample: StatefulResampler,
    recorder_ref: list,
) -> None:
    """Receive audio from PersonaPlex, downsample, and send to Twilio."""
    sends = 0
    try:
        while not client.is_closed:
            pcm_24k = await client.recv_audio(timeout=0.05)
            if pcm_24k is None:
                continue

            # Downsample 24 kHz → 8 kHz for Twilio
            pcm_8k = downsample.resample(pcm_24k)

            # Record agent side
            if recorder_ref[0]:
                recorder_ref[0].record_agent(pcm_8k)

            # encode_twilio_media: PCM16 → mulaw + base64 encode
            payload_b64 = encode_twilio_media(pcm_8k)

            await websocket.send_json({
                "event": "media",
                "media": {"payload": payload_b64},
            })
            sends += 1

    except WebSocketDisconnect:
        logger.info("PersonaPlex send: WebSocket disconnected after %d sends", sends)
    except Exception:
        logger.exception("PersonaPlex send error")


async def _post_call_cleanup(call_sid: str, phone: str) -> None:
    """After hangup: poll for S3 transcript, run search, stop GPU."""
    import os
    import boto3
    from app.services.dynamodb_sessions import get_session, put_session
    from app.services.sagemaker_notebook import stop_notebook as stop_gpu

    bucket = os.environ.get("S3_BUCKET", "personaplex-recordings")
    s3 = boto3.client("s3")
    transcript_key = f"transcripts/{call_sid}.txt"

    # Poll S3 up to 60s for transcript
    for _ in range(120):
        try:
            obj = s3.get_object(Bucket=bucket, Key=transcript_key)
            transcript = obj["Body"].read().decode()
            break
        except s3.exceptions.NoSuchKey:
            await asyncio.sleep(0.5)
    else:
        logger.warning("Transcript not found in S3 for %s after 60s", call_sid)
        await asyncio.get_event_loop().run_in_executor(None, stop_gpu)
        return

    session = get_session(phone)
    session["state"] = "searching"
    put_session(phone, session)

    from app.services.search_pipeline import run_search
    await run_search(phone, transcript=transcript)

    # Stop GPU after search pipeline sends the first listing
    await asyncio.get_event_loop().run_in_executor(None, stop_gpu)
