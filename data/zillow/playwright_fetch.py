"""Fetch Zillow pages via ScraperAPI (handles proxies, CAPTCHAs, rendering)."""
import os
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")
SCRAPER_API_URL = "https://api.scraperapi.com"
MAX_RETRIES = 3


def fetch_html(
    url: str,
    *,
    headless: bool = False,
    wait_selector: Optional[str] = None,
    wait_timeout_ms: int = 25_000,
    pause_for_captcha: bool = True,
) -> Optional[str]:
    if not SCRAPER_API_KEY:
        print("[fetch] No SCRAPER_API_KEY set — get one at https://www.scraperapi.com")
        print("[fetch] Then: export SCRAPER_API_KEY='your_key'")
        return None

    params = {
        "api_key": SCRAPER_API_KEY,
        "url": url,
        "render": "true",
        "country_code": "us",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[fetch] ScraperAPI attempt {attempt}/{MAX_RETRIES}: {url}")
        try:
            resp = requests.get(SCRAPER_API_URL, params=params, timeout=70)
            if resp.status_code == 200:
                print(f"[fetch] Success ({len(resp.text)} chars)")
                return resp.text
            print(f"[fetch] Status {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            print(f"[fetch] Request error: {e}")

    print("[fetch] All ScraperAPI attempts failed")
    return None
