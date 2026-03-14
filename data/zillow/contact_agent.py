"""Open a Zillow listing URL, open the contact agent form, fill it, optionally submit. Head-on by default."""
from dataclasses import dataclass
from typing import Optional

# Update these from the live Zillow listing page when you inspect the contact form.
CONTACT_BUTTON_SELECTOR = "[data-test='contact-agent-button'], button:has-text('Contact'), a:has-text('Contact Agent')"
FORM_NAME_SELECTOR = "input[name='name'], input[placeholder*='Name'], #name"
FORM_PHONE_SELECTOR = "input[name='phone'], input[type='tel'], input[placeholder*='Phone']"
FORM_EMAIL_SELECTOR = "input[name='email'], input[type='email'], input[placeholder*='Email']"
FORM_MESSAGE_SELECTOR = "textarea[name='message'], textarea[placeholder*='Message'], textarea"
FORM_SUBMIT_SELECTOR = "button[type='submit'], button:has-text('Contact Agent'), input[type='submit']"


@dataclass
class ContactFormData:
    name: str
    phone: str
    email: str
    message: str


def run_contact_flow(
    url: str,
    form_data: ContactFormData,
    *,
    headless: bool = False,
    submit: Optional[bool] = None,
) -> None:
    """
    Open url in a visible browser, click contact agent, fill the form.
    If submit is None, prompt the user (y/n). If True/False, skip prompt and submit or not.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_load_state("networkidle", timeout=15_000)

            page.click(CONTACT_BUTTON_SELECTOR, timeout=10_000)
            page.wait_for_selector(FORM_NAME_SELECTOR, timeout=10_000)

            page.fill(FORM_NAME_SELECTOR, form_data.name)
            page.fill(FORM_PHONE_SELECTOR, form_data.phone)
            page.fill(FORM_EMAIL_SELECTOR, form_data.email)
            page.fill(FORM_MESSAGE_SELECTOR, form_data.message)

            if submit is None:
                answer = input("Submit form? (y/n): ").strip().lower()
                submit = answer == "y" or answer == "yes"

            if submit:
                page.click(FORM_SUBMIT_SELECTOR, timeout=5_000)
            else:
                input("Form filled. Press Enter to close browser.")
        finally:
            browser.close()
