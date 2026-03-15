import os


def pytest_configure():
    # Minimal env for config imports during tests
    os.environ.setdefault("TWILIO_ACCOUNT_SID", "test_sid")
    os.environ.setdefault("TWILIO_AUTH_TOKEN", "test_token")
    os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15550001111")
    os.environ.setdefault("TWILIO_VOICE_NUMBER", "+15550002222")
    os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")
    os.environ.setdefault("WS_BASE_URL", "ws://localhost:8000")
