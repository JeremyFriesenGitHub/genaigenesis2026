from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import sms

app = FastAPI(title="AI Real Estate Agent")

app.include_router(sms.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve static frontend as catch-all (checked after API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
