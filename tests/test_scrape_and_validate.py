"""
End-to-end test: transcript → LLM → search criteria → Zillow scrape → detail features → rank.
Requires .env with GPT_OSS_BASE_URL, GPT_OSS_MODEL, SCRAPER_API_KEY.

Run:  python -m pytest tests/test_scrape_and_validate.py -v -s
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT_PATH = ROOT / "trans.txt"


def _print_listing(r: dict, label: str):
    print(f"\n  [{label}] {r['title']}")
    print(f"       score={r['_score']}  price={r['price']!r}  beds={r['beds']!r}")
    detail = r.get("_detail_features", {})
    if detail.get("features_found"):
        print(f"       features found: {detail['features_found']}")
    if detail.get("pet_policy"):
        print(f"       pet policy: {detail['pet_policy']}")
    if detail.get("parking"):
        print(f"       parking: {detail['parking']}")
    if detail.get("schools"):
        nearby = [f"{s['name']} ({s['distance']}mi, rated {s['rating']})" for s in detail["schools"][:3]]
        print(f"       schools: {', '.join(nearby)}")
    for note in r.get("_feature_notes", []):
        print(f"       • {note}")
    for v in r.get("_violations", []):
        print(f"       !! {v}")


def test_full_pipeline():
    from app.agents.build_search_criteria import extract_search_criteria
    from data.zillow.scraper import search

    # Step 1: extract criteria from transcript
    transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    criteria = extract_search_criteria(transcript)

    print("\n=== SEARCH CRITERIA ===")
    print(json.dumps(criteria, indent=2))

    # Step 2: broad scrape + detail fetch + rank
    data = search(criteria)
    results = data["results"]

    print(f"\n=== {results['message']} ===")

    matches = results["matches"]
    nearest = results["nearest"]

    if matches:
        print(f"\n--- EXACT MATCHES ({len(matches)}) ---")
        for r in matches:
            _print_listing(r, "MATCH")

    if nearest:
        print(f"\n--- CLOSEST ({len(nearest)}) ---")
        for r in nearest:
            _print_listing(r, "CLOSE")

    total = len(matches) + len(nearest)
    print(f"\n=== SUMMARY ===")
    print(f"  Total scraped:  {total}")
    print(f"  Exact matches:  {len(matches)}")
    print(f"  Closest:        {len(nearest)}")
    print(f"  Search URL:     {data['search_url']}")

    assert total > 0, "No listings returned — scraper may have been blocked"
    assert matches or nearest, "Expected at least some listings"

    if not matches and nearest:
        top = nearest[0]
        print(f"\n  Best near-match: {top['title']} (score {top['_score']})")
