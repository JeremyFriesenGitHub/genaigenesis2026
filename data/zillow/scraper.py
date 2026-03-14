"""Zillow search: build URL, fetch via Playwright, parse."""
from urllib.parse import quote_plus

from .parse import dedupe_links, listing_links_from_html, parse_listings
from .playwright_fetch import fetch_html

SEARCH_SELECTOR = "script[data-zrr-shared-data-key], article, [data-test='property-card-price']"


def build_search_url(criteria: dict) -> str:
    location = criteria.get("location", "")
    intent = criteria.get("intent", "rent")
    price_max = criteria.get("price_max", "")
    beds_min = criteria.get("beds_min", "")
    slug = quote_plus(location)
    return f"https://www.zillow.com/homes/for_{intent}/{slug}/?price_max={price_max}&beds_min={beds_min}"


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
        return {"listings": [], "listing_links": [], "raw_html": "", "search_url": url}
    listings = parse_listings(html)
    links = listing_links_from_html(html)
    if not links and listings:
        links = [r.get("url", "") or "" for r in listings]
    links = dedupe_links(links)
    return {
        "listings": listings,
        "listing_links": links,
        "raw_html": html,
        "search_url": url,
    }
