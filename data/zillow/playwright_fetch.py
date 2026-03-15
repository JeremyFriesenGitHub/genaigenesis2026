"""Fetch Zillow pages via Playwright with stealth to bypass bot detection."""
import time
from typing import Optional


def _dismiss_captcha_overlay(page) -> None:
    """Remove PerimeterX CAPTCHA overlay if present."""
    captcha = page.locator("#px-captcha-modal, #px-captcha-wrapper, .px-captcha-container")
    try:
        if not captcha.first.is_visible(timeout=2000):
            return
    except Exception:
        return
    try:
        captcha.first.wait_for(state="hidden", timeout=10_000)
        return
    except Exception:
        pass
    page.evaluate("""() => {
        for (const sel of ['#px-captcha-modal', '#px-captcha-wrapper', '.px-captcha-container']) {
            document.querySelectorAll(sel).forEach(el => el.remove());
        }
    }""")
    time.sleep(0.5)


def fetch_html(
    url: str,
    *,
    headless: bool = False,
    wait_selector: Optional[str] = None,
    wait_timeout_ms: int = 25_000,
    pause_for_captcha: bool = True,
) -> Optional[str]:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    stealth = Stealth()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        stealth.apply_stealth_sync(page)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(1)
            _dismiss_captcha_overlay(page)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=wait_timeout_ms)
                except Exception:
                    if pause_for_captcha:
                        input("\nSolve CAPTCHA in browser, then press Enter...")
            return page.content()
        finally:
            context.close()
            browser.close()
