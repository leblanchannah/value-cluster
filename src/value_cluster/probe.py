"""Check what Sephora Canada returns to this machine before running a full scrape.

Run from the repo root:

    uv run python -m value_cluster.probe              # plain HTTP requests only
    uv run python -m value_cluster.probe --selenium   # also try headless Chrome
    uv run python -m value_cluster.probe --selenium-only --headed   # Chrome only, visible window

It makes a handful of requests (a few seconds apart), prints a summary to paste
back into the Claude session, and saves the responses (gzipped) under
data/probe/ (ignored by git) so parsers and tests can be built from real data.

What it checks:
- requests: brands list and product pages, looking for product JSON embedded in the HTML
- selenium: brands list, one brand page's product links, and product pages
  loaded in Chrome, looking for the same embedded product JSON
"""

import argparse
import gzip
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from value_cluster.sephora import find_product, iter_dicts, parse_brand_products, parse_brands

BASE_URL = "https://www.sephora.com"
LOCALE_PATH = "/ca/en"
# Products that exist in the January 2025 snapshot (data/preprocessed_data.csv).
SAMPLE_PRODUCTS = ["P513304", "P427517"]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}
# Sephora picks the country from the IP unless these are set.
LOCALE_COOKIES = {"site_locale": "ca", "site_language": "en"}
DELAY_SECONDS = 4
# data/probe/ in the repo (ignored by git), whatever directory the probe is run from.
# Copy a file into tests/fixtures/sephora/ only when it is needed for a test.
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "probe"
SAMPLE_BRAND = "/brand/benefit-cosmetics"


def save(name: str, content: bytes) -> Path:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"{name}.gz"
    path.write_bytes(gzip.compress(content))
    return path


def describe(label: str, response: requests.Response) -> None:
    print(f"\n== {label}")
    print(f"url:          {response.url}")
    print(f"status:       {response.status_code}")
    print(f"server:       {response.headers.get('server')}")
    print(f"content-type: {response.headers.get('content-type')}")
    print(f"bytes:        {len(response.content)}")
    cookies = {k: v for k, v in response.cookies.items() if "country" in k or "locale" in k}
    if cookies:
        print(f"cookies:      {cookies}")


