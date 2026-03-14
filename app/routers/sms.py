import logging
from fastapi import APIRouter, Form
from fastapi.responses import Response
from app.config import VAPI_API_KEY
from app.services.vapi_call import trigger_call

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


def twiml_response(message: str) -> Response:
    """Return a TwiML XML response with a message."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{message}</Message>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/webhook")
async def sms_webhook(From: str = Form(...), Body: str = Form("")):
    """Handle incoming SMS from Twilio."""
    phone = From
    body = Body.strip()
    state = conversations.get(phone, "new")

    logger.info(f"SMS from {phone} (state={state}): {body}")

    if state == "new":
        conversations[phone] = "awaiting_confirmation"
        return twiml_response(GREETING)

    if state == "awaiting_confirmation":
        if body.upper() == "YES":
            conversations[phone] = "called"
            if VAPI_API_KEY and not VAPI_API_KEY.startswith("your_"):
                try:
                    result = await trigger_call(phone)
                    logger.info(f"Vapi call initiated: {result}")
                    return twiml_response("Great! Calling you now...")
                except Exception as e:
                    logger.error(f"Failed to trigger Vapi call: {e}")
                    conversations[phone] = "awaiting_confirmation"
                    return twiml_response(
                        "Sorry, I couldn't start the call. Please try replying YES again."
                    )
            else:
                logger.info(f"Vapi not configured — skipping call for {phone}")
                return twiml_response(
                    "Thanks for confirming! We'll be in touch soon."
                )
        else:
            return twiml_response(
                "No worries! Reply YES whenever you're ready for a call."
            )

    if state == "called":
        return twiml_response(
            "We already have your info from our call. "
            "We'll text you with listings soon!"
        )

    # Fallback
    conversations[phone] = "new"
    return twiml_response(GREETING)
