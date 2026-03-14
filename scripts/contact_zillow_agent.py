"""
Open a Zillow listing URL and run the contact-agent flow (headed browser).
Backend passes the URL and form fields; user is prompted to submit or not.
Usage: python scripts/contact_zillow_agent.py --url <listing_url> --name "..." --phone "..." --email "..." --message "..."
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.zillow.contact_agent import ContactFormData, run_contact_flow


def main():
    p = argparse.ArgumentParser(description="Open Zillow listing, fill contact form, optionally submit.")
    p.add_argument("--url", required=True, help="Zillow listing URL")
    p.add_argument("--name", required=True)
    p.add_argument("--phone", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--message", default="", help="Message body")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--submit", action="store_true", help="Submit form without prompting")
    p.add_argument("--no-submit", action="store_true", help="Do not submit; just fill and prompt")
    args = p.parse_args()

    submit = None
    if args.submit:
        submit = True
    if args.no_submit:
        submit = False

    form = ContactFormData(name=args.name, phone=args.phone, email=args.email, message=args.message)
    run_contact_flow(args.url, form, headless=args.headless, submit=submit)


if __name__ == "__main__":
    main()
