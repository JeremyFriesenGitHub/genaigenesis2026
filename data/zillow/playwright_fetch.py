"""Fetch Zillow pages via Playwright (avoids CAPTCHA when used in a real browser)."""
from typing import Optional


def fetch_html(
    url: str,
    *,
    headless: bool = False,
    wait_selector: Optional[str] = None,
    wait_timeout_ms: int = 25_000,
    pause_for_captcha: bool = True,
) -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=wait_timeout_ms)
                except Exception:
                    if pause_for_captcha:
                        input("\n>>> Solve CAPTCHA in browser, then press Enter...")
            return page.content()
        finally:
            browser.close()
    return None
