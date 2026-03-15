import os
from dotenv import load_dotenv

load_dotenv()

GPT_OSS_BASE_URL = os.environ.get("GPT_OSS_BASE_URL", "")
GPT_OSS_BASE_URL_FALLBACK = os.environ.get("GPT_OSS_BASE_URL_FALLBACK", "")
GPT_OSS_MODEL = os.environ.get("GPT_OSS_MODEL", "")

# Telnyx
TELNYX_API_KEY = os.environ["TELNYX_API_KEY"]
TELNYX_CONNECTION_ID = os.environ["TELNYX_CONNECTION_ID"]
TELNYX_PHONE_NUMBER = os.environ["TELNYX_PHONE_NUMBER"]
APP_BASE_URL = os.environ["APP_BASE_URL"]           # e.g. https://personaplex.click
STREAM_WS_URL = os.environ["STREAM_WS_URL"]         # e.g. wss://personaplex.click/voice/stream
VOICE_EVENTS_URL = os.environ["VOICE_EVENTS_URL"]   # e.g. https://personaplex.click/voice/events

# PersonaPlex
PERSONAPLEX_STREAM_URL = os.environ.get("PERSONAPLEX_STREAM_URL", "ws://localhost:8998/api/chat")
PERSONAPLEX_VOICE = os.environ.get("PERSONAPLEX_VOICE", "NATF2.pt")
PERSONAPLEX_TEXT_PROMPT = os.environ.get("PERSONAPLEX_TEXT_PROMPT", "")
PERSONAPLEX_SEED = int(os.environ.get("PERSONAPLEX_SEED", "-1"))

# Recordings
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/tmp/recordings")
