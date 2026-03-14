# Transcript → search criteria

Turn a call transcript (or any conversation) into a structured criteria dict and save it as JSON. That dict is what the Zillow scraper expects: location, intent, price_max, beds_min, baths_min. Handy for demos and for wiring "intake call" → "search" without editing code.

---

## Run it

From project root:

```bash
python scripts/fake_call_search_criteria.py
```

With no arguments it uses `data/transcripts/sample_intake.txt`. To use another file:

```bash
python scripts/fake_call_search_criteria.py path/to/transcript.txt
```

Output: one JSON file under `data/search_criteria/`, named from the extracted location (e.g. `new_york.json`, `brooklyn_or_manhattan_ny.json`). The script prints the path. If the agent used Railtracks you'll see `(railtracks)` before the path; if it fell back to direct HTTP you'll see `(http fallback)`.

---

## Setup (once)

**Env**  
Copy `.env.example` to `.env` and set:

- `OPENAI_API_KEY` – any value the hackathon endpoint accepts (often a placeholder is fine).
- `GPT_OSS_BASE_URL` – your OpenAI-compatible endpoint (e.g. hackathon URL ending in `/v1`).
- `GPT_OSS_MODEL` – model id (e.g. `openai/gpt-oss-120b`).

**Deps**  
`pip install -r requirements.txt` (or at least railtracks, openai, jinja2, python-dotenv).

**Run from repo root** so `app.agents` and `app.config` resolve.

---

## What it does under the hood

1. Reads the transcript (default: `data/transcripts/sample_intake.txt`).
2. Renders two Jinja prompts from `templates/build_search_criteria/`: system (extract JSON with location, intent, price_max, beds_min, baths_min) and user (the transcript).
3. Calls the build-search-criteria agent. The agent uses Railtracks with `OpenAICompatibleProvider` (model + api_base + api_key) pointing at your endpoint. If that fails, it falls back to a direct HTTP POST to the same endpoint.
4. Parses the reply (strip markdown if present, then JSON) into a criteria dict.
5. Derives a filename from `location` (e.g. "Brooklyn or Manhattan NY" → `brooklyn_or_manhattan_ny.json`), creates `data/search_criteria/` if needed, writes the JSON there, and prints the path.

---

## Using the output with the Zillow scraper

**From disk**  
Load the JSON and pass it to the scraper:

```python
import json
from pathlib import Path
from data.zillow.scraper import search, build_search_url

path = Path("data/search_criteria/new_york.json")
criteria = json.loads(path.read_text())
data = search(criteria)
# data["listings"], data["listing_links"], data["raw_html"], data["search_url"]
```

**From code**  
Get criteria from a transcript without writing to disk:

```python
from app.agents.build_search_criteria import extract_search_criteria
from data.zillow.scraper import search

transcript = "..."  # or path.read_text()
criteria = extract_search_criteria(transcript)
data = search(criteria)
```

To run the full Zillow pipeline with fixed criteria, edit `data/zillow/run.py` and set its `criteria` dict (or load from a JSON file there).

---

## When something goes wrong

| Symptom | What to try |
|--------|-------------|
| `ModuleNotFoundError: railtracks` | Install deps; run from the same env. |
| `No module named 'app'` | Run from project root. |
| `Set GPT_OSS_BASE_URL and GPT_OSS_MODEL in .env` | Add those to `.env` (see .env.example). |
| Timeout / connection error | Check network and that the endpoint URL is correct. |
| Weird or empty criteria | Model might have returned non-JSON; you get a safe default (e.g. intent=rent, rest empty). |
