"""Zillow search: broad scrape, then score & rank listings against criteria."""
import re
from urllib.parse import quote_plus

from .parse import dedupe_links, listing_links_from_html, parse_listings
from .playwright_fetch import fetch_html

SEARCH_SELECTOR = "script[data-zrr-shared-data-key], article, [data-test='property-card-price']"


# ---------------------------------------------------------------------------
# URL builder — intentionally broad (location + intent only)
# ---------------------------------------------------------------------------

def build_search_url(criteria: dict) -> str:
    loc = criteria.get("location", {})
    if isinstance(loc, dict):
        location = loc.get("query") or loc.get("city") or loc.get("state_province") or ""
    else:
        location = str(loc)

    intent = criteria.get("intent", "rent")
    slug = quote_plus(location)
    return f"https://www.zillow.com/homes/for_{intent}/{slug}/"


# ---------------------------------------------------------------------------
# Listing field parsers
# ---------------------------------------------------------------------------

def _parse_price(price_str: str) -> int | None:
    m = re.search(r"\$?([\d,]+)", (price_str or "").replace(",", ""))
    return int(m.group(1)) if m else None


def _parse_beds(beds_str: str) -> int | None:
    m = re.search(r"(\d+)\s*b", (beds_str or "").lower())
    return int(m.group(1)) if m else None


def _parse_baths(baths_str: str) -> float | None:
    m = re.search(r"([\d.]+)\s*ba", (baths_str or "").lower())
    return float(m.group(1)) if m else None


def _parse_sqft(sqft_str: str) -> int | None:
    m = re.search(r"([\d,]+)\s*sq", (sqft_str or "").replace(",", "").lower())
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Scoring — how well does a listing match the criteria?
# ---------------------------------------------------------------------------

def _score_listing(listing: dict, criteria: dict) -> tuple[float, list[str]]:
    """
    Score 0.0 (worst) to 1.0 (perfect match).
    Returns (score, list_of_violation_strings).
    """
    score = 1.0
    violations = []

    price = _parse_price(listing.get("price", ""))
    beds = _parse_beds(listing.get("beds", ""))
    baths = _parse_baths(listing.get("baths", ""))
    sqft = _parse_sqft(listing.get("sqft", ""))

    # --- price ---
    price_crit = criteria.get("price", {}) if isinstance(criteria.get("price"), dict) else {}
    p_max = price_crit.get("max")
    p_min = price_crit.get("min")

    if p_max and price:
        if price <= p_max:
            score += 0.3
        else:
            overshoot = (price - p_max) / p_max
            penalty = min(overshoot * 0.5, 0.5)
            score -= penalty
            violations.append(f"price ${price:,} > max ${p_max:,} (+{overshoot:.0%})")
    if p_min and price:
        if price < p_min:
            violations.append(f"price ${price:,} < min ${p_min:,}")
            score -= 0.2

    # --- bedrooms ---
    beds_crit = criteria.get("bedrooms", {}) if isinstance(criteria.get("bedrooms"), dict) else {}
    b_min = beds_crit.get("min")
    b_max = beds_crit.get("max")

    if b_min and beds:
        if beds >= b_min:
            score += 0.2
        else:
            violations.append(f"beds {beds} < min {b_min}")
            score -= 0.3
    if b_max and beds:
        if beds > b_max:
            violations.append(f"beds {beds} > max {b_max}")
            score -= 0.1

    # --- bathrooms ---
    baths_crit = criteria.get("bathrooms", {}) if isinstance(criteria.get("bathrooms"), dict) else {}
    ba_min = baths_crit.get("min")

    if ba_min and baths:
        if baths >= ba_min:
            score += 0.1
        else:
            violations.append(f"baths {baths} < min {ba_min}")
            score -= 0.1

    # --- sqft ---
    size_crit = criteria.get("size", {}) if isinstance(criteria.get("size"), dict) else {}
    sqft_min = size_crit.get("sqft_min")

    if sqft_min and sqft:
        if sqft >= sqft_min:
            score += 0.1
        else:
            violations.append(f"sqft {sqft} < min {sqft_min}")
            score -= 0.1

    # Bonus: if we couldn't parse price/beds the listing is incomplete — small penalty
    if price is None:
        score -= 0.05
    if beds is None:
        score -= 0.05

    return (max(score, 0.0), violations)


def rank_listings(listings: list[dict], criteria: dict) -> dict:
    """
    Score every listing, split into matches (no violations) and
    nearest (has violations, sorted by score descending).
    """
    scored = []
    for listing in listings:
        s, v = _score_listing(listing, criteria)
        scored.append({**listing, "_score": round(s, 3), "_violations": v})

    scored.sort(key=lambda x: x["_score"], reverse=True)

    matches = [r for r in scored if not r["_violations"]]
    nearest = [r for r in scored if r["_violations"]]

    if matches:
        message = f"Found {len(matches)} listing(s) matching your criteria."
    elif nearest:
        message = (
            "No exact matches found for your criteria. "
            f"Here are the {len(nearest)} closest listing(s), ranked by how well they fit."
        )
    else:
        message = "No listings found for this search."

    return {
        "message": message,
        "matches": matches,
        "nearest": nearest,
    }


# ---------------------------------------------------------------------------
# Main search entry point
# ---------------------------------------------------------------------------

def search(criteria: dict, *, headless: bool = False) -> dict:
    url = build_search_url(criteria)
    html = fetch_html(
        url,
        headless=headless,
        wait_selector=SEARCH_SELECTOR,
        wait_timeout_ms=25_000,
        pause_for_captcha=True,
    )
    if not html:
        return {
            "search_url": url,
            "raw_html": "",
            "listings": [],
            "listing_links": [],
            "results": rank_listings([], criteria),
        }

    listings = parse_listings(html)
    links = listing_links_from_html(html)
    if not links and listings:
        links = [r.get("url", "") or "" for r in listings]
    links = dedupe_links(links)

    return {
        "search_url": url,
        "raw_html": html,
        "listings": listings,
        "listing_links": links,
        "results": rank_listings(listings, criteria),
    }
