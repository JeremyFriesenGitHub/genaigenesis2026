"""
Run the build-search-criteria agent on a transcript; writes data/search_criteria/<city>.json.
Default transcript: data/transcripts/sample_intake.txt. See docs/TRANSCRIPT_TO_CRITERIA.md.
Run from repo root: python scripts/fake_call_search_criteria.py [path/to/transcript.txt]
"""
import json
import re
import sys
from pathlib import Path

# Add project root so app.agents is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.build_search_criteria import extract_search_criteria

# Default: use sample transcript in data/transcripts/ (treat as real call)
DEFAULT_TRANSCRIPT_PATH = ROOT / "data" / "transcripts" / "sample_intake.txt"
OUTPUT_CRITERIA_DIR = ROOT / "data" / "search_criteria"


def _filename_from_location(location: str) -> str:
    """Turn location (e.g. 'New York', 'Brooklyn NY') into a safe filename stem."""
    if not (location or "").strip():
        return "unknown"
    s = re.sub(r"[^\w\s-]", "", str(location).strip())
    s = re.sub(r"[-\s]+", "_", s).strip("_").lower()
    return s or "unknown"


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = DEFAULT_TRANSCRIPT_PATH
    if not path.exists():
        print(f"Transcript file not found: {path}")
        sys.exit(1)
    transcript = path.read_text(encoding="utf-8").strip()
    criteria = extract_search_criteria(transcript)
    location = criteria.get("location") or ""
    name = _filename_from_location(location)
    OUTPUT_CRITERIA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_CRITERIA_DIR / f"{name}.json"
    out_path.write_text(json.dumps(criteria, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
