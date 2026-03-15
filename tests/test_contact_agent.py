"""
Test: contact agent flow on a real Zillow listing.
Runs in preview mode (fills form, does NOT submit).

Run:  python -m pytest tests/test_contact_agent.py -v -s
"""
import logging

logging.basicConfig(level=logging.INFO)


def test_contact_flow_preview():
    from app.contact import Lead, run_contact_flow

    listing_url = "https://www.zillow.com/homedetails/59-Braywin-Dr-Toronto-ON-M9P-2P2/2077138476_zpid/"

    lead = Lead(
        name="Maya Chen",
        email="maya@personaplex.ai",
        phone="+18252035213",
        message="Hi, I'm interested in a 2-bedroom unit. Are pets allowed? I have a small dog. When is the earliest move-in date?",
    )

    print(f"\n=== CONTACT AGENT TEST ===")
    print(f"  Listing: {listing_url}")
    print(f"  Lead: {lead.name} / {lead.email}")
    print(f"  Mode: preview (fill only, no submit)\n")

    result = run_contact_flow(
        listing_url,
        lead,
        mode="preview",
        headless=False,
        slow_mo_ms=150,
        beds_min=2,
    )

    print(f"\n=== RESULT ===")
    print(f"  CTA found:     {result.cta_found}")
    print(f"  Form found:    {result.form_found}")
    print(f"  Fields filled: {result.fields_filled}")
    print(f"  Submit found:  {result.submit_button_found}")
    print(f"  Submitted:     {result.submitted}")
    if result.error:
        print(f"  Error:         {result.error}")

    assert result.cta_found, f"CTA not found: {result.error}"
