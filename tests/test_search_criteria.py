"""
Integration test: transcript → LLM → search criteria.
Requires .env with GPT_OSS_BASE_URL and GPT_OSS_MODEL set.

Run:  python -m pytest tests/test_search_criteria.py -v -s
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT_PATH = ROOT / "trans.txt"


def test_extract_search_criteria_from_transcript():
    from app.agents.build_search_criteria import extract_search_criteria

    transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    result = extract_search_criteria(transcript)

    print("\n--- LLM output ---")
    print(json.dumps(result, indent=2))
    print("------------------")

    assert isinstance(result, dict)

    # -- top-level keys present --
    expected_keys = {
        "location", "intent", "price", "bedrooms", "bathrooms",
        "property_type", "size", "year_built", "features", "keywords",
        "sort", "page", "page_size",
    }
    assert expected_keys.issubset(result.keys()), f"Missing keys: {expected_keys - result.keys()}"

    # -- location --
    loc = result["location"]
    assert isinstance(loc, dict)
    loc_text = (loc.get("query") or "") + (loc.get("state_province") or "")
    assert "jersey" in loc_text.lower(), f"Expected NJ somewhere in location, got {loc}"

    # -- intent --
    assert result["intent"] in ("rent", "buy")

    # -- bedrooms --
    assert result["bedrooms"]["min"] == 2

    # -- features --
    all_features = result["features"].get("required", []) + result["features"].get("nice_to_have", [])
    assert "pet_friendly" in all_features or "near_schools" in all_features, (
        f"Expected pet_friendly or near_schools in features, got {all_features}"
    )

    # -- structural checks --
    assert isinstance(result["property_type"], list)
    assert isinstance(result["keywords"], list)
    assert isinstance(result["sort"], dict)
    assert result["page"] == 1
    assert result["page_size"] == 20
