"""
28car.com NINJA 400 Market Data Scraper
Fetches listing data for Kawasaki NINJA 400 from 28car.com
"""

import requests
import cloudscraper
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://m.28car.com/",
    "Connection": "keep-alive",
}

BASE_URL = "https://m.28car.com"
SEARCH_URLS = [
    f"{BASE_URL}/sell_ico.php?brand=KAWASAKI&model=NINJA+400",
    f"{BASE_URL}/sell_lst.php?brand=KAWASAKI&model=NINJA+400",
    f"{BASE_URL}/sell_ico.php?key=NINJA+400",
]


def fetch_with_cloudscraper(url: str) -> str | None:
    """Use cloudscraper to bypass Cloudflare protection."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    try:
        resp = scraper.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.text
        print(f"  Status {resp.status_code} for {url}")
    except Exception as e:
        print(f"  cloudscraper error: {e}")
    return None


def fetch_with_requests(url: str) -> str | None:
    """Standard requests fetch with browser-like headers."""
    session = requests.Session()
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.text
        print(f"  Status {resp.status_code} for {url}")
    except Exception as e:
        print(f"  requests error: {e}")
    return None


def extract_price(text: str) -> int | None:
    """Parse HK$ price string to integer."""
    text = text.replace(",", "").replace("$", "").replace("HK", "").strip()
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def parse_listing_page(html: str) -> list[dict]:
    """Parse a 28car listing page and extract NINJA 400 entries."""
    soup = BeautifulSoup(html, "lxml")
    listings = []

    # 28car mobile layout uses various card/row patterns
    for card in soup.select(".sell_car_item, .car_item, .list_item, article, .item"):
        try:
            title_el = card.select_one(".car_name, .title, h2, h3, .name")
            price_el = card.select_one(".price, .car_price, .sell_price")
            year_el = card.select_one(".year, .car_year")
            mileage_el = card.select_one(".mileage, .km, .car_km")
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else ""
            if "NINJA" not in title.upper() and "400" not in title:
                continue

            price_raw = price_el.get_text(strip=True) if price_el else ""
            price = extract_price(price_raw)

            year_raw = year_el.get_text(strip=True) if year_el else ""
            year_m = re.search(r"(20\d{2}|\d{4})", year_raw)
            year = int(year_m.group()) if year_m else None

            mileage_raw = mileage_el.get_text(strip=True) if mileage_el else ""
            km_m = re.search(r"[\d,]+", mileage_raw)
            mileage = int(km_m.group().replace(",", "")) if km_m else None

            href = link_el["href"] if link_el else ""
            url = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")

            listings.append(
                {
                    "title": title,
                    "price_hkd": price,
                    "year": year,
                    "mileage_km": mileage,
                    "url": url,
                    "source": "28car.com",
                    "fetched_at": datetime.now().isoformat(),
                }
            )
        except Exception:
            continue

    # Fallback: scan all text for price patterns near NINJA keywords
    if not listings:
        text_blocks = soup.find_all(string=re.compile(r"(?i)ninja\s*400"))
        for block in text_blocks:
            parent = block.parent
            context = parent.get_text(" ", strip=True) if parent else ""
            price_m = re.search(r"[\$＄HK]*\s*([\d,]{4,7})", context)
            price = extract_price(price_m.group(1)) if price_m else None
            year_m = re.search(r"(20\d{2})", context)
            year = int(year_m.group()) if year_m else None
            km_m = re.search(r"([\d,]+)\s*[Kk][Mm]", context)
            mileage = int(km_m.group(1).replace(",", "")) if km_m else None
            if price or year:
                listings.append(
                    {
                        "title": context[:80],
                        "price_hkd": price,
                        "year": year,
                        "mileage_km": mileage,
                        "url": "",
                        "source": "28car.com (text extract)",
                        "fetched_at": datetime.now().isoformat(),
                    }
                )

    return listings


def get_total_count(html: str) -> int | None:
    """Try to extract total result count from page."""
    patterns = [
        r"共\s*([\d,]+)\s*架",
        r"([\d,]+)\s*架",
        r"total[:\s]+([\d,]+)",
        r"results?[:\s]+([\d,]+)",
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def scrape_28car() -> dict:
    """Main scrape function. Returns dict with listings and metadata."""
    print("Attempting to scrape 28car.com for NINJA 400 listings...")
    all_listings = []
    total_count = None
    raw_html = None

    for url in SEARCH_URLS:
        print(f"  Trying: {url}")
        html = fetch_with_cloudscraper(url)
        if not html:
            html = fetch_with_requests(url)
        if html:
            raw_html = html
            count = get_total_count(html)
            if count:
                total_count = count
            found = parse_listing_page(html)
            all_listings.extend(found)
            print(f"  Found {len(found)} listings from {url}")
            time.sleep(1)

    return {
        "listings": all_listings,
        "total_count": total_count,
        "scraped_at": datetime.now().isoformat(),
        "source_url": BASE_URL,
        "success": len(all_listings) > 0 or raw_html is not None,
        "raw_available": raw_html is not None,
    }


if __name__ == "__main__":
    result = scrape_28car()
    print(json.dumps(result, ensure_ascii=False, indent=2))
