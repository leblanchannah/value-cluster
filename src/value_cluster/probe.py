"""Check what Sephora Canada returns to this machine before running a full scrape.

Run from the repo root:

    uv run python -m value_cluster.probe              # plain HTTP requests only
    uv run python -m value_cluster.probe --selenium   # also try headless Chrome

It makes a handful of requests (a few seconds apart), prints a summary to paste
back into the Claude session, and saves the responses (gzipped) under
tests/fixtures/sephora/ so parsers and tests can be built from real data.

What it checks:
- requests: brands list and product pages, looking for product JSON embedded in the HTML
- selenium: brands list, one brand page's product links, and the product API
  called with fetch() from inside the browser (the plain API call gets a 403)
"""

import argparse
import gzip
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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


def find_product(data: object) -> dict | None:
    """Find the product object (the dict with a currentSku) anywhere in nested page JSON."""
    if isinstance(data, dict):
        if "currentSku" in data and "productDetails" in data:
            return data
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    for child in children:
        found = find_product(child)
        if found is not None:
            return found
    return None


def probe_requests() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(LOCALE_COOKIES)

    brands = session.get(f"{BASE_URL}{LOCALE_PATH}/brands-list", timeout=30)
    describe("brands list (requests)", brands)
    if brands.ok:
        link_store = report_embedded_json(brands.text)
        print(f"linkStore:    {'found' if link_store else 'not found'}")
        print(f"saved:        {save('brands_list.html', brands.content)}")

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


def probe_selenium() -> None:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
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
            products = driver.find_elements(By.XPATH, '//a[contains(@href, "/ca/en/product/")]')
            hrefs = sorted({href for a in products if (href := a.get_attribute("href"))})
            print(f"product links (before scrolling): {len(hrefs)}")
            if hrefs:
                print(f"first link:   {hrefs[0]}")

        for product_code in SAMPLE_PRODUCTS:
            print(f"\n== product API {product_code} (fetch inside selenium)")
            time.sleep(DELAY_SECONDS)
            url = (
                requests.Request(
                    "GET", f"{BASE_URL}/api/v3/catalog/products/{product_code}", params=API_PARAMS
                )
                .prepare()
                .url
            )
            result = driver.execute_async_script(
                """
                const done = arguments[arguments.length - 1];
                fetch(arguments[0], {credentials: "include"})
                  .then(r => r.text().then(body => done({status: r.status, body})))
                  .catch(e => done({status: -1, body: String(e)}));
                """,
                url,
            )
            print(f"status:       {result['status']}")
            try:
                data = json.loads(result["body"])
            except ValueError:
                print(f"body start:   {result['body'][:200]!r}")
                continue
            report_product(data)
            print(f"saved:        {save(f'product_{product_code}.json', result['body'].encode())}")


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
