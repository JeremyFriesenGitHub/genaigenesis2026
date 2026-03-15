import os
import httpx
import logging
from app.config import TELNYX_API_KEY, TELNYX_PHONE_NUMBER

logger = logging.getLogger(__name__)
TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"
_MESSAGING_PROFILE_ID = os.environ.get("TELNYX_MESSAGING_PROFILE_ID", "")


def send_sms(to: str, body: str) -> None:
    payload = {"from": TELNYX_PHONE_NUMBER, "to": to, "text": body}
    if _MESSAGING_PROFILE_ID:
        payload["messaging_profile_id"] = _MESSAGING_PROFILE_ID
    resp = httpx.post(
        TELNYX_MESSAGES_URL,
        headers={"Authorization": f"Bearer {TELNYX_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=10.0,
    )
    resp.raise_for_status()
    logger.info("SMS sent to %s", to)
