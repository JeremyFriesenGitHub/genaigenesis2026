import httpx
import logging

from app.config import (
    TELNYX_API_KEY,
    TELNYX_CONNECTION_ID,
    TELNYX_PHONE_NUMBER,
    STREAM_WS_URL,
    VOICE_EVENTS_URL,
)

logger = logging.getLogger(__name__)

TELNYX_API_URL = "https://api.telnyx.com/v2/calls"


def create_outbound_call(to: str) -> str:
    """Dial an outbound call via Telnyx Call Control with streaming enabled.

    Returns the call_control_id.
    """
    resp = httpx.post(
        TELNYX_API_URL,
        headers={
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "connection_id": TELNYX_CONNECTION_ID,
            "to": to,
            "from": TELNYX_PHONE_NUMBER,
            "stream_url": STREAM_WS_URL,
            "stream_track": "both_tracks",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "L16",
            "webhook_url": VOICE_EVENTS_URL,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    call_control_id = data["call_control_id"]
    logger.info("Telnyx outbound call created: %s", call_control_id)
    return call_control_id
