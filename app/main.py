import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import sms, voice
from app.services import prewarm


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cleanup loop for expired pre-warmed connections
    async def _cleanup():
        while True:
            await asyncio.sleep(5)
            await prewarm.cleanup_expired()

    task = asyncio.create_task(_cleanup())
    yield
    task.cancel()
    await prewarm.close_all()


app = FastAPI(title="AI Real Estate Agent", lifespan=lifespan)
app.include_router(sms.router)
app.include_router(voice.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/pipeline/inbound")
async def pipeline_inbound(request: Request):
    """Receive transcript from EC2 and run the search pipeline locally."""
    body = await request.json()
    phone = body.get("phone", "")
    transcript = body.get("transcript", "")
    if not phone or not transcript:
        return JSONResponse({"error": "missing phone or transcript"}, status_code=400)

    # Ensure session exists (call may have come in on EC2 but session is new here)
    session = sms.sessions.setdefault(phone, sms._new_session())
    session["state"] = "searching"

    asyncio.create_task(_run_pipeline(phone, transcript))
    return JSONResponse({"ok": True})


async def _run_pipeline(phone: str, transcript: str):
    from app.services.search_pipeline import run_search
    await run_search(phone, transcript=transcript)


@app.post("/sms/forward")
async def sms_forward(request: Request):
    """Receive forwarded SMS from EC2 for rejection re-search."""
    body = await request.json()
    phone = body.get("phone", "")
    text = body.get("text", "")
    ec2_session = body.get("session", {})
    if not phone:
        return JSONResponse({"error": "missing phone"}, status_code=400)

    session = sms.sessions.setdefault(phone, sms._new_session())
    # Sync rejection reasons and page from EC2
    if ec2_session.get("rejection_reasons"):
        session["rejection_reasons"] = ec2_session["rejection_reasons"]
    if ec2_session.get("page"):
        session["page"] = ec2_session["page"]
    session["state"] = "searching"

    asyncio.create_task(_run_pipeline_no_transcript(phone))
    return JSONResponse({"ok": True})


async def _run_pipeline_no_transcript(phone: str):
    """Re-run search with existing criteria (rejection re-search)."""
    from app.services.search_pipeline import run_search
    await run_search(phone)


@app.post("/contact/run")
async def contact_run(request: Request):
    """Run Zillow contact-agent form fill for a liked property."""
    body = await request.json()
    phone = body.get("phone", "")
    listing_url = body.get("listing_url", "")
    if not phone or not listing_url:
        return JSONResponse({"error": "missing phone or listing_url"}, status_code=400)

    asyncio.create_task(_run_contact(phone, listing_url))
    return JSONResponse({"ok": True})


async def _run_contact(phone: str, listing_url: str):
    """Run contact flow in a thread (playwright is sync) and SMS the result."""
    from app.contact.contact_agent import Lead, run_contact_flow
    from app.services.telnyx_sms import send_sms
    import logging
    logger = logging.getLogger(__name__)

    lead = Lead(
        name="Mary Chen",
        email="mary@agentsquared.ai",
        phone=phone,
        message="Hi, I'm interested in this property. When can I schedule a viewing?",
    )

    try:
        result = await asyncio.to_thread(
            run_contact_flow, listing_url, lead, mode="preview", headless=False, slow_mo_ms=150, use_proxy=False
        )
        if result.submitted:
            send_sms(phone, "I've submitted an inquiry to the listing agent on your behalf! They should reach out to you soon. 🎉")
            logger.info("Contact form submitted for %s at %s", phone, listing_url)
        elif result.form_found:
            send_sms(phone, "I found the contact form but couldn't submit it. Here's the listing so you can reach out directly: " + listing_url)
            logger.warning("Contact form found but not submitted for %s: %s", phone, result.error)
        else:
            send_sms(phone, "I couldn't find a contact form on this listing. You can reach out to the agent directly here: " + listing_url)
            logger.warning("No contact form found for %s at %s", phone, listing_url)
    except Exception:
        logger.exception("Contact flow failed for %s", phone)
        send_sms(phone, "I had trouble contacting the agent. You can reach out directly here: " + listing_url)


# Serve static frontend as catch-all (checked after API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
