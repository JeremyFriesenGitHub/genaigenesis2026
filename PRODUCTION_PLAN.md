# PersonaPlex Production Plan

## Architecture Overview

```
User (Ontario) → Twilio CA media region → SageMaker g5.xlarge (ca-central-1)
                                               ├── Voice bridge (port 8001, WSS)
                                               └── Moshi model server (port 8998, WSS)
Twilio SMS/events → Railway (FastAPI) → DynamoDB (ca-central-1)
                                      → S3 (ca-central-1)
                                      → EventBridge Scheduler
                                      → SageMaker start/stop
```

---

## ✅ Already Done

### Infrastructure
- [x] AWS account created, IAM user `claude` with admin access
- [x] DynamoDB table `personaplex-sessions` (us-east-1, TTL enabled) — *to migrate to ca-central-1*
- [x] S3 bucket `personaplex-recordings` (us-east-1, 30-day lifecycle) — *to migrate to ca-central-1*
- [x] EventBridge Scheduler group `personaplex-cooldowns`
- [x] IAM role `personaplex-lambda-role` with all required permissions
- [x] SageMaker notebook quota approved: `ml.g5.xlarge` in `ca-central-1`

### Code Migration (Telnyx → Twilio, EB → Lambda/Railway)
- [x] `app/services/twilio_sms.py` — Twilio SMS via REST
- [x] `app/services/twilio_voice.py` — outbound call with TwiML `<Stream>`
- [x] `app/services/dynamodb_sessions.py` — DynamoDB session store
- [x] `app/services/ec2_gpu.py` — GPU start/stop (will update for SageMaker)
- [x] `app/services/eventbridge_scheduler.py` — 1-hour cooldown schedules
- [x] `app/routers/sms.py` — Twilio form-encoded webhooks, DynamoDB, STOP keyword
- [x] `app/routers/voice.py` — mulaw codec, CallSid, S3 transcript polling
- [x] `app/services/recorder.py` — WAV + transcript upload to S3
- [x] `app/config.py` — Twilio + AWS vars
- [x] `app/voice_bridge.py` — minimal FastAPI app (voice WebSocket only)
- [x] `handler.py` — Mangum Lambda entry point
- [x] Deleted: `telnyx_sms.py`, `telnyx_voice.py`, `app/contact/`

### Model
- [x] `brianmatzelle/personaplex-7b-v1-bnb-4bit` identified (Moshi-based, 4-bit NF4)
- [x] Model weights downloaded (`model_bnb_4bit.pt`, 6.6GB)
- [x] Moshi package installed, protocol confirmed identical to existing `personaplex_client.py`
- [x] `personaplex-model.service` systemd unit written
- [x] `voice-bridge.service` systemd unit written

### Twilio
- [x] Account verified (full, not trial)
- [x] Phone number `+18259067207` purchased
- [x] SMS webhook: `https://s9owkdib8c.execute-api.us-east-1.amazonaws.com/sms/webhook`
- [x] Voice status callback: `https://s9owkdib8c.execute-api.us-east-1.amazonaws.com/voice/events`

---

## 🔧 Before Test Link

### 1. Migrate AWS Resources to ca-central-1
- [ ] Create DynamoDB table `personaplex-sessions` in `ca-central-1`
- [ ] Create S3 bucket `personaplex-recordings-ca` in `ca-central-1`
- [ ] Update EventBridge Scheduler group in `ca-central-1`
- [ ] Update IAM role permissions for new region resources

### 2. Launch SageMaker Notebook (ca-central-1)
- [ ] Create SageMaker notebook instance `personaplex-gpu` (`ml.g5.xlarge`, ca-central-1)
- [ ] On-start lifecycle config:
  - Clone `brianmatzelle/personaplex-7b-v1-bnb-4bit`
  - Install moshi package + bitsandbytes
  - Copy model weights
  - Start voice bridge (port 8001, WSS)
  - Start Moshi model server (port 8998, WSS, `--quantize-4bit`)
- [ ] Open ports 8001 + 8998 in SageMaker security group
- [ ] Get notebook public IP/DNS

### 3. Deploy Backend to Railway
- [ ] Create `Procfile`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Remove Mangum from `app/main.py` (Railway runs uvicorn directly)
- [ ] Push to Railway from GitHub repo
- [ ] Set all environment variables on Railway:
  - Twilio credentials
  - AWS credentials (ca-central-1 resources)
  - SageMaker notebook IP for `STREAM_WS_URL` + `PERSONAPLEX_STREAM_URL`
- [ ] Get Railway public URL

### 4. Replace ec2_gpu.py with SageMaker Notebook Start/Stop
- [ ] Update `app/services/ec2_gpu.py` → `app/services/sagemaker_notebook.py`
  - `start_notebook()` — call `create_presigned_notebook_instance_url` or `start_notebook_instance`
  - `stop_notebook()` — call `stop_notebook_instance`
  - Poll until `InService` state, return public IP
