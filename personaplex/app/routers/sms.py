import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import TELNYX_PHONE_NUMBER, TELNYX_API_KEY, TELNYX_MESSAGING_PROFILE_ID
from app.services.personaplex_client import PersonaPlexClient
from app.services.telnyx_voice import create_outbound_call
from app.services import prewarm

import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms", tags=["sms"])

# In-memory conversation state keyed by phone number
# States: "new" -> "awaiting_confirmation" -> "called"
conversations: dict[str, str] = {}

GREETING = (
    "Hey! I'd love to help you find a place. "
    "Can I give you a call to learn what you're looking for? "
    "Reply YES to confirm."
)


def send_sms(to: str, text: str) -> None:
    """Send an SMS via Telnyx Messaging API."""
    resp = httpx.post(
        "https://api.telnyx.com/v2/messages",
        headers={
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": TELNYX_PHONE_NUMBER,
            "to": to,
            "text": text,
            "messaging_profile_id": TELNYX_MESSAGING_PROFILE_ID,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    logger.info("SMS sent to %s", to)


async def _start_prewarm(call_control_id: str) -> None:
    """Connect a PersonaPlexClient in the background and store in pool."""
    try:
        client = PersonaPlexClient.from_env()
        prewarm.store(call_control_id, client)
        await asyncio.wait_for(client.connect(), timeout=10.0)
        logger.info("Pre-warm ready for call %s", call_control_id)
    except Exception:
        logger.exception("Pre-warm failed for call %s", call_control_id)
        prewarm.remove(call_control_id)


@router.post("/webhook")
async def sms_webhook(request: Request):
    """Handle incoming SMS from Telnyx."""
    body = await request.json()
    data = body.get("data", {})
    payload = data.get("payload", {})

    event_type = data.get("event_type", "")
    if event_type != "message.received":
        return JSONResponse({"ok": True})

    phone = payload.get("from", {}).get("phone_number", "")
    text = payload.get("text", "").strip()
    state = conversations.get(phone, "new")

    logger.info(f"SMS from {phone} (state={state}): {text}")

    if state == "new":
        conversations[phone] = "awaiting_confirmation"
        send_sms(phone, GREETING)
        return JSONResponse({"ok": True})

    if state == "awaiting_confirmation":
        if text.upper() == "YES":
            conversations[phone] = "called"
            call_control_id = await asyncio.to_thread(create_outbound_call, phone)
            logger.info("Outbound call created: %s", call_control_id)
            asyncio.create_task(_start_prewarm(call_control_id))
            send_sms(
                phone,
                "Great! We'll give you a call shortly to learn more about what you're looking for.",
            )
            return JSONResponse({"ok": True})
        send_sms(phone, "No worries! Reply YES whenever you're ready for a call.")
        return JSONResponse({"ok": True})

    if state == "called":
        send_sms(
            phone,
            "We already have your info from our call. "
            "We'll text you with listings soon!",
        )
        return JSONResponse({"ok": True})

    # Fallback — unknown state, restart
    conversations[phone] = "new"
    send_sms(phone, GREETING)
    return JSONResponse({"ok": True})


@router.post("/reset")
async def reset_conversations():
    """Clear all conversation states so numbers can re-enter the flow."""
    conversations.clear()
    logger.info("All SMS conversation states reset")
    return {"status": "ok", "message": "All conversations reset"}
