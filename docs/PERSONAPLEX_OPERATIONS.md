# PersonaPlex voice operations – context

Quick reference from the voice/SMS + EC2 deployment work.

## Deployment

- **EC2**: `ubuntu@35.175.69.191`
- **SSH key**: `personaplex-key.pem` (e.g. `~/Desktop/personaplex/personaplex-key.pem`)
- **App on EC2**: `/opt/personaplex-api/genaigenesis2026`
- **API (public)**: `https://api.personaplex.click` (Caddy + TLS)
- **Uvicorn**: port 8000, log file `/tmp/uvicorn.log`
- **PersonaPlex/Moshi**: Docker `personaplex-personaplex-1`, port 8998; compose at `/home/ubuntu/personaplex` on EC2
- **Test number**: +1 (825) 203-5213 (Telnyx)

## Audio / sample rates

- **Telnyx L16** is **8 kHz** (standard telephony), not 16 kHz.  
  If you treat it as 16 kHz, playback on Telnyx will sound half-speed (slow-mo).
- **Resamplers in voice bridge**: `8000 ↔ 24000` (upsample 8k→24k for PersonaPlex, downsample 24k→8k for Telnyx).  
  See `app/routers/voice.py` (or `personaplex/app/routers/voice.py`): `StatefulResampler(in_rate=8000, out_rate=24000)` and `(in_rate=24000, out_rate=8000)`.

## Model

- **Voice**: NATF2.pt (Natural Female 2) – from EC2 `.env` (e.g. `VOICE_PATH` or equivalent).
- **Moshi**: Pre-quantized **brianmatzelle/personaplex-7b-v1-bnb-4bit** — use `--moshi-weight /app/model_bnb_4bit.pt` and `--quantize-4bit` with brianmatzelle’s modified `moshi/`; voices/mimi/tokenizer come from **nvidia/personaplex-7b-v1** (default `--hf-repo`). See `deploy/switch_to_brianmatzelle_prequant.sh` to switch EC2 to this setup.

### brianmatzelle pre-quantized vs current (on-the-fly 4-bit)

| | **Current (nvidia + `--quantize-4bit`)** | **brianmatzelle (pre-quant)** |
|---|----------------------------------------|-------------------------------|
| **Weights** | Full bf16 downloaded, then bitsandbytes 4-bit NF4 in memory at load | Pre-saved `model_bnb_4bit.pt`; loader skips re-quantization |
| **What’s quantized** | Whatever the stock server quantizes (often most linear layers) | Only main transformer linear layers (attention + FFN). **Mimi, Depformer, embeddings, output heads kept in bf16** → better audio |
| **Voice quality** | Can be slightly more artifacted | Often sounds more natural (audio-critical parts stay full precision) |
| **Voices** | Come from nvidia repo | Repo has no voice assets; use `--moshi-weight model_bnb_4bit.pt` + voices from nvidia (e.g. clone nvidia repo for voice-prompt-dir, or rely on HF cache after accepting license) |

To use brianmatzelle on EC2: run `deploy/switch_to_brianmatzelle_prequant.sh` on the host (or copy the script to EC2 and run it from the personaplex app dir). It replaces `moshi/` with brianmatzelle’s, adds `--moshi-weight /app/model_bnb_4bit.pt` to the server command, and rebuilds/restarts. Ensure `HF_TOKEN` is in `.env` and `model_bnb_4bit.pt` is at `/home/ubuntu/model_bnb_4bit.pt` (or pass paths as script args). If Docker build fails with "no space left on device", free space (`docker system prune -a`, clear `/tmp`) or use a larger volume.

## Recordings and SMS

- **Call recordings/transcripts on EC2**: `/tmp/recordings/*.txt` (one file per call; filename includes call ID).
- **SMS reset** (clear conversations):  
  `curl -s -X POST http://localhost:8000/sms/reset` (run on EC2 or against API).

## Latency logging

- In `voice.py`, every 250 chunks: Telnyx→PersonaPlex processing time, PersonaPlex→Telnyx queue/convert/send, and time to first model response after last user audio.
- PersonaPlex client also logs send timing every 250 sends.
- After a call, inspect `/tmp/uvicorn.log` on EC2 for these numbers.

## Deploying code changes

- Rsync app files to EC2, then SSH in and restart Uvicorn, e.g.:  
  `pkill -f 'uvicorn app.main'` then  
  `cd /opt/personaplex-api/genaigenesis2026 && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &`
- Restart Moshi: from `/home/ubuntu/personaplex` on EC2, `docker compose down && docker compose up -d` (model load can take a few minutes with 4-bit).

## Repo layout

- **Root** `genaigenesis2026`: main app (agents, contact, data, deploy, etc.).
- **Subfolder** `personaplex/`: voice integration (Telnyx/PersonaPlex bridge, audio_utils, recorder, personaplex_client, tests).  
  The 8 kHz fix and latency logging live in `personaplex/app/routers/voice.py`; the deployed EC2 app may use code from repo root or from this folder depending on how it’s set up.
