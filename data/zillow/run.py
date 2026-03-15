"""Run Zillow search: save raw HTML and one JSON with criteria, URL, listings, links.

Usage (from repo root):
  python -m data.zillow.run [path/to/criteria.json]
  python -m data.zillow.run data/search_criteria/new_york.json

If no path is given, uses data/search_criteria/new_york.json.
"""
import json
import sys
from pathlib import Path

from .scraper import search

DATA_DIR = Path(__file__).resolve().parent.parent
CRITERIA_DIR = DATA_DIR / "search_criteria"
OUTPUT_DIR = DATA_DIR / "output"
ZILLOW_RAW_HTML = OUTPUT_DIR / "zillow_raw.html"
ZILLOW_JSON = OUTPUT_DIR / "zillow.json"
DEFAULT_CRITERIA = CRITERIA_DIR / "new_york.json"


def load_criteria(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Criteria file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    # Normalize: location can be string in JSON; scraper accepts string or dict
    if "location" not in data:
        raise ValueError(f"Criteria file must contain 'location': {path}")
    return data


def main():
    criteria_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CRITERIA
    if not criteria_path.is_absolute():
        criteria_path = (Path.cwd() / criteria_path).resolve()
    criteria = load_criteria(criteria_path)
    print(f"Criteria: {criteria_path}")
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
