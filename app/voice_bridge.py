"""Minimal FastAPI app for the GPU EC2 voice bridge.

Runs only the voice WebSocket router — all other endpoints are handled by Lambda.
Start with: uvicorn app.voice_bridge:app --host 0.0.0.0 --port 8001
"""

from fastapi import FastAPI
from app.routers.voice import router

app = FastAPI()
app.include_router(router)
