"""Fill contact form fields using ranked fallback strategies (label, placeholder, type, etc.)."""
import re
import logging
from typing import Optional

from playwright.sync_api import Locator, Page

LOG = logging.getLogger(__name__)


def _scope(page: Page, scope: Optional[Locator]) -> Locator:
    return scope if scope is not None else page


def _try_fill(loc: Locator, value: str, slow_mo_ms: int = 0) -> bool:
    if not value:
        return False
    try:
        loc.first.wait_for(state="visible", timeout=2000)
        loc.first.fill(value)
        if slow_mo_ms:
            import time
            time.sleep(slow_mo_ms / 1000.0)
        return True
    except Exception:
        return False


def fill_name(page: Page, value: str, scope: Optional[Locator] = None, slow_mo_ms: int = 0) -> bool:
    """Try getByLabel, getByPlaceholder, then generic text input for name."""
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
    """Try getByLabel, getByPlaceholder, then input[type=email]."""
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
    """Try getByLabel, getByPlaceholder, then input[type=tel]."""
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
    """Try getByLabel, getByPlaceholder, then textarea."""
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
    slow_mo_ms: int = 80,
) -> dict:
    """Fill name, email, phone, message. Returns dict of field -> filled (bool)."""
    return {
        "name": fill_name(page, name, scope, slow_mo_ms),
        "email": fill_email(page, email, scope, slow_mo_ms),
        "phone": fill_phone(page, phone, scope, slow_mo_ms),
        "message": fill_message(page, message, scope, slow_mo_ms),
    }
