"""
Tool: Inspect the structure of a Zillow detail page to find features/facts/policies.

Usage:
    python -m data.zillow.inspect_detail <url_or_local_html>

Examples:
    python -m data.zillow.inspect_detail https://www.zillow.com/apartments/orange-nj/the-elks/CqTWcY/
    python -m data.zillow.inspect_detail data/output/detail_sample.html
"""
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def find_property_data(obj, depth=0, path=""):
    """Recursively search for property/feature data in nested JSON."""
    if depth > 8:
        return
    if isinstance(obj, dict):
        for key in obj:
            if key in ("resoFacts", "buildingAttributes", "petPolicy", "amenities",
                       "amenityDetails", "atAGlanceFacts", "homeFacts", "assignedSchools"):
                print(f"\nFOUND '{key}' at path: {path}.{key}")
                print(json.dumps(obj[key], indent=2)[:3000])
            elif key == "property" and isinstance(obj[key], dict):
                print(f"\nFOUND 'property' at path: {path}.property")
                print(f"  keys: {sorted(obj[key].keys())}")
                find_property_data(obj[key], depth + 1, f"{path}.property")
            else:
                val = obj[key]
                if isinstance(val, (dict, list, str)):
                    if isinstance(val, str) and len(val) > 100:
                        try:
                            parsed = json.loads(val)
                            find_property_data(parsed, depth + 1, f"{path}.{key}(parsed)")
                        except json.JSONDecodeError:
                            pass
                    elif isinstance(val, (dict, list)):
                        find_property_data(val, depth + 1, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:5]):
            find_property_data(item, depth + 1, f"{path}[{i}]")


def inspect_html(html: str):
    """Parse all script tags in the HTML and search for property/feature data."""
    soup = BeautifulSoup(html, "html.parser")

    for i, s in enumerate(soup.select("script")):
        text = s.string or ""
        if not text.strip():
            continue
        for start_char in ("", "!"):
            candidate = text.strip().lstrip(start_char).strip("<>-! ")
            try:
                d = json.loads(candidate)
                print(f"\n{'=' * 60}")
                print(f"Script #{i}: parsed OK, type={type(d).__name__}")
                if isinstance(d, dict):
                    print(f"  top keys: {list(d.keys())[:15]}")
                find_property_data(d, 0, f"script#{i}")
                break
            except json.JSONDecodeError:
                pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]
    path = Path(target)

    if path.exists():
        print(f"Reading local file: {path}")
        html = path.read_text(encoding="utf-8")
    else:
        print(f"Fetching URL: {target}")
        from .playwright_fetch import fetch_html
        html = fetch_html(target, headless=True)
        if not html:
            print("Failed to fetch page.")
            sys.exit(1)

    inspect_html(html)


if __name__ == "__main__":
    main()
