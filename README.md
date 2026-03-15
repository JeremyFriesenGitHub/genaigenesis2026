# Agent<sup>2</sup>

[![Built at GenAI Genesis 2026](https://img.shields.io/badge/GenAI_Genesis-2026-blue)](#)

**Your real estate agent <ins>agent</ins>.** Text a number, take a short call, and get matched home listings sent to your phone. No apps, no accounts, no browsing.

---

## What is this?

Agent<sup>2</sup> is an end-to-end AI-powered home buying assistant. A user texts our number, receives a call from an AI voice agent (Mary), describes what kind of home they want in plain conversation, and gets real listings texted back — then we contact the listing agent on their behalf.

1. **Listens** to the conversation via a Telnyx + PersonaPlex voice pipeline with real-time echo cancellation (SpeexDSP AEC + RNNoise)
2. **Extracts** structured search criteria (location, budget, bedrooms, features, etc.) from the transcript using an LLM
3. **Scrapes** Zillow for matching listings with filtered search URLs, scores them against the criteria, and ranks by fit
4. **Contacts agents** on the caller's behalf by automating the "Contact Agent" form on Zillow with Playwright

The whole flow — from a spoken sentence like *"I'm looking for a two-bedroom house in Toronto, under 800k, pet-friendly"* to a filled-out contact form on a real listing — is automated.

---

## How it works

```
User texts Agent² number
        │
        ▼
  SMS greeting → user replies YES
        │
        ▼
  AI calls user back (Telnyx + PersonaPlex voice agent "Mary")
        │
        ▼
  Full-duplex conversation with AEC + RNNoise audio pipeline
        │
        ▼
  Transcript extracted (faster-whisper) → LLM extracts search criteria
        │
        ▼
  Zillow searched with filtered URLs (price, beds, baths, location)
        │
        ▼
  Listings scored, ranked, deduped → LLM picks best match
        │
        ▼
  Top listing sent to user via SMS
        │
        ▼
  User replies YES → contact agent form filled (Playwright)
  User replies NO  → asks why → re-searches with feedback
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  EC2 (g6e.xlarge, NVIDIA L40S 46GB)                 │
│                                                      │
│  ┌──────────────┐  ┌──────────────────────────────┐ │
│  │ PersonaPlex   │  │ FastAPI (app.main)            │ │
│  │ Voice Model   │  │  • /sms/webhook              │ │
│  │ (7B, 4-bit)   │◄─┤  • /voice/stream (WS bridge) │ │
│  │ Port 8998     │  │  • /voice/events             │ │
│  └──────────────┘  │  • /pipeline/inbound          │ │
│                     │  • /contact/run               │ │
│                     └──────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
         ▲                        ▲
         │ WebSocket              │ HTTPS
         │ (audio bridge)         │ (webhooks)
         ▼                        ▼
    ┌──────────┐            ┌──────────┐
    │  Telnyx  │            │  Telnyx  │
    │  Voice   │            │  SMS     │
    └──────────┘            └──────────┘
```

### Audio Pipeline (per call)

```
Caller mic (8kHz) → SpeexDSP AEC → RNNoise → upsample 24kHz → PersonaPlex
                         ▲
PersonaPlex out → downsample 8kHz → feed as AEC reference → send to caller
```

- **SpeexDSP AEC**: Removes model echo using playback reference signal (~20ms)
- **RNNoise**: Neural noise suppression for background noise (~10ms, pipelined)
- **Total overhead**: ~20ms — duplex/barge-in preserved

---

## Setup

### Prerequisites

- Python 3.10+
- [ScraperAPI](https://www.scraperapi.com/) key (for Zillow scraping)
- Telnyx account (SMS + voice)
- OpenAI-compatible LLM endpoint (for criteria extraction + listing ranking)
- EC2 GPU instance with PersonaPlex (for voice model)

### Install

```bash
git clone https://github.com/chantalzhang/genaigenesis2026.git
cd genaigenesis2026
pip install -r requirements.txt
playwright install chromium
```

### Environment variables

Copy `.env.example` to `.env` and fill in:

```
TELNYX_API_KEY=...
TELNYX_PHONE_NUMBER=+1...
TELNYX_CONNECTION_ID=...
APP_BASE_URL=https://...
STREAM_WS_URL=wss://.../voice/stream
VOICE_EVENTS_URL=https://.../voice/events
GPT_OSS_BASE_URL=https://your-llm-endpoint/v1
GPT_OSS_MODEL=openai/gpt-oss-120b
SCRAPER_API_KEY=...
PERSONAPLEX_STREAM_URL=wss://...:8998/api/chat
PERSONAPLEX_TEXT_PROMPT=...
```

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## SMS State Machine

```
new → awaiting_confirmation → in_call → searching → awaiting_property_feedback
                                                          │                │
                                                    (YES) → contact       (NO) → awaiting_rejection_reason
                                                      agent + cooldown              │
                                                      (1hr) → searching      re-search with feedback
```

Text **RESET** at any time to clear your session and start over.

---

## Quick demo (end-to-end)

```bash
python run_e2e.py
```

This will:
1. Read `trans.txt` (sample call transcript)
2. Call the LLM to extract search criteria
3. Scrape Zillow for matching listings
4. Open a browser and fill the "Contact Agent" form on the top listing

---

## Run individual pieces

### Extract search criteria from a transcript

```python
from app.agents.build_search_criteria import extract_search_criteria

criteria = extract_search_criteria(open("trans.txt").read())
```

### Scrape Zillow listings

```python
from data.zillow.scraper import search

results = search(criteria)
# results["matches"]  — listings that fit all criteria
# results["nearest"]  — close alternatives with violations
```

### Contact an agent on a listing

```python
from app.contact import Lead, run_contact_flow

result = run_contact_flow(
    "https://www.zillow.com/homedetails/...",
    Lead(),
    mode="preview",
    headless=False,
)
```

### Run tests

```bash
python -m pytest tests/ -v -s
```

---

## Project structure

```
genaigenesis2026/
├── app/
│   ├── main.py                    # FastAPI app, pipeline endpoints
│   ├── config.py                  # Environment config
│   ├── audio_utils.py             # Resampling, AEC, RNNoise pipeline
│   ├── routers/
│   │   ├── sms.py                 # SMS webhook + session state machine
│   │   └── voice.py               # Telnyx ↔ PersonaPlex audio bridge
│   ├── agents/
│   │   └── build_search_criteria.py  # LLM: transcript → search criteria
│   ├── contact/
│   │   ├── contact_agent.py       # Playwright: listing → fill contact form
│   │   ├── fill_form.py           # Character-by-character form filling
│   │   ├── locators.py            # CTA button, form, submit locators
│   │   └── debug.py               # Failure screenshots/HTML
│   └── services/
│       ├── telnyx_sms.py          # Send SMS via Telnyx API
│       ├── telnyx_voice.py        # Outbound call via Telnyx Call Control
│       ├── search_pipeline.py     # Transcript → criteria → Zillow → SMS
│       ├── personaplex_client.py  # PersonaPlex WebSocket client
│       ├── prewarm.py             # Pre-warm PersonaPlex connections
│       └── recorder.py            # Call recording + transcription
├── data/zillow/
│   ├── scraper.py                 # URL builder, search, score & rank
│   ├── parse.py                   # Parse Zillow HTML
│   ├── detail.py                  # Fetch listing detail features
│   └── playwright_fetch.py        # HTTP fetch via ScraperAPI
├── templates/build_search_criteria/
│   ├── system_prompt.jinja        # LLM instructions + JSON schema
│   └── user_prompt.jinja          # Transcript input template
├── static/                        # Landing page
├── tests/
└── run_e2e.py                     # End-to-end demo script
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, Uvicorn |
| **Voice** | Telnyx Call Control + Media Streaming, PersonaPlex 7B (4-bit quantized) |
| **Audio** | SpeexDSP (echo cancellation), RNNoise (noise suppression), audioop (resampling) |
| **AI** | OpenAI-compatible LLM (criteria extraction + listing ranking) |
| **Scraping** | ScraperAPI + Playwright (Zillow search + detail pages) |
| **Browser automation** | Playwright + Stealth (contact agent form fill) |
| **Infrastructure** | AWS EC2 g6e.xlarge (NVIDIA L40S 46GB), Docker |
| **Frontend** | HTML, CSS, JavaScript (landing page) |

---

## Search criteria schema

The LLM extracts this from a conversation:

```json
{
  "location": { "query": "Toronto", "city": "Toronto", "state_province": "ON" },
  "intent": "buy",
  "price": { "min": 500000, "max": 1000000 },
  "bedrooms": { "min": 3, "max": null },
  "bathrooms": { "min": 2, "max": null },
  "property_type": ["house"],
  "features": {
    "required": ["pet_friendly", "near_schools"],
    "nice_to_have": ["parking", "basement"]
  }
}
```

Price always includes both min and max. Location always includes province/state abbreviation for Canadian/US cities.

---

## Listing scoring

Each listing is scored against criteria:

- **Price**: within budget = +0.3, over budget = penalty scaled by overshoot
- **Bedrooms/bathrooms**: meeting minimums = bonus, below = violation
- **Property type**: matched from title/URL
- **Features**: checked from detail page. Required missing = violation; nice-to-have = bonus
- **Deduplication**: seen listings tracked per session, never sent twice

Listings split into **exact matches** and **nearest alternatives** (ranked by score, violations listed).
