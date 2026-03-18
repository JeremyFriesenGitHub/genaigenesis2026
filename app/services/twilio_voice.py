import httpx
import logging
import os

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]


def create_outbound_call(to: str, stream_ws_url: str, status_callback_url: str) -> str:
    """Create Twilio outbound call. Returns CallSid."""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{stream_ws_url}" />'
        "</Connect>"
        "</Response>"
    )
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json"
    resp = httpx.post(
        url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        data={
            "From": TWILIO_PHONE_NUMBER,
            "To": to,
            "Twiml": twiml,
            "StatusCallback": status_callback_url,
            "StatusCallbackEvent": "completed",
            "StatusCallbackMethod": "POST",
            "MediaRegion": "ca1",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    call_sid = resp.json()["sid"]
    logger.info("Outbound call to %s, CallSid=%s", to, call_sid)
    return call_sid
