from fastapi import FastAPI
from app.routers import sms, vapi

app = FastAPI(title="AI Real Estate Agent")

app.include_router(sms.router)
app.include_router(vapi.router)


@app.get("/")
async def health():
    return {"status": "ok"}
