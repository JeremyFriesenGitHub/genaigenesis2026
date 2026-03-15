"""Fill contact form fields with visible character-by-character typing for demo effect."""
import re
import logging
import time
from typing import Optional

from playwright.sync_api import Locator, Page

LOG = logging.getLogger(__name__)

TYPING_DELAY_MS = 60
PAUSE_BETWEEN_FIELDS_S = 1.0


def _scope(page: Page, scope: Optional[Locator]) -> Locator:
    return scope if scope is not None else page


def _try_fill(loc: Locator, value: str, slow_mo_ms: int = 0) -> bool:
    """Click the field, clear it, then type character by character."""
    if not value:
        return False
    try:
        loc.first.wait_for(state="visible", timeout=3000)
        loc.first.scroll_into_view_if_needed(timeout=2000)
        time.sleep(0.3)
        loc.first.click()
        time.sleep(0.2)
        loc.first.fill("")
        delay = slow_mo_ms if slow_mo_ms else TYPING_DELAY_MS
        loc.first.type(value, delay=delay)
        time.sleep(0.3)
        return True
    except Exception:
        return False


def fill_name(page: Page, value: str, scope: Optional[Locator] = None, slow_mo_ms: int = 0) -> bool:
    base = _scope(page, scope)
    candidates = [
        base.get_by_label(re.compile(r"name|full\s*name|your\s*name", re.I)),
        base.get_by_placeholder(re.compile(r"name|full\s*name", re.I)),
        base.locator("input[type='text']").first,
        base.get_by_role("textbox", name=re.compile(r"name", re.I)),
    ]
    for loc in candidates:
        if _try_fill(loc, value, slow_mo_ms):
            LOG.info("Filled name")
            return True
    return False


def fill_email(page: Page, value: str, scope: Optional[Locator] = None, slow_mo_ms: int = 0) -> bool:
    base = _scope(page, scope)
    candidates = [
        base.get_by_label(re.compile(r"email|e-?mail", re.I)),
        base.get_by_placeholder(re.compile(r"email|e-?mail", re.I)),
        base.locator("input[type='email']").first,
        base.get_by_role("textbox", name=re.compile(r"email", re.I)),
    ]
    for loc in candidates:
        if _try_fill(loc, value, slow_mo_ms):
            LOG.info("Filled email")
            return True
    return False


def fill_phone(page: Page, value: str, scope: Optional[Locator] = None, slow_mo_ms: int = 0) -> bool:
    base = _scope(page, scope)
    candidates = [
        base.get_by_label(re.compile(r"phone|tel|mobile", re.I)),
        base.get_by_placeholder(re.compile(r"phone|tel|number", re.I)),
        base.locator("input[type='tel']").first,
        base.get_by_role("textbox", name=re.compile(r"phone|tel", re.I)),
    ]
    for loc in candidates:
        if _try_fill(loc, value, slow_mo_ms):
            LOG.info("Filled phone")
            return True
    return False


def fill_message(page: Page, value: str, scope: Optional[Locator] = None, slow_mo_ms: int = 0) -> bool:
    base = _scope(page, scope)
    candidates = [
        base.get_by_label(re.compile(r"message|comment|inquiry|how\s+can", re.I)),
        base.get_by_placeholder(re.compile(r"message|comment|tell\s+us|write", re.I)),
        base.get_by_role("textbox", name=re.compile(r"message|comment", re.I)),
        base.locator("textarea").first,
    ]
    for loc in candidates:
        if _try_fill(loc, value, slow_mo_ms):
            LOG.info("Filled message")
            return True
    return False


def fill_all(
    page: Page,
    name: str,
    email: str,
    phone: str,
    message: str,
    scope: Optional[Locator] = None,
    slow_mo_ms: int = TYPING_DELAY_MS,
    pause_between: float = PAUSE_BETWEEN_FIELDS_S,
) -> dict:
    """Fill name, email, phone, message with visible typing and pauses between fields."""
    results = {}
    for label, func, value in [
        ("name", fill_name, name),
        ("phone", fill_phone, phone),
        ("email", fill_email, email),
        ("message", fill_message, message),
    ]:
        results[label] = func(page, value, scope, slow_mo_ms)
        if results[label]:
            time.sleep(pause_between)
    return results
