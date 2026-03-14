import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

GPT_OSS_BASE_URL = os.environ["GPT_OSS_BASE_URL"]
GPT_OSS_MODEL = os.environ["GPT_OSS_MODEL"]
