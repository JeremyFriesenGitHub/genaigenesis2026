from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.telnyx_sms import send_sms
from app.services.telnyx_voice import create_outbound_call

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sms", tags=["sms"])

# Shared mutable state (imported by voice.py too)
sessions: dict[str, dict] = {}
call_sessions: dict[str, str] = {}  # call_control_id → phone


def _new_session() -> dict:
    return {
        "state": "new",
        "call_control_id": None,
        "criteria": None,
        "rejection_reasons": [],
        "page": 1,
        "liked_properties": [],
        "current_property": None,
        "cooldown_until": None,
        "seen_urls": [],
    }


GREETING = (
    "Hey! I'm Mary, your real estate agent. Want me to give you a call "
    "to learn what you're looking for? Reply YES to confirm."
)


@router.post("/webhook")
async def sms_webhook(request: Request):
    body = await request.json()
    payload = body.get("data", {}).get("payload", {})
    phone = payload.get("from", {}).get("phone_number", "")
    text = payload.get("text", "").strip()

    if not phone:
        return JSONResponse({"ok": True})

    # Magic reset keyword — clears session from any state
    if text.strip().upper() == "RESET":
        sessions[phone] = _new_session()
        send_sms(phone, "Session reset! " + GREETING)
        return JSONResponse({"ok": True})

    session = sessions.setdefault(phone, _new_session())
    state = session["state"]
    logger.info("SMS from %s (state=%s): %s", phone, state, text)

    if state == "new":
        session["state"] = "awaiting_confirmation"
        send_sms(phone, GREETING)

    elif state == "awaiting_confirmation":
        if text.strip().upper() in ("YES", "Y", "YEAH", "YEP", "SURE"):
            session["state"] = "in_call"
            call_control_id = create_outbound_call(phone)
            session["call_control_id"] = call_control_id
            call_sessions[call_control_id] = phone
            send_sms(phone, "Calling you now! 📞")
        else:
            send_sms(phone, "No worries! Reply YES whenever you're ready.")

    elif state == "in_call":
        send_sms(phone, "We're still processing your call — hang tight!")

    elif state == "searching":
        send_sms(phone, "Still searching for the perfect place for you...")

    elif state == "awaiting_property_feedback":
        prop = session.get("current_property")
        answer = text.strip().upper()
        if answer in ("YES", "Y", "YEAH", "YEP", "SURE"):
            if prop:
                session["liked_properties"].append(prop.get("url", ""))
            session["page"] += 1
            session["state"] = "cooldown"
            session["cooldown_until"] = time.time() + 3600  # 1 hour
            send_sms(phone, "Ok great, I'll contact the realtor! 🏡")
            asyncio.create_task(_delayed_search(phone, delay=3600))
        elif answer in ("NO", "N", "NOPE", "NAH"):
            session["state"] = "awaiting_rejection_reason"
            send_sms(phone, "Got it! What didn't you like about it?")
        else:
            session["state"] = "awaiting_rejection_reason"
            send_sms(phone, "Got it! What didn't you like about it?")

    elif state == "awaiting_rejection_reason":
        session["rejection_reasons"].append(text)
        session["page"] += 1
        session["state"] = "searching"
        send_sms(phone, "Thanks for the feedback! Searching for something better...")
        asyncio.create_task(_run_search(phone))

    else:
        # Unknown state — reset
        sessions[phone] = _new_session()
        sessions[phone]["state"] = "awaiting_confirmation"
        send_sms(phone, GREETING)

    return JSONResponse({"ok": True})


async def _run_search(phone: str):
    """Thin async wrapper — import here to avoid circular imports."""
    from app.services.search_pipeline import run_search
    await run_search(phone)


async def _delayed_search(phone: str, delay: float):
    """Wait `delay` seconds (1hr cooldown), then resume search."""
    await asyncio.sleep(delay)
    session = sessions.get(phone)
    if session and session.get("state") == "cooldown":
        session["state"] = "searching"
        from app.services.search_pipeline import run_search
        await run_search(phone)
