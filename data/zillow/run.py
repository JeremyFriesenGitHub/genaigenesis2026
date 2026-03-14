"""Run Zillow search: save raw HTML, then one JSON file with criteria, URL, listings, links."""
import json
from pathlib import Path

from .scraper import search

DATA_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = DATA_DIR / "output"
ZILLOW_RAW_HTML = OUTPUT_DIR / "zillow_raw.html"
ZILLOW_JSON = OUTPUT_DIR / "zillow.json"


def main():
    criteria = {
        "location": "New York NY",
        "intent": "rent",
        "price_max": 3000,
        "beds_min": 1,
    }
    print("Opening browser. Solve CAPTCHA if shown, then press Enter.\n")
    data = search(criteria, headless=False)
    listings = data["listings"]
    links = data["listing_links"]
    raw_html = data.get("raw_html") or ""
    search_url = data.get("search_url") or ""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Save raw HTML first (so when parsing breaks, you can inspect without rerunning)
    ZILLOW_RAW_HTML.write_text(raw_html, encoding="utf-8")
    print(f"Saved raw HTML: {ZILLOW_RAW_HTML}")

    # 2. Single output file: criteria, search_url, listing_count, listings, listing_links
    payload = {
        "criteria": criteria,
        "search_url": search_url,
        "listing_count": len(listings),
        "listings": listings,
        "listing_links": links,
    }
    ZILLOW_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved {ZILLOW_JSON}  (listings: {len(listings)}, links: {len(links)})")


if __name__ == "__main__":
    main()
