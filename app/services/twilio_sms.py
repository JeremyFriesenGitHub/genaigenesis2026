from twilio.rest import Client
from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_sms(to: str, body: str) -> str:
    """Send an SMS via Twilio. Returns the message SID."""
    message = client.messages.create(
        body=body,
        from_=TWILIO_PHONE_NUMBER,
        to=to,
    )
    return message.sid
