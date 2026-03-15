from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VOICE_NUMBER


def create_outbound_call(to: str, url: str, status_callback: str | None = None) -> str:
    from twilio.rest import Client

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        to=to,
        from_=TWILIO_VOICE_NUMBER,
        url=url,
        status_callback=status_callback,
        status_callback_event=["initiated", "ringing", "answered", "completed"],
    )
    return call.sid
