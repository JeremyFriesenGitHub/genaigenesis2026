"""Fetch Zillow pages via Playwright with stealth and rotating proxies."""
import time
from typing import Optional

from .proxy import proxy_for_playwright

MAX_RETRIES = 10


def _has_captcha(page) -> bool:
    """Check if a PerimeterX CAPTCHA overlay is present."""
    captcha = page.locator("#px-captcha-modal, #px-captcha-wrapper, .px-captcha-container")
    try:
        return captcha.first.is_visible(timeout=2000)
    except Exception:
        return False


def _dismiss_captcha_overlay(page) -> None:
    """Remove PerimeterX CAPTCHA overlay if present."""
    if not _has_captcha(page):
        return
    try:
        page.locator("#px-captcha-modal, #px-captcha-wrapper, .px-captcha-container").first.wait_for(
            state="hidden", timeout=10_000
        )
        return
    except Exception:
        pass
    page.evaluate("""() => {
        for (const sel of ['#px-captcha-modal', '#px-captcha-wrapper', '.px-captcha-container']) {
            document.querySelectorAll(sel).forEach(el => el.remove());
        }
    }""")
    time.sleep(0.5)


def _attempt_fetch(
    url: str,
    *,
    headless: bool,
    wait_selector: Optional[str],
    wait_timeout_ms: int,
    proxy: Optional[dict],
) -> Optional[str]:
    """Single fetch attempt with a given proxy. Returns HTML or None on failure."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    stealth = Stealth()
    proxy_label = proxy["server"] if proxy else "direct"
    print(f"[fetch] Trying {proxy_label}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, proxy=proxy)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        stealth.apply_stealth_sync(page)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(1)
            _dismiss_captcha_overlay(page)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=wait_timeout_ms)
            if _has_captcha(page):
                print(f"[fetch] CAPTCHA detected with {proxy_label}, rotating...")
                return None
            return page.content()
        except Exception as e:
            print(f"[fetch] Failed with {proxy_label}: {e}")
            return None
        finally:
            context.close()
            browser.close()


def fetch_html(
    url: str,
    *,
    headless: bool = False,
    wait_selector: Optional[str] = None,
    wait_timeout_ms: int = 25_000,
    pause_for_captcha: bool = True,
) -> Optional[str]:
    # Try with rotating proxies first
    for attempt in range(1, MAX_RETRIES + 1):
        proxy = proxy_for_playwright()
        print(f"[fetch] Attempt {attempt}/{MAX_RETRIES}")
        html = _attempt_fetch(
            url,
            headless=headless,
            wait_selector=wait_selector,
            wait_timeout_ms=wait_timeout_ms,
            proxy=proxy,
        )
        if html:
            return html

    # All proxy attempts failed — fall back to direct connection with manual CAPTCHA
    print("[fetch] All proxy attempts failed, trying direct connection...")
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    stealth = Stealth()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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