def report_embedded_json(html: str) -> dict | None:
    """Print the JSON <script> tags in a page and return the linkStore data if present."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": lambda t: bool(t) and "json" in t})
    print(f"json scripts: {[(tag.get('id'), len(tag.get_text())) for tag in scripts]}")
    link_store = soup.find("script", id="linkStore")
    if link_store is None:
        return None
    try:
        return json.loads(link_store.get_text())
    except ValueError:
        print("linkStore:    present but not valid JSON")
        return None


def report_product(data: dict) -> None:
    """Print the fields the scraper needs from product data (API or embedded JSON)."""
    sku = data.get("currentSku", {})
    print(f"display name: {data.get('productDetails', {}).get('displayName')}")
    print(f"list price:   {sku.get('listPrice')}  size: {sku.get('size')}")
    print(f"child skus:   {len(data.get('regularChildSkus', []))}")


def probe_requests() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(LOCALE_COOKIES)

    brands = session.get(f"{BASE_URL}{LOCALE_PATH}/brands-list", timeout=30)
    describe("brands list (requests)", brands)
    if brands.ok:
        link_store = report_embedded_json(brands.text)
        print(f"linkStore:    {'found' if link_store else 'not found'}")
        print(f"brands found: {len(parse_brands(brands.text))}")
        print(f"saved:        {save('brands_list.html', brands.content)}")

    # A brand page, and its second page, to see how products and paging are listed.
    for suffix, name in [("", "brand_page"), ("?currentPage=2", "brand_page_2")]:
        time.sleep(DELAY_SECONDS)
        response = session.get(f"{BASE_URL}{LOCALE_PATH}{SAMPLE_BRAND}{suffix}", timeout=30)
        describe(f"brand page{suffix} (requests)", response)
        if not response.ok:
            print(f"body start:   {response.text[:200]!r}")
            continue
        print(f"saved:        {save(f'{name}.html', response.content)}")
        link_store = report_embedded_json(response.text)
        products = parse_brand_products(response.text)
        print(f"products found: {len(products)}")
        for product in products[:3]:
            print(f"  {product}")
        counts = {
            key: value
            for item in iter_dicts(link_store)
            for key, value in item.items()
            if "total" in key.lower() and isinstance(value, int)
        }
        print(f"total-ish fields: {counts}")

    for product_code in SAMPLE_PRODUCTS:
        time.sleep(DELAY_SECONDS)
        response = session.get(f"{BASE_URL}{LOCALE_PATH}/product/{product_code}", timeout=30)
        describe(f"product page {product_code} (requests)", response)
        if not response.ok:
            print(f"body start:   {response.text[:200]!r}")
            continue
        print(f"saved:        {save(f'product_page_{product_code}.html', response.content)}")
        product = find_product(report_embedded_json(response.text))
        if product is None:
            print("product json: not found in page")
        else:
            report_product(product)


def is_blocked(title: str, html: str) -> bool:
    return "Access Denied" in title or "<H1>Access Denied</H1>" in html


def probe_selenium(headed: bool) -> None:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    options = Options()
    if not headed:
        options.add_argument("--headless=new")
    with webdriver.Chrome(options=options) as driver:
        print("\n== brands list (selenium)")
        driver.get(f"{BASE_URL}{LOCALE_PATH}/brands-list")
        time.sleep(DELAY_SECONDS)
        links = driver.find_elements(By.XPATH, '//a[@data-at="brand_link"]')
        print(f"brand links:  {len(links)}")
        print(f"country:      {(driver.get_cookie('current_country') or {}).get('value')}")
        brand_url = links[0].get_attribute("href") if links else None

        if brand_url:
            print(f"\n== brand page (selenium) {brand_url}")
            time.sleep(DELAY_SECONDS)
            driver.get(brand_url)
            time.sleep(DELAY_SECONDS)
            print(f"title:        {driver.title}")
            print(f"blocked:      {is_blocked(driver.title, driver.page_source)}")
            for _ in range(3):  # let lazy-loaded product tiles render
                driver.execute_script("window.scrollBy(0, 1500);")
                time.sleep(1)
            products = driver.find_elements(By.XPATH, '//a[contains(@href, "/product/")]')
            hrefs = sorted({href for a in products if (href := a.get_attribute("href"))})
            print(f"product links: {len(hrefs)}")
            for href in hrefs[:3]:
                print(f"  {href}")
            print(f"saved:        {save('brand_page.html', driver.page_source.encode())}")

        for product_code in SAMPLE_PRODUCTS:
            print(f"\n== product page {product_code} (selenium)")
            time.sleep(DELAY_SECONDS)
            driver.get(f"{BASE_URL}{LOCALE_PATH}/product/{product_code}")
            time.sleep(DELAY_SECONDS)
            html = driver.page_source
            print(f"title:        {driver.title}")
            if is_blocked(driver.title, html):
                print("blocked:      True")
                continue
            print(f"saved:        {save(f'product_page_{product_code}.html', html.encode())}")
            product = find_product(report_embedded_json(html))
            if product is None:
                print("product json: not found in page")
            else:
                report_product(product)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check what Sephora Canada returns to this machine."
    )
    parser.add_argument("--selenium", action="store_true", help="also try Chrome via Selenium")
    parser.add_argument(
        "--selenium-only", action="store_true", help="skip the plain requests checks"
    )
    parser.add_argument(
        "--headed", action="store_true", help="show the Chrome window instead of running headless"
    )
    args = parser.parse_args()
    if not args.selenium_only:
        probe_requests()
    if args.selenium or args.selenium_only:
        probe_selenium(headed=args.headed)
    print("\nDone. Paste everything above into the Claude session.")


if __name__ == "__main__":
    main()
