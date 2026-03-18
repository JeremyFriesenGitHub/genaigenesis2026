import os


def pytest_configure():
    # Minimal env for config imports during tests
    os.environ.setdefault("GPT_OSS_BASE_URL", "http://localhost:8000")
    os.environ.setdefault("GPT_OSS_MODEL", "test-model")
    os.environ.setdefault("TELNYX_API_KEY", "test_key")
    os.environ.setdefault("TELNYX_CONNECTION_ID", "test_conn")
    os.environ.setdefault("TELNYX_PHONE_NUMBER", "+15550001111")
    os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")
    os.environ.setdefault("STREAM_WS_URL", "wss://localhost:8000/voice/stream")
    os.environ.setdefault("VOICE_EVENTS_URL", "http://localhost:8000/voice/events")
