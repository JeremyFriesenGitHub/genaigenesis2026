from __future__ import annotations

import json
import logging

import httpx

from app.agents.build_search_criteria import extract_search_criteria
from data.zillow import search
from app.services.telnyx_sms import send_sms
from app.config import GPT_OSS_BASE_URL, GPT_OSS_MODEL

logger = logging.getLogger(__name__)


def _sync_to_ec2(phone: str, session: dict) -> None:
    """Push session state back to EC2 so its SMS handler stays in sync."""
    import os
    ec2_url = os.environ.get("APP_BASE_URL", "")
    if not ec2_url:
        return
    try:
        httpx.post(
            f"{ec2_url}/session/sync",
            json={
                "phone": phone,
                "state": session.get("state"),
                "current_property": session.get("current_property"),
                "criteria": session.get("criteria"),
                "rejection_reasons": session.get("rejection_reasons"),
                "page": session.get("page"),
            },
            timeout=10.0,
        )
        logger.info("Session synced to EC2 for %s (state=%s)", phone, session.get("state"))
    except Exception:
        logger.exception("Failed to sync session to EC2 for %s", phone)


def _normalize_criteria(raw: dict) -> dict:
    """Convert flat LLM output (price_max, beds_min) to nested format the scorer expects."""
    c = dict(raw)
    # price
    if "price_max" in c or "price_min" in c:
        p_max = c.pop("price_max", None)
        p_min = c.pop("price_min", None)
        c["price"] = {"max": p_max if p_max != "" else None,
                       "min": p_min if p_min != "" else None}
    # bedrooms
    if "beds_min" in c or "beds_max" in c:
        b_min = c.pop("beds_min", None)
        b_max = c.pop("beds_max", None)
        c["bedrooms"] = {"min": int(b_min) if b_min not in (None, "") else None,
                          "max": int(b_max) if b_max not in (None, "") else None}
    # bathrooms
    if "baths_min" in c or "baths_max" in c:
        ba_min = c.pop("baths_min", None)
        ba_max = c.pop("baths_max", None)
        c["bathrooms"] = {"min": int(ba_min) if ba_min not in (None, "") else None,
                           "max": int(ba_max) if ba_max not in (None, "") else None}
    return c


async def run_search(phone: str, transcript_path: str | None = None, transcript: str | None = None) -> None:
    from app.routers.sms import sessions

    session = sessions.get(phone)
    if not session:
        return

    # Step 1: Extract criteria from transcript (first call only)
    transcript_text = transcript or (open(transcript_path).read() if transcript_path else None)
    if transcript_text and not session.get("criteria"):
        try:
            raw = extract_search_criteria(transcript_text)
            session["criteria"] = _normalize_criteria(raw)
            logger.info("Criteria for %s: %s", phone, session["criteria"])
        except Exception:
            logger.exception("Failed to extract criteria for %s", phone)
            send_sms(phone, "Sorry, I had trouble understanding the call. Could you text me what you're looking for?")
            session["state"] = "new"
            _sync_to_ec2(phone, session)
            return

    criteria = session.get("criteria")
    if not criteria:
        send_sms(phone, "I don't have your search criteria yet. Let me call you!")
        session["state"] = "new"
        return

    # Step 2: Search Zillow with current page
    criteria_with_page = {**criteria, "page": session["page"]}
    try:
        results = search(criteria_with_page)
    except Exception:
        logger.exception("Zillow search failed for %s", phone)
        send_sms(phone, "I hit a snag searching listings. I'll try again shortly!")
        return

    ranked = results.get("results", results)
    listings = ranked.get("matches", []) or ranked.get("nearest", [])

    # Deduplicate — never send a listing the user already saw
    seen = set(session.get("seen_urls", []))
    listings = [l for l in listings if l.get("url", "") not in seen]

    if not listings:
        send_sms(phone, "I've exhausted the listings I can find matching your criteria. Want to adjust what you're looking for?")
        session["state"] = "new"
        _sync_to_ec2(phone, session)
        return

    # Step 3: LLM picks best property
    top = listings[:5]
    chosen = _llm_pick(top, criteria, session["rejection_reasons"])

    if not chosen:
        chosen = top[0]  # fallback to top score

    # Step 4: Send property
    session["current_property"] = chosen
    session["state"] = "awaiting_property_feedback"

    url = chosen.get("url", "No URL")
    session.setdefault("seen_urls", []).append(url)
    price = chosen.get("price", "")
    address = chosen.get("address", "") or chosen.get("title", "")
    beds = chosen.get("beds", "")
    baths = chosen.get("baths", "")

    send_sms(phone, f"🏠 {address}\n{beds} bed · {baths} bath · {price}\n{url}")
    send_sms(phone, "Do you like this one?")

    # Sync state back to EC2 so it knows we're awaiting feedback
    _sync_to_ec2(phone, session)


def _llm_pick(listings: list[dict], criteria: dict, rejection_reasons: list[str]) -> dict | None:
    """Ask the LLM to pick the best property from the scored list."""
    summaries = []
    for i, l in enumerate(listings):
        url = l.get("url", "")
        summaries.append(
            f"{i}: {l.get('address')} — {l.get('price')} — "
            f"{l.get('beds')} bed/{l.get('baths')} bath — score: {l.get('_score', 0):.2f} "
            f"— violations: {l.get('_violations', [])}\n   Zillow link: {url}"
        )

    rejection_text = "\n".join(rejection_reasons) if rejection_reasons else "None"
    prompt = (
        f"You are a real estate advisor. Pick the single best listing for a user based on their preferences.\n\n"
        f"Search criteria: {json.dumps(criteria, default=str)}\n\n"
        f"User rejection feedback from previous listings:\n{rejection_text}\n\n"
        f"Listings (index: address — price — beds/baths — match score — violations; each has a Zillow link):\n"
        + "\n".join(summaries)
        + "\n\n"
        "Use the Zillow links above to search or open each listing on Zillow and compare details (photos, description, location, amenities) when making your decision. Then pick the single best option.\n\n"
        "Respond with JSON only: {\"index\": <number>}"
    )

    try:
        resp = httpx.post(
            f"{GPT_OSS_BASE_URL}/chat/completions",
            headers={"Authorization": "Bearer test", "Content-Type": "application/json"},
            json={"model": GPT_OSS_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 50, "temperature": 0.0},
            timeout=30.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"] or ""
        # Extract JSON if wrapped in markdown
        if "```" in content:
            content = content.split("```")[1].strip().lstrip("json").strip()
        if not content:
            return None
        idx = json.loads(content).get("index", 0)
        return listings[int(idx)]
    except Exception:
        logger.exception("LLM pick failed, falling back to top result")
        return None
