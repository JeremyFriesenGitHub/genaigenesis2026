import os
from dotenv import load_dotenv

load_dotenv()

# Telnyx credentials
TELNYX_API_KEY = os.environ["TELNYX_API_KEY"]
TELNYX_PHONE_NUMBER = os.environ["TELNYX_PHONE_NUMBER"]
TELNYX_CONNECTION_ID = os.environ["TELNYX_CONNECTION_ID"]
TELNYX_OUTBOUND_PROFILE_ID = os.environ.get("TELNYX_OUTBOUND_PROFILE_ID", "")
TELNYX_MESSAGING_PROFILE_ID = os.environ.get("TELNYX_MESSAGING_PROFILE_ID", "")

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")
WS_BASE_URL = os.environ.get("WS_BASE_URL", "ws://localhost:8000")

VOICE_EVENTS_URL = os.environ.get("VOICE_EVENTS_URL", f"{APP_BASE_URL}/voice/events")
STREAM_WS_URL = os.environ.get("STREAM_WS_URL", f"{WS_BASE_URL}/voice/stream")

# PersonaPlex server
PERSONAPLEX_STREAM_URL = os.environ.get(
    "PERSONAPLEX_STREAM_URL", "ws://localhost:8998/api/chat"
)
PERSONAPLEX_VOICE = os.environ.get("PERSONAPLEX_VOICE", "NATF2.pt")
PERSONAPLEX_TEXT_PROMPT = os.environ.get(
    "PERSONAPLEX_TEXT_PROMPT",
    (
        "Your name is Maya Chen. You are a friendly, knowledgeable real estate agent. "
        "You help callers find their perfect home by asking about their budget, "
        "preferred neighborhoods, must-have features, and timeline. "
        "You're warm, professional, and conversational. "
        "Keep responses concise since this is a phone call."
    ),
)

PREWARM_TTL_SECONDS = int(os.environ.get("PREWARM_TTL_SECONDS", "30"))
