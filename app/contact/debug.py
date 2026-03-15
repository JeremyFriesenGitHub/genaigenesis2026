"""Save debug artifacts (screenshot, HTML, trace) on failure."""
import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page

LOG = logging.getLogger(__name__)
DEBUG_DIR = Path("data/output/contact_debug")


def ensure_debug_dir() -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return DEBUG_DIR


def save_screenshot(page: Page, name: str = "failure") -> Path:
    """Save a PNG screenshot. Returns path to file."""
    d = ensure_debug_dir()
    path = d / f"{name}.png"
    page.screenshot(path=path)
    LOG.info("Saved screenshot: %s", path)
    return path


def save_html(page: Page, name: str = "failure") -> Path:
    """Save current page HTML. Returns path to file."""
    d = ensure_debug_dir()
    path = d / f"{name}.html"
    path.write_text(page.content(), encoding="utf-8")
    LOG.info("Saved HTML: %s", path)
    return path


def save_artifacts(page: Page, prefix: str = "failure") -> dict:
    """Save screenshot and HTML. Returns dict of saved paths."""
    ensure_debug_dir()
    return {
        "screenshot": str(save_screenshot(page, prefix)),
        "html": str(save_html(page, prefix)),
    }
