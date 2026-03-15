"""Resilient Playwright locators for Zillow inquiry CTA and contact form. Uses role/label/placeholder, not brittle CSS."""
import re
import logging
from typing import List, Optional

from playwright.sync_api import Locator, Page

LOG = logging.getLogger(__name__)

# CTA text patterns (order matters: try most specific first)
CTA_PATTERNS = [
    re.compile(r"contact\s+agent", re.I),
    re.compile(r"request\s+a\s+tour", re.I),
    re.compile(r"ask\s+a\s+question", re.I),
    re.compile(r"schedule\s+(a\s+)?tour", re.I),
    re.compile(r"contact\s+listing", re.I),
    re.compile(r"^contact$", re.I),
    re.compile(r"^tour$", re.I),
    re.compile(r"message\s+(agent|listing)?", re.I),
    re.compile(r"^message$", re.I),
    re.compile(r"reach\s+out", re.I),
]


def build_cta_locators(page: Page) -> List[Locator]:
    """Build a list of CTA locators (buttons and links) to try in order. Includes Zillow DOM fallbacks from listing pages."""
    locators: List[Locator] = []
    # Zillow listing detail: button that opens contact form (from inspect: data-cft-name="omp-v2-contact-button")
    locators.append(page.locator("button[data-cft-name='omp-v2-contact-button']").first)
    for pattern in CTA_PATTERNS:
        locators.append(page.get_by_role("button", name=pattern))
        locators.append(page.get_by_role("link", name=pattern))
    # Zillow DOM fallbacks
    locators.append(page.locator(".ds-agent-contact-button-container a, .ds-agent-contact-button-container button").first)
    locators.append(page.locator(".contact-button").first)
    return locators


def first_visible_locator(candidates: List[Locator], timeout_ms: int = 2000) -> Optional[Locator]:
    """Return the first candidate that becomes visible within timeout, or None."""
    for loc in candidates:
        try:
            loc.first.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except Exception:
            continue
    return None


def find_and_click_cta(page: Page, slow_mo_ms: int = 0) -> bool:
    """Find first visible CTA and click it. Scroll into view if possible; try click even if scroll fails."""
    import time
    candidates = build_cta_locators(page)
    loc = first_visible_locator(candidates, timeout_ms=2500)
    if not loc:
        return False
    try:
        loc.first.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    if slow_mo_ms:
        time.sleep(slow_mo_ms / 1000.0)
    try:
        loc.first.click(timeout=5000)
        LOG.info("CTA clicked (matched one of: contact agent, request tour, etc.)")
        return True
    except Exception as e:
        LOG.warning("CTA click failed: %s", e)
        return False


def get_form_root_candidates(page: Page) -> List[Locator]:
    """Return locators that might contain the inquiry form: dialog, then form, then main."""
    return [
        page.get_by_role("dialog"),
        page.locator("form").first,
        page.get_by_role("region", name=re.compile(r"contact|inquiry|message|lead", re.I)),
        page.locator("[role='dialog']").first,
    ]


def find_form_root(page: Page, wait_after_cta_ms: int = 1500) -> Optional[Locator]:
    """After CTA click, wait briefly then return first visible form container or None (use page as scope)."""
    import time
    time.sleep(wait_after_cta_ms / 1000.0)
    for loc in get_form_root_candidates(page):
        try:
            loc.first.wait_for(state="visible", timeout=2000)
            return loc
        except Exception:
            continue
    return None


def get_submit_button_candidates(page: Page, scope: Optional[Locator] = None) -> List[Locator]:
    """Build list of possible submit button locators. If scope given, search within it."""
    base = scope or page
    patterns = [
        re.compile(r"submit|send", re.I),
        re.compile(r"contact\s+agent", re.I),
        re.compile(r"request\s+tour", re.I),
        re.compile(r"send\s+message", re.I),
        re.compile(r"^submit$", re.I),
    ]
    locators: List[Locator] = []
    for p in patterns:
        locators.append(base.get_by_role("button", name=p))
    locators.append(base.locator("button[type='submit']").first)
    locators.append(base.locator("input[type='submit']").first)
    return locators


def find_submit_button(page: Page, scope: Optional[Locator] = None) -> Optional[Locator]:
    """Return first visible submit button within scope (or page)."""
    candidates = get_submit_button_candidates(page, scope)
    return first_visible_locator(candidates, timeout_ms=1500)
