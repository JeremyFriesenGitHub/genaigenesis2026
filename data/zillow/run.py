"""Run Zillow search: save raw HTML and one JSON with criteria, URL, listings, links."""
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
    data = search(criteria)
    listings = data["listings"]
    links = data["listing_links"]
    raw_html = data["raw_html"]
    search_url = data["search_url"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ZILLOW_RAW_HTML.write_text(raw_html, encoding="utf-8")
    print(f"Saved raw HTML: {ZILLOW_RAW_HTML}")

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
