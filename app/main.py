import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import sms, voice
from mangum import Mangum

app = FastAPI(title="PersonaPlex Real Estate Agent")
app.include_router(sms.router)
app.include_router(voice.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/events/resume")
async def eventbridge_resume(request: Request):
    """EventBridge Scheduler fires this when a cooldown period ends."""
    body = await request.json()
    if body.get("type") == "resume_search":
        phone = body.get("phone")
        if phone:
            from app.services.dynamodb_sessions import get_session, put_session
            session = get_session(phone)
            if session.get("state") == "cooldown":
                session["state"] = "searching"
                put_session(phone, session)
                from app.services.search_pipeline import run_search
                asyncio.create_task(run_search(phone))
    return JSONResponse({"ok": True})


@app.post("/session/sync")
async def session_sync(request: Request):
    """Called by search pipeline to sync session state (writes to DynamoDB)."""
    body = await request.json()
    phone = body.get("phone")
    if phone:
        from app.services.dynamodb_sessions import get_session, put_session
        session = get_session(phone)
        for k in ("state", "current_property", "criteria", "rejection_reasons", "page"):
            if k in body:
                session[k] = body[k]
        put_session(phone, session)
    return JSONResponse({"ok": True})


# Serve static frontend as catch-all (checked after API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Lambda entry point
handler = Mangum(app, lifespan="off")
