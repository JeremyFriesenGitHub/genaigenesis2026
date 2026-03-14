# Zillow scraper: what it does and how

Run `python -m data.zillow.run`. A browser opens, hits a Zillow search URL, and you get raw HTML plus one JSON file with listings. This doc tracks how that works so you can fix or extend it.

---

## Command → output

You run:

```bash
python -m data.zillow.run
```

`run.py` sets a criteria dict (location, rent/buy, price, beds), calls `search(criteria)`, then writes:

- **`data/output/zillow_raw.html`** – full page HTML (handy when parsing breaks).
- **`data/output/zillow.json`** – criteria, search_url, listing_count, listings, listing_links in one place.

---

## Criteria and URL

Criteria live in `run.py` (or you pass them in). Example:

```python
criteria = {
    "location": "New York NY",
    "intent": "rent",
    "price_max": 3000,
    "beds_min": 1,
}
```

`build_search_url(criteria)` in `scraper.py` turns that into a Zillow URL: slug the location, plug into `https://www.zillow.com/homes/for_{intent}/{slug}/?price_max=...&beds_min=...`. No discovery—we build the URL from the dict.

---

## Fetch: Playwright

`fetch_html(url)` in `playwright_fetch.py`:

1. Launches Chromium (visible window by default).
2. Goes to the URL.
3. Waits for content (script tag, articles, or price cards) up to ~25s.
4. If it times out, you often have a CAPTCHA—script prompts you to solve it and press Enter.
5. Returns `page.content()` (full HTML), then closes the browser.

Using a real browser keeps Zillow happier than a bare HTTP client.

---

## Parse: JSON first, then HTML

All parsing is in `parse.py`.

**Step 1 – Embedded JSON**  
Look for `<script data-zrr-shared-data-key="...">`, parse the JSON, read `cat1.searchResults.listResults`. Map each item to our standard listing shape. This path is more stable when Zillow changes layout.

**Step 2 – HTML fallback**  
If the script tag is missing or JSON fails, scrape `<article>` cards with BeautifulSoup (title, price, address, beds, baths, sqft, link, image).

**Step 3 – Normalize**  
Every listing goes through `normalize_listing()` so we always get the same keys: `title`, `price`, `address`, `beds`, `baths`, `sqft`, `url`, `image`, `source: "zillow"`. Missing fields become `""`.

**Step 4 – Dedupe**  
Listings by URL and by listing ID (last path segment of the URL). Links get deduped too.

---

## What `search()` returns

```python
{
    "listings": [ {...}, ... ],      # normalized, deduped
    "listing_links": [ "https://...", ... ],
    "raw_html": "<!DOCTYPE html>...",
    "search_url": "https://www.zillow.com/..."
}
```

`run.py` takes that, writes raw_html to `zillow_raw.html`, and writes a single JSON with criteria, search_url, listing_count, listings, and listing_links to `zillow.json`.

---

## Flow in one go

```
python -m data.zillow.run
  → run.main(): criteria dict
  → search(criteria)
      → build_search_url(criteria) → url
      → fetch_html(url) → Playwright, load page, maybe CAPTCHA → raw_html
      → parse_listings(raw_html): JSON first, else HTML → normalize → dedupe
      → listing_links_from_html + dedupe_links
  → write raw_html → zillow_raw.html
  → write { criteria, search_url, listing_count, listings, listing_links } → zillow.json
```

Files: `scraper.py` (URL + orchestration), `playwright_fetch.py` (browser), `parse.py` (JSON + HTML + normalize + dedupe), `run.py` (entry + disk).
