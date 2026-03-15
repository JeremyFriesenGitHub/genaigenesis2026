"""Run Zillow contact-agent demo. Same pattern as run_zillow_search.py: run from repo root."""
import json
import logging
import sys
from pathlib import Path

# Run from repo root: python scripts/run_contact_demo.py --listing-url "..." --name "..." --email "..." --phone "..." --message "..."
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.contact.contact_agent import Lead, ContactResult, run_contact_flow

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(
        description="Zillow contact-agent demo (preview by default). Use a real listing URL from data/output/zillow*.json."
    )
    p.add_argument("--listing-url", required=True, help="Zillow listing URL (e.g. from zillow.json listings[].url)")
    p.add_argument("--name", required=True, help="Lead name")
    p.add_argument("--email", required=True, help="Lead email")
    p.add_argument("--phone", required=True, help="Lead phone")
    p.add_argument("--message", required=True, help="Inquiry message")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--preview", action="store_true", help="Fill form but do not submit (default)")
    g.add_argument("--submit", action="store_true", help="Fill form and submit")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--slow-mo", type=int, default=80, metavar="MS", help="Slow motion ms (default 80)")
    args = p.parse_args()

    mode = "submit" if args.submit else "preview"
    lead = Lead(name=args.name, email=args.email, phone=args.phone, message=args.message)

    result: ContactResult = run_contact_flow(
        args.listing_url,
        lead,
        mode=mode,
        headless=args.headless,
        slow_mo_ms=args.slow_mo,
    )

    out = {
        "cta_found": result.cta_found,
        "form_found": result.form_found,
        "fields_filled": result.fields_filled,
        "submit_button_found": result.submit_button_found,
        "submitted": result.submitted,
        "error": result.error,
        "debug_artifacts": result.debug_artifacts,
    }
    print(json.dumps(out, indent=2))

    if result.error:
        sys.exit(1)
    if mode == "preview" and result.cta_found:
        print("Preview complete. Form filled, not submitted.", file=sys.stderr)


if __name__ == "__main__":
    main()