- [ ] Update `app/routers/sms.py` to import from `sagemaker_notebook.py`
- [ ] Update `app/routers/voice.py` post-call cleanup to stop notebook

### 5. Update Twilio Webhooks
- [ ] Update SMS webhook → Railway URL `/sms/webhook`
- [ ] Update voice status callback → Railway URL `/voice/events`
- [ ] **Pin Twilio media region to `ca1`** (Montreal) in outbound call TwiML:
  ```python
  # In twilio_voice.py, add to Calls.json POST:
  "MediaRegion": "ca1"
  ```

### 6. Smoke Test
- [ ] Text `+18259067207` → receive Maya greeting
- [ ] Reply YES → notebook starts, call arrives ~60s later
- [ ] Converse with Maya → hang up
- [ ] Check S3 for transcript
- [ ] Receive property listing SMS
- [ ] Reply 1 → EventBridge cooldown scheduled
- [ ] Reply 2 → rejection reason collected, new listing sent

---

## 🚀 Before Production (Latency + Reliability)

### Latency Optimizations

#### Model / Inference
- [ ] **Warm up Moshi on notebook start** — run a silent audio pass through the model on boot so the first real call doesn't pay the cold-start cost
- [ ] **Keep notebook running between calls** — instead of stop/start per call, keep the notebook alive and stop after 30min of inactivity (saves ~60s call setup time)
- [ ] **Torch compile** — add `--compile` flag to Moshi server (speeds up per-frame inference ~20-30% on repeated calls after first)

#### Twilio
- [ ] **Pin media region to `ca1`** — cuts Twilio's internal routing latency by 20-50ms for Ontario callers
- [ ] **Set `<Stream track="inbound_track">`** instead of both tracks — halves WebSocket bandwidth if we don't need outbound echo reference (test first)

#### Audio Pipeline
- [ ] **Tune AEC filter length** — currently 5 frames (~100ms). Reduce to 3 frames (~60ms) if echo isn't an issue
- [ ] **Profile resampling bottleneck** — confirm `audioop.ratecv` isn't blocking the event loop under load

#### Backend
- [ ] **Railway region** — deploy in closest Railway region to ca-central-1 (currently `us-east4` Virginia; `ca-central` not available on Railway — acceptable given backend is not in audio path)
- [ ] **DynamoDB in ca-central-1** — eliminates cross-region call for session reads during voice events

### Reliability

#### SageMaker Notebook
- [ ] **Lifecycle config** — ensure both services (`voice-bridge`, `personaplex-model`) auto-start on notebook boot and restart on failure
- [ ] **Health check endpoint** — Railway pings `https://{notebook_ip}:8001/health` before placing call; if down, SMS user and retry
- [ ] **Notebook start timeout handling** — if notebook takes >120s to start, SMS user "taking longer than expected, calling in 2 min"

#### Session Handling
- [ ] **Idempotent SMS webhook** — Twilio can send duplicate webhooks; add dedup via DynamoDB condition expression
- [ ] **CallSid → phone mapping persistence** — `call_sessions` dict is in-memory on Railway; if Railway restarts mid-call, voice events will be lost. Move `call_sid → phone` mapping to DynamoDB

#### Post-Call Pipeline
- [ ] **Transcript retry logic** — if S3 poll times out (60s), retry search with partial session context instead of silently failing
- [ ] **LLM fallback** — if primary HuggingFace endpoint is paused/down, auto-retry with `GPT_OSS_BASE_URL_FALLBACK`
- [ ] **Restart HuggingFace LLM endpoints** — both endpoints are currently paused

#### Monitoring
- [ ] **Railway logs** — verify structured logging is on for SMS/voice events
- [ ] **CloudWatch** — set alert if EventBridge scheduler failures > 0
- [ ] **S3 transcript alarm** — alert if no transcript appears within 90s of call end

### Final Pre-Production Checklist
- [ ] End-to-end test with real Ontario phone number
- [ ] Test STOP keyword opt-out
- [ ] Test 1-hour cooldown drip (manually fire EventBridge event)
- [ ] Test LLM fallback endpoint
- [ ] Test notebook auto-restart after stop
- [ ] Load test: 2 simultaneous calls (verify session isolation)
- [ ] Confirm GPU stops after each call (cost control)

---

## Cost Estimate (Per Day, Light Usage)

| Resource | Cost |
|---|---|
| SageMaker ml.g5.xlarge (~2hr/day) | ~$0.92/day |
| Railway (hobby plan) | ~$0.17/day |
| DynamoDB (on-demand) | ~$0.01/day |
| S3 (recordings) | ~$0.01/day |
| Twilio (calls + SMS) | ~$0.10/call |
| **Total** | **~$1.11/day + $0.10/call** |
