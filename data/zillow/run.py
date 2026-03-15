"""Run Zillow search: save raw HTML and one JSON with criteria, URL, listings, links."""
import json
from pathlib import Path

from .scraper import search

DATA_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = DATA_DIR / "output"
ZILLOW_RAW_HTML = OUTPUT_DIR / "zillow_raw.html"
ZILLOW_JSON = OUTPUT_DIR / "zillow.json"


def main():
    from pathlib import Path as _P
    _root = _P(__file__).resolve().parent.parent.parent
    _transcript = _root / "trans.txt"

    if _transcript.exists():
        from app.agents.build_search_criteria import extract_search_criteria
        print("Extracting search criteria from transcript...")
        criteria = extract_search_criteria(_transcript.read_text(encoding="utf-8"))
        print(f"Criteria: {json.dumps(criteria, indent=2)}\n")
    else:
        criteria = {
            "location": {"query": "New York NY", "city": "New York", "state_province": "NY"},
            "intent": "rent",
            "price": {"min": None, "max": 3000},
            "bedrooms": {"min": 1, "max": None},
            "bathrooms": {"min": None, "max": None},
            "property_type": [],
            "features": {"required": [], "nice_to_have": []},
        }

    print("Fetching listings via ScraperAPI...\n")
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
