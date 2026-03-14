"""Fetch Zillow pages via Playwright."""
from typing import Optional


def fetch_html(
    url: str,
    *,
    headless: bool = False,
    wait_selector: Optional[str] = None,
    wait_timeout_ms: int = 25_000,
    pause_for_captcha: bool = True,
) -> Optional[str]:
    from playwright.sync_api import sync_playwright

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
                        input("\nSolve CAPTCHA in browser, then press Enter...")
            return page.content()
        finally:
            browser.close()
