from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.twilio_sms import send_sms
from app.services.twilio_voice import create_outbound_call
from app.services.dynamodb_sessions import get_session, put_session
from app.services.eventbridge_scheduler import schedule_resume_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sms", tags=["sms"])

# In-memory reverse lookup: call_sid → phone (only lives as long as Lambda instance)
# DynamoDB is source of truth for sessions; this is just for fast voice event lookups
call_sessions: dict[str, str] = {}

GREETING = (
    "Hey! I'm Maya, your AI real estate agent. "
    "Want me to give you a call to learn what you're looking for? Reply YES to confirm."
)

APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
STREAM_WS_URL = os.environ.get("STREAM_WS_URL", "")


@router.post("/webhook")
async def sms_webhook(request: Request):
    """Twilio SMS webhook — form-encoded."""
    form = await request.form()
    phone = form.get("From", "")
    text = (form.get("Body") or "").strip()

    if not phone:
        return JSONResponse({"ok": True})

    if text.upper() == "STOP":
        session = get_session(phone)
        session["state"] = "stopped"
        put_session(phone, session)
        return JSONResponse({"ok": True})  # Twilio handles STOP opt-out natively

    if text.upper() == "RESET":
        put_session(phone, {"state": "new"})
        send_sms(phone, "Session reset. Text anything to start over.")
        return JSONResponse({"ok": True})

    session = get_session(phone)
    state = session.get("state", "new")
    logger.info("SMS from %s (state=%s): %s", phone, state, text)

    if state in ("new", "stopped"):
        session["state"] = "awaiting_confirmation"
        put_session(phone, session)
        send_sms(phone, GREETING)

    elif state == "awaiting_confirmation":
        if text.upper() in ("YES", "Y"):
            session["state"] = "starting_gpu"
            put_session(phone, session)
            send_sms(phone, "Starting up the AI — I'll call you in about 60 seconds! 📞")
            asyncio.create_task(_start_gpu_and_call(phone))
        else:
            send_sms(phone, "No worries! Reply YES whenever you're ready.")

    elif state in ("starting_gpu", "in_call"):
        send_sms(phone, "We're still processing your call — hang tight!")

    elif state == "searching":
        send_sms(phone, "Still searching for the perfect place for you...")

    elif state == "awaiting_property_feedback":
        prop = session.get("current_property") or {}
        text_upper = text.upper().strip()

        if text_upper in ("1", "YES", "Y"):
            if isinstance(prop, dict) and prop.get("url"):
                liked = session.get("liked_properties") or []
                liked.append(prop["url"])
                session["liked_properties"] = liked
            session["page"] = (session.get("page") or 1) + 1
            session["state"] = "cooldown"
            put_session(phone, session)
            send_sms(phone, "Ok great, I'll send the realtor your info! 🏡 I'll find more options in an hour.")
            schedule_resume_search(phone, delay_seconds=3600)

        elif text_upper in ("2", "NO", "N"):
            session["state"] = "awaiting_rejection_reason"
            put_session(phone, session)
            send_sms(phone, "Got it! What didn't you like about it?")

        else:
            send_sms(phone, "Reply 1 if you like it, or 2 to see something else.")

    elif state == "awaiting_rejection_reason":
        reasons = session.get("rejection_reasons") or []
        reasons.append(text)
        session["rejection_reasons"] = reasons
        session["page"] = (session.get("page") or 1) + 1
        session["state"] = "searching"
        put_session(phone, session)
        send_sms(phone, "Thanks for the feedback! Searching for something better...")
        asyncio.create_task(_run_search(phone))

    elif state == "cooldown":
        send_sms(phone, "I'll send your next listing in about an hour! Reply STOP to pause.")

    else:
        session = {"state": "awaiting_confirmation"}
        put_session(phone, session)
        send_sms(phone, GREETING)

    return JSONResponse({"ok": True})


async def _start_gpu_and_call(phone: str) -> None:
    """Start SageMaker notebook, wait until InService, then place Twilio call."""
    from app.services.sagemaker_notebook import start_notebook

    try:
        ip = await asyncio.get_event_loop().run_in_executor(None, start_notebook)
        stream_ws_url = f"wss://{ip}:8001/voice/stream"
        status_callback = f"{APP_BASE_URL}/voice/events"

        call_sid = create_outbound_call(phone, stream_ws_url, status_callback)

        session = get_session(phone)
        session["state"] = "in_call"
        session["call_sid"] = call_sid
        put_session(phone, session)
        call_sessions[call_sid] = phone

    except Exception:
        logger.exception("Failed to start GPU and call %s", phone)
        session = get_session(phone)
        session["state"] = "awaiting_confirmation"
        put_session(phone, session)
        send_sms(phone, "Sorry, I had trouble starting the AI. Reply YES to try again.")


async def _run_search(phone: str) -> None:
    from app.services.search_pipeline import run_search
    await run_search(phone)
