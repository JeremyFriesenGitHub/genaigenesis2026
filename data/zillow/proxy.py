"""Fetch and rotate free HTTPS proxies for Playwright sessions."""
import random
import requests

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=us&ssl=yes&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
]

_proxy_list: list[str] = []


def _fetch_proxies() -> list[str]:
    """Fetch proxy list from free sources."""
    proxies = []
    for url in PROXY_SOURCES:
        try:
            resp = requests.get(url, timeout=10)
            if resp.ok:
                for line in resp.text.strip().splitlines():
                    line = line.strip()
                    if line and ":" in line:
                        proxies.append(line)
        except Exception:
            continue
    return list(set(proxies))


def get_proxy() -> str | None:
    """Return a random proxy in host:port format, fetching list if needed."""
    global _proxy_list
    if not _proxy_list:
        _proxy_list = _fetch_proxies()
        if _proxy_list:
            random.shuffle(_proxy_list)
            print(f"[proxy] Loaded {len(_proxy_list)} proxies")
    if not _proxy_list:
        print("[proxy] No proxies available, using direct connection")
        return None
    return _proxy_list.pop()


def proxy_for_playwright() -> dict | None:
    """Return a proxy dict for Playwright browser.new_context(), or None."""
    addr = get_proxy()
    if not addr:
        return None
    return {"server": f"http://{addr}"}
