"""
Integration test: transcript → LLM → search criteria.
Requires .env with GPT_OSS_BASE_URL and GPT_OSS_MODEL set.

Run:  python -m pytest tests/test_search_criteria.py -v -s
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT_PATH = ROOT / "trans.txt"


def test_extract_search_criteria_from_transcript():
    from app.agents.build_search_criteria import extract_search_criteria

    transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    result = extract_search_criteria(transcript)

    print("\n--- LLM output ---")
    for k, v in result.items():
        print(f"  {k}: {v!r}")
    print("------------------")

    assert isinstance(result, dict)
    required_keys = {"location", "intent", "price_max", "beds_min", "baths_min"}
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"

    assert "jersey" in result["location"].lower(), f"Expected NJ, got {result['location']!r}"
    assert result["intent"] in ("rent", "buy")
    assert result["beds_min"] == 2 or result["beds_min"] == "2"
