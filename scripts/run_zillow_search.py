"""Run Zillow scraper with configurable city/criteria. Practice script for different markets."""
import json
import re
import sys
from pathlib import Path

# Run from repo root: python scripts/run_zillow_search.py [--city "Chicago IL"]
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.zillow.scraper import search

OUTPUT_DIR = ROOT / "data" / "output"


def main():
    import argparse
    p = argparse.ArgumentParser(description="Run Zillow search for a city")
    p.add_argument("--city", default="Chicago IL", help="Location, e.g. 'Chicago IL', 'San Francisco CA'")
    p.add_argument("--rent", action="store_true", default=True, help="Search for rent (default)")
    p.add_argument("--buy", action="store_true", help="Search for sale")
    p.add_argument("--price-max", type=int, default=2500, help="Max price (default 2500)")
    p.add_argument("--beds-min", type=int, default=1, help="Min beds (default 1)")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    args = p.parse_args()

    intent = "sale" if args.buy else "rent"
    criteria = {
        "location": args.city,
        "intent": intent,
        "price_max": args.price_max,
        "beds_min": args.beds_min,
    }
    slug = re.sub(r"[^\w]+", "_", args.city.strip()).strip("_").lower() or "search"
    out_json = OUTPUT_DIR / f"zillow_{slug}.json"
    out_html = OUTPUT_DIR / f"zillow_{slug}_raw.html"

    print(f"Search: {criteria}")
    print("Opening browser. Solve CAPTCHA if shown, then press Enter.\n")
    data = search(criteria, headless=args.headless)
    listings = data["listings"]
    links = data["listing_links"]
    raw_html = data["raw_html"]
    search_url = data["search_url"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_html.write_text(raw_html, encoding="utf-8")
    print(f"Saved raw HTML: {out_html}")

    payload = {
        "criteria": criteria,
        "search_url": search_url,
        "listing_count": len(listings),
        "listings": listings,
        "listing_links": links,
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved {out_json}  (listings: {len(listings)}, links: {len(links)})")


if __name__ == "__main__":
    main()
