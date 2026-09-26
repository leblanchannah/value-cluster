"""Check what Sephora Canada returns to this machine before running a full scrape.

Run from the repo root:

    uv run python -m value_cluster.probe              # plain HTTP requests only
    uv run python -m value_cluster.probe --selenium   # also try headless Chrome

It makes a handful of requests (a few seconds apart), prints a summary to paste
back into the Claude session, and saves the responses (gzipped) under
tests/fixtures/sephora/ so parsers and tests can be built from real data.
"""

import argparse
import gzip
import time
from pathlib import Path

import requests

BASE_URL = "https://www.sephora.com"
LOCALE_PATH = "/ca/en"
# Products that exist in the January 2025 snapshot (data/preprocessed_data.csv).
SAMPLE_PRODUCTS = ["P513304", "P427517"]
API_PARAMS = {
    "addCurrentSkuToProductChildSkus": "true",
    "includeRegionsMap": "true",
    "showContent": "true",
    "includeConfigurableSku": "true",
    "countryCode": "CA",
    "removePersonalizedData": "true",
    "includeReviewFilters": "true",
    "includeReviewImages": "false",
    "includeRnR": "true",
    "loc": "en-CA",
    "ch": "rwd",
}
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
FIXTURE_DIR = Path("tests/fixtures/sephora")


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


def probe_requests() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(LOCALE_COOKIES)

    home = session.get(f"{BASE_URL}{LOCALE_PATH}/", timeout=30)
    describe("homepage", home)
    time.sleep(DELAY_SECONDS)

    brands = session.get(f"{BASE_URL}{LOCALE_PATH}/brands-list", timeout=30)
    describe("brands list", brands)
    brand_links = brands.text.count('data-at="brand_link"')
    print(f"brand links:  {brand_links}")
    if brands.ok:
        print(f"saved:        {save('brands_list.html', brands.content)}")

    for product_code in SAMPLE_PRODUCTS:
        time.sleep(DELAY_SECONDS)
        response = session.get(
            f"{BASE_URL}/api/v3/catalog/products/{product_code}", params=API_PARAMS, timeout=30
        )
        describe(f"product API {product_code}", response)
        try:
            data = response.json()
        except ValueError:
            print("json:         not JSON (probably a bot-protection page)")
            print(f"body start:   {response.text[:200]!r}")
            continue
        sku = data.get("currentSku", {})
        print(f"display name: {data.get('productDetails', {}).get('displayName')}")
        print(f"list price:   {sku.get('listPrice')}  size: {sku.get('size')}")
        print(f"child skus:   {len(data.get('regularChildSkus', []))}")
        print(f"saved:        {save(f'product_{product_code}.json', response.content)}")


def probe_selenium() -> None:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    print("\n== selenium brands list")
    with webdriver.Chrome(options=options) as driver:
        driver.get(f"{BASE_URL}{LOCALE_PATH}/brands-list")
        time.sleep(DELAY_SECONDS)
        links = driver.find_elements(By.XPATH, '//a[@data-at="brand_link"]')
        print(f"title:        {driver.title}")
        print(f"brand links:  {len(links)}")
        if links:
            print(f"first link:   {links[0].get_attribute('href')}")
        print(f"country cookie: {driver.get_cookie('current_country')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check what Sephora Canada returns to this machine."
    )
    parser.add_argument("--selenium", action="store_true", help="also try headless Chrome")
    args = parser.parse_args()
    probe_requests()
    if args.selenium:
        probe_selenium()
    print("\nDone. Paste everything above into the Claude session.")


if __name__ == "__main__":
    main()
