"""Run Zillow contact-agent demo using MultiOn browse API."""
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from app.contact_multion.contact_agent import Lead, ContactResult, run_contact_flow

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Zillow contact-agent via MultiOn (preview by default).")
    p.add_argument("--listing-url", required=True, help="Zillow listing URL")
    p.add_argument("--name", required=True, help="Lead name")
    p.add_argument("--email", required=True, help="Lead email")
    p.add_argument("--phone", required=True, help="Lead phone")
    p.add_argument("--message", required=True, help="Inquiry message")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--preview", action="store_true", help="Fill form but do not submit (default)")
    g.add_argument("--submit", action="store_true", help="Fill form and submit")
    p.add_argument("--local", action="store_true", help="Use local browser (needs MultiOn extension)")
    p.add_argument("--no-proxy", action="store_true", help="Disable proxy")
    p.add_argument("--max-steps", type=int, default=20, help="Max steps (default 20)")
    args = p.parse_args()

    mode = "submit" if args.submit else "preview"
    lead = Lead(name=args.name, email=args.email, phone=args.phone, message=args.message)

    result: ContactResult = run_contact_flow(
        args.listing_url,
        lead,
        mode=mode,
        local=args.local,
        use_proxy=not args.no_proxy,
        max_steps=args.max_steps,
    )

    out = {
        "session_id": result.session_id,
        "status": result.status,
        "message": result.message,
        "url": result.url,
        "screenshot": result.screenshot,
        "error": result.error,
        "metadata": result.metadata,
    }
    print(json.dumps(out, indent=2))

    if result.error:
        sys.exit(1)
    if mode == "preview":
        print("Preview mode: form filled, not submitted.", file=sys.stderr)


if __name__ == "__main__":
    main()
