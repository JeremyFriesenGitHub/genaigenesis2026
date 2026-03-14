"""Parse Zillow search page: structured data first (embedded JSON), then HTML fallback."""
import json
from bs4 import BeautifulSoup

# Normalized listing shape: same keys every time, missing = ""
LISTING_KEYS = ("title", "price", "address", "beds", "baths", "sqft", "url", "image", "source")


def normalize_listing(raw: dict) -> dict:
    """One place: clean any listing dict into a consistent shape. Missing fields = ""."""
    url = (raw.get("url") or "").strip()
    if url and not url.startswith("http"):
        url = f"https://www.zillow.com{url}" if url.startswith("/") else f"https://www.zillow.com/{url}"
    return {
        "title": str(raw.get("title") or "").strip(),
        "price": str(raw.get("price") or "").strip(),
        "address": str(raw.get("address") or "").strip(),
        "beds": str(raw.get("beds") or "").strip(),
        "baths": str(raw.get("baths") or "").strip(),
        "sqft": str(raw.get("sqft") or "").strip(),
        "url": url,
        "image": str(raw.get("image") or "").strip(),
        "source": "zillow",
    }


def _listing_id_from_url(url: str) -> str:
    """Last path segment (e.g. /ChWHPZ/ -> ChWHPZ) for dedupe."""
    if not url:
        return ""
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else ""


def dedupe_listings_by_url(listings: list[dict]) -> list[dict]:
    """Dedupe by URL; prefer first occurrence. Optionally by listing ID from URL."""
    seen_url: set[str] = set()
    seen_id: set[str] = set()
    out = []
    for r in listings:
        url = (r.get("url") or "").strip()
        if not url:
            out.append(r)
            continue
        if url in seen_url:
            continue
        lid = _listing_id_from_url(url)
        if lid and lid in seen_id:
            continue
        seen_url.add(url)
        if lid:
            seen_id.add(lid)
        out.append(r)
    return out


def dedupe_links(links: list[str]) -> list[str]:
    """Dedupe by full URL and by listing ID (last path segment)."""
    seen_url: set[str] = set()
    seen_id: set[str] = set()
    out = []
    for u in links:
        u = (u or "").strip()
        if not u:
            continue
        if u in seen_url:
            continue
        lid = _listing_id_from_url(u)
        if lid and lid in seen_id:
            continue
        seen_url.add(u)
        if lid:
            seen_id.add(lid)
        out.append(u)
    return out


def _listings_from_json(html: str) -> list[dict]:
    """Try to get listings from embedded script JSON. Returns [] on failure."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script[data-zrr-shared-data-key]")
    if not script or not script.contents:
        return []
    try:
        data = json.loads(script.contents[0].strip("!<>-"))
        rows = data["cat1"]["searchResults"]["listResults"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    out = []
    for r in rows:
        detail_url = r.get("detailUrl") or ""
        if not detail_url:
            continue
        if "http" not in detail_url:
            detail_url = f"https://www.zillow.com{detail_url}"
        # Map common Zillow JSON fields to our shape
        vd = r.get("variableData")
        price_text = (vd.get("text") if isinstance(vd, dict) else None) if vd else None
        raw = {
            "title": r.get("address") or r.get("statusText") or "",
            "price": r.get("price") or price_text or r.get("unformattedPrice") or "",
            "address": r.get("address") or "",
            "beds": r.get("beds") or "",
            "baths": r.get("baths") or "",
            "sqft": r.get("area") or r.get("sqft") or "",
            "url": detail_url,
            "image": r.get("imgSrc") or r.get("image") or "",
        }
        out.append(normalize_listing(raw))
    return out


def _text(el) -> str:
    return el.get_text(strip=True) if el else ""


def _listings_from_html(html: str) -> list[dict]:
    """Fallback: parse visible <article> cards."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select("article"):
        link_el = card.select_one("a")
        url = (link_el.get("href") or "").strip() if link_el else ""
        raw = {
            "title": (card.select_one("img") or {}).get("alt", "").strip() if card.select_one("img") else "",
            "price": _text(card.select_one('[data-test="property-card-price"]')),
            "address": _text(card.select_one('[data-test="property-card-addr"]')),
            "beds": _text(card.select_one("ul li:nth-of-type(1)")),
            "baths": _text(card.select_one("ul li:nth-of-type(2)")),
            "sqft": _text(card.select_one("ul li:nth-of-type(3)")),
            "url": url,
            "image": (card.select_one("img") or {}).get("src", "").strip() if card.select_one("img") else "",
        }
        out.append(normalize_listing(raw))
    return out


def parse_listings(html: str) -> list[dict]:
    """Structured data first, then HTML fallback. All listings normalized and deduped."""
    listings = _listings_from_json(html)
    if not listings:
        listings = _listings_from_html(html)
    return dedupe_listings_by_url(listings)


def listing_links_from_html(html: str) -> list[str]:
    """Extract listing URLs from embedded JSON, else from parsed listings."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script[data-zrr-shared-data-key]")
    if script and script.contents:
        try:
            data = json.loads(script.contents[0].strip("!<>-"))
            rows = data["cat1"]["searchResults"]["listResults"]
            links = []
            for r in rows:
                u = r.get("detailUrl") or ""
                if not u:
                    continue
                links.append(f"https://www.zillow.com{u}" if "http" not in u else u)
            return dedupe_links(links)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return []
