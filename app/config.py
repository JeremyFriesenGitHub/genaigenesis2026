import os
from dotenv import load_dotenv

load_dotenv()

# LLM
GPT_OSS_BASE_URL = os.environ.get("GPT_OSS_BASE_URL", "https://api.openai.com/v1")
GPT_OSS_BASE_URL_FALLBACK = os.environ.get("GPT_OSS_BASE_URL_FALLBACK", "")
GPT_OSS_MODEL = os.environ.get("GPT_OSS_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Twilio
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

# AWS
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "personaplex-sessions")
S3_BUCKET = os.environ.get("S3_BUCKET", "personaplex-recordings")
SAGEMAKER_NOTEBOOK_NAME = os.environ.get("SAGEMAKER_NOTEBOOK_NAME", "personaplex-gpu")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
LAMBDA_FUNCTION_ARN = os.environ.get("LAMBDA_FUNCTION_ARN", "")
LAMBDA_ROLE_ARN = os.environ.get("LAMBDA_ROLE_ARN", "")

# PersonaPlex (on GPU EC2)
PERSONAPLEX_STREAM_URL = os.environ.get("PERSONAPLEX_STREAM_URL", "ws://localhost:8998/api/chat")
PERSONAPLEX_VOICE = os.environ.get("PERSONAPLEX_VOICE", "NATF2.pt")
PERSONAPLEX_TEXT_PROMPT = os.environ.get("PERSONAPLEX_TEXT_PROMPT", "")
PERSONAPLEX_SEED = int(os.environ.get("PERSONAPLEX_SEED", "-1"))
