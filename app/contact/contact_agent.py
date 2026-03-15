"""Zillow contact-agent flow: open listing, click inquiry CTA, fill form, optional submit. Demo-first, preview by default."""
import logging
import os
import re
import time

from dotenv import load_dotenv
load_dotenv()
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page, sync_playwright
from playwright_stealth import Stealth

from .debug import save_artifacts
from .fill_form import fill_all
from .locators import find_form_root, find_submit_button, find_and_click_cta

LOG = logging.getLogger(__name__)

DEFAULT_SLOW_MO_MS = 150
PAGE_STABILITY_WAIT_S = 3
WAIT_AFTER_CTA_MS = 2000
PAUSE_BETWEEN_FIELDS_S = 1.0

SCRAPERAPI_PROXY_HOST = "proxy-server.scraperapi.com"
SCRAPERAPI_PROXY_PORT = 8001


@dataclass
class Lead:
    name: str = "Maya Chen"
    email: str = "maya@personaplex.ai"
    phone: str = "+18252035213"
    message: str = "Hi, I'm interested in this property. When can I schedule a viewing?"


@dataclass
class ContactResult:
    cta_found: bool
    form_found: bool
    fields_filled: dict = field(default_factory=dict)
    submit_button_found: bool = False
    submitted: bool = False
    error: Optional[str] = None
    debug_artifacts: dict = field(default_factory=dict)


def _dismiss_captcha_overlay(page: Page, max_wait_s: int = 10) -> None:
    """Wait for PerimeterX CAPTCHA modal iframe to disappear, or remove it via JS."""
    captcha = page.locator("#px-captcha-modal, #px-captcha-wrapper, .px-captcha-container")
    try:
        if not captcha.first.is_visible(timeout=2000):
            return
    except Exception:
        return
    LOG.info("CAPTCHA overlay detected, waiting for it to clear...")
    try:
        captcha.first.wait_for(state="hidden", timeout=max_wait_s * 1000)
        LOG.info("CAPTCHA overlay cleared on its own")
        return
    except Exception:
        pass
    LOG.info("CAPTCHA overlay still present, removing via JS")
    page.evaluate("""() => {
        for (const sel of ['#px-captcha-modal', '#px-captcha-wrapper', '.px-captcha-container']) {
            document.querySelectorAll(sel).forEach(el => el.remove());
        }
    }""")
    time.sleep(0.5)


def _dismiss_overlays(page: Page, timeout_ms: int = 1500) -> None:
    """Try to close common popups (e.g. sign-in prompt) so they don't block the CTA."""
    _dismiss_captcha_overlay(page)
    close_selectors = [
        page.get_by_role("button", name=re.compile(r"close|dismiss|no\s+thanks", re.I)),
        page.locator("[aria-label='Close']").first,
    ]
    for loc in close_selectors:
        try:
            loc.first.click(timeout=timeout_ms)
            time.sleep(0.3)
        except Exception:
            pass


def _build_proxy_config() -> dict | None:
    """Build ScraperAPI proxy config if SCRAPER_API_KEY is set."""
    api_key = os.environ.get("SCRAPER_API_KEY", "")
    if not api_key:
        return None
    return {
        "server": f"http://{SCRAPERAPI_PROXY_HOST}:{SCRAPERAPI_PROXY_PORT}",
        "username": "scraperapi.country_code=us",
        "password": api_key,
    }


def run_contact_flow(
    listing_url: str,
    lead: Lead,
    mode: str = "preview",
    *,
    headless: bool = False,
    slow_mo_ms: int = DEFAULT_SLOW_MO_MS,
    use_proxy: bool = True,
) -> ContactResult:
    """
    Open listing URL, click inquiry CTA, fill form. If mode == "preview" (default), do not submit.
    If use_proxy=True and SCRAPER_API_KEY is set, routes traffic through ScraperAPI's rotating
    proxies to avoid IP bans. Playwright still controls the browser visually.
    """
    result = ContactResult(cta_found=False, form_found=False, fields_filled={})
    if mode not in ("preview", "submit"):
        result.error = f"Invalid mode: {mode}"
        return result

    proxy = _build_proxy_config() if use_proxy else None
    if proxy:
        LOG.info("Using ScraperAPI proxy for IP rotation")
    else:
        LOG.info("Running without proxy (set SCRAPER_API_KEY to enable)")

    stealth = Stealth()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo_ms, proxy=proxy)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True if proxy else False,
        )
        page = context.new_page()
        stealth.apply_stealth_sync(page)
        try:
            LOG.info("Opening listing: %s", listing_url)
            page.goto(listing_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_load_state("load", timeout=15_000)
            except Exception:
                LOG.warning("Page load event timed out; continuing (e.g. CAPTCHA may be shown)")
            time.sleep(PAGE_STABILITY_WAIT_S)
            _dismiss_overlays(page)

            LOG.info("Searching for inquiry CTA...")
            if not find_and_click_cta(page, slow_mo_ms=slow_mo_ms):
                LOG.warning("No CTA found")
                result.debug_artifacts = save_artifacts(page, "cta_not_found")
                result.error = "CTA not found"
                return result
            result.cta_found = True

            form_root = find_form_root(page, wait_after_cta_ms=WAIT_AFTER_CTA_MS)
            if form_root:
                result.form_found = True
                LOG.info("Form area detected")
            else:
                LOG.info("No specific form container; filling in page scope")

            result.fields_filled = fill_all(
                page,
                lead.name,
                lead.email,
                lead.phone,
                lead.message,
                scope=form_root,
                slow_mo_ms=slow_mo_ms,
            )

            submit_btn = find_submit_button(page, scope=form_root)
            result.submit_button_found = submit_btn is not None
            if submit_btn:
                LOG.info("Submit button found")
                if mode == "preview":
                    LOG.info("Preview complete. Form filled, not submitted.")
                    return result
                try:
                    submit_btn.first.scroll_into_view_if_needed(timeout=2000)
                    if slow_mo_ms:
                        time.sleep(slow_mo_ms / 1000.0)
                    submit_btn.first.click(timeout=5000)
                    result.submitted = True
                    LOG.info("Form submitted")
                except Exception as e:
                    result.error = str(e)
                    save_artifacts(page, "submit_failed")
            else:
                if mode == "submit":
                    result.error = "Submit button not found"
                    save_artifacts(page, "submit_not_found")
                else:
                    LOG.info("Preview complete. Form filled, submit button not found (not submitted).")

            return result
        except Exception as e:
            LOG.exception("Contact flow failed")
            result.error = str(e)
            if page:
                try:
                    result.debug_artifacts = save_artifacts(page, "failure")
                except Exception:
                    pass
            return result
        finally:
            context.close()
            browser.close()
