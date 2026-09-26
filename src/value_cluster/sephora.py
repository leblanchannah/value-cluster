"""Fetch and parse Sephora Canada pages without a browser.

Sephora embeds each page's data as JSON in ``<script id="linkStore">``. Product pages
carry the same product object the (now blocked) catalog API returned: ``productDetails``,
``currentSku``, ``regularChildSkus`` and ``parentCategory``. Every shade or size is a
child SKU with its own price, so there is no need to click swatches.

The client is deliberately slow and gives up when Sephora refuses requests: it never
tries to get around bot protection.
"""

import gzip
import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sephora.com"
LOCALE_PATH = "/ca/en"
COUNTRY = "CA"
CURRENCY = "CAD"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}
# Sephora picks the country from the IP address unless these are set.
LOCALE_COOKIES = {"site_locale": "ca", "site_language": "en"}

PRODUCT_CODE_RE = re.compile(r"(P\d+)(?:[/?#]|$)")


class BlockedError(RuntimeError):
    """Sephora refused too many requests in a row; stop instead of retrying."""


class NotCanadaError(RuntimeError):
    """Sephora served a non-Canadian page, so prices would not be CAD."""


@dataclass
class FetchStats:
    ok: int = 0
    blocked: int = 0
    not_found: int = 0
    errors: int = 0


@dataclass
class SephoraClient:
    """A slow, polite HTTP client for sephora.com/ca.

    ``delay`` seconds pass between requests. A 403/429 response doubles the wait (up to
    ``max_backoff``) and after ``max_consecutive_blocks`` refusals in a row the client
    raises :class:`BlockedError` so the run stops cleanly.
    """

    delay: float = 5.0
    max_backoff: float = 300.0
    max_consecutive_blocks: int = 3
    timeout: float = 30.0
    session: requests.Session = field(default_factory=requests.Session)
    stats: FetchStats = field(default_factory=FetchStats)
    sleep: Any = time.sleep
    last_status: int | None = field(default=None, init=False)
    _last_request: float = field(default=0.0, init=False)
    _consecutive_blocks: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.session.headers.update(HEADERS)
        self.session.cookies.update(LOCALE_COOKIES)

    def get(self, path_or_url: str) -> requests.Response | None:
        """GET a page. Returns None for 403/404/429 and network errors."""
        url = path_or_url if path_or_url.startswith("http") else f"{BASE_URL}{path_or_url}"
        wait = self.delay * (2**self._consecutive_blocks)
        self._pause(min(wait, self.max_backoff))
        self.last_status = None
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            logger.warning("request failed for %s: %s", url, e)
            self.stats.errors += 1
            return None
        self.last_status = response.status_code

        if is_blocked(response):
            self.stats.blocked += 1
            self._consecutive_blocks += 1
            logger.warning(
                "blocked (%s) on %s [%d in a row]",
                response.status_code,
                url,
                self._consecutive_blocks,
            )
            if self._consecutive_blocks >= self.max_consecutive_blocks:
                raise BlockedError(
                    f"Sephora refused {self._consecutive_blocks} requests in a row "
                    f"(last: {url}). Stopping; try again later."
                )
            return None

        self._consecutive_blocks = 0
        if response.status_code == 404:
            self.stats.not_found += 1
            return None
        if not response.ok:
            logger.warning("HTTP %s for %s", response.status_code, url)
            self.stats.errors += 1
            return None

        country = response.cookies.get("current_country") or self.session.cookies.get(
            "current_country"
        )
        if country and country != COUNTRY:
            raise NotCanadaError(f"Sephora served country={country} for {url}")
        self.stats.ok += 1
        return response

    def wait(self) -> None:
        """Wait out the normal delay (for work done outside ``get``, like a browser load)."""
        self._pause(self.delay)

    def _pause(self, seconds: float) -> None:
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < seconds:
            self.sleep(seconds - elapsed)
        self._last_request = time.monotonic()


def page_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return " ".join(match.group(1).split()) if match else None


def is_blocked(response: requests.Response) -> bool:
    if response.status_code in (403, 429):
        return True
    server = response.headers.get("server", "")
    return "Akamai" in server and "Access Denied" in response.text[:500]


# --- page JSON -------------------------------------------------------------------------


def extract_linkstore(html: str) -> dict | None:
    """Return the parsed ``<script id="linkStore">`` JSON from a page, if present."""
    tag = BeautifulSoup(html, "html.parser").find("script", id="linkStore")
    if tag is None:
        return None
    try:
        data = json.loads(tag.get_text())
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def iter_dicts(data: object) -> Iterator[dict]:
    """Yield every dict nested anywhere inside ``data`` (depth first)."""
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            yield item
            stack.extend(reversed(list(item.values())))
        elif isinstance(item, list):
            stack.extend(reversed(item))


def find_product(data: object) -> dict | None:
    """Find the product object (the dict with ``currentSku`` and ``productDetails``)."""
    for item in iter_dicts(data):
        if "currentSku" in item and "productDetails" in item:
            return item
    return None


def product_code_from_url(url: str) -> str | None:
    """``/ca/en/product/bad-gal-bang-mascara-P427517?skuId=1`` -> ``P427517``."""
    match = PRODUCT_CODE_RE.search(url.split("?")[0].split("#")[0] + "/")
    return match.group(1) if match else None


# --- product JSON -> rows --------------------------------------------------------------


def _category_chain(category: dict | None, key: str) -> str:
    """Join a category and its parents, leaf first: ``"Mascara --- Eye --- Makeup"``."""
    parts = []
    while category:
        if key in category:
            parts.append(str(category[key]))
        category = category.get("parentCategory")
    return " --- ".join(parts)


def sku_record(sku: dict) -> dict:
    refinements = sku.get("refinements") or {}
    return {
        "sku_id": sku.get("skuId"),
        "brand_name": sku.get("brandName", ""),
        "ingredients": sku.get("ingredientDesc", ""),
        "limited_edition": sku.get("isLimitedEdition"),
        "first_access": sku.get("isFirstAccess"),
        "limited_time_offer": sku.get("isLimitedTimeOffer"),
        "new_product": sku.get("isNew"),
        "online_only": sku.get("isOnlineOnly"),
        "few_left": sku.get("isOnlyFewLeft"),
        "out_of_stock": sku.get("isOutOfStock"),
        "price": sku.get("listPrice"),
        "sale_price": sku.get("salePrice"),
        "max_purchase_quantity": sku.get("maxPurchaseQuantity"),
        "size": sku.get("size", ""),
        "type": sku.get("type", ""),
        "url": sku.get("url", ""),
        "variation_type": sku.get("variationType", ""),
        "variation_value": sku.get("variationValue", ""),
        "returnable": sku.get("isReturnable"),
        "finish_refinement": " ".join(refinements.get("finishRefinements", [])),
        "size_refinement": " ".join(refinements.get("sizeRefinements", [])),
    }


def product_records(product: dict) -> list[dict]:
    """One row per SKU (the current SKU plus every child SKU, de-duplicated)."""
    details = product.get("productDetails", {})
    parent = product.get("parentCategory")
    shared = {
        "target_url": product.get("targetUrl", ""),
        "full_product_url": product.get("fullSiteProductUrl", ""),
        "product_code": product.get("productId", ""),
        "display_name": details.get("displayName", ""),
        "loves_count": details.get("lovesCount"),
        "rating": details.get("rating"),
        "reviews": details.get("reviews"),
        "brand_id": (details.get("brand") or {}).get("brandId", ""),
        "short_description": details.get("shortDescription", ""),
        "long_description": details.get("longDescription", ""),
        "suggested_usage": details.get("suggestedUsage", ""),
        "category_id": _category_chain(parent, "categoryId"),
        "category_name": _category_chain(parent, "displayName"),
        "category_url": _category_chain(parent, "targetUrl"),
        "country": COUNTRY,
        "currency": CURRENCY,
    }
    skus = [product["currentSku"], *product.get("regularChildSkus", [])]
    records, seen = [], set()
    for sku in skus:
        record = {**shared, **sku_record(sku)}
        if record["sku_id"] in seen:
            continue
        seen.add(record["sku_id"])
        price = record["price"]
        if price is not None and not str(price).lstrip().startswith("$"):
            raise NotCanadaError(f"unexpected price format {price!r} for {record['sku_id']}")
        records.append(record)
    return records


def parse_product_page(html: str) -> tuple[dict | None, list[dict]]:
    """Return ``(product_json, rows)`` for a product page; ``(None, [])`` if not found."""
    product = find_product(extract_linkstore(html))
    if product is None:
        return None, []
    return product, product_records(product)


def save_raw(product: dict, raw_dir: Path) -> Path:
    """Gzip the product JSON so it can be re-parsed later without scraping again."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{product.get('productId', 'unknown')}.json.gz"
    path.write_bytes(gzip.compress(json.dumps(product).encode()))
    return path


# --- discovery: brands and each brand's products ----------------------------------------

BRAND_PATH_RE = re.compile(r"^(?:https?://www\.sephora\.com)?(?:/ca/en)?(/brand/[\w\-]+)/?$")
URL_KEYS = ("targetUrl", "url", "brandUrl", "link")
NAME_KEYS = ("shortName", "displayName", "brandName", "name", "title")


def normalize_brand_url(url: str) -> str | None:
    """``https://www.sephora.com/ca/en/brand/a313`` or ``/brand/a313`` -> ``/ca/en/brand/a313``."""
    match = BRAND_PATH_RE.match(url.split("?")[0])
    return f"{LOCALE_PATH}{match.group(1)}" if match else None


def parse_brands(html: str) -> list[dict]:
    """Brands from the brands-list page: linkStore JSON first, then plain links."""
    brands: dict[str, str] = {}
    for item in iter_dicts(extract_linkstore(html)):
        url = next((item[k] for k in URL_KEYS if isinstance(item.get(k), str)), None)
        name = next((item[k] for k in NAME_KEYS if isinstance(item.get(k), str)), None)
        brand_url = normalize_brand_url(url) if url else None
        if brand_url and name:
            brands.setdefault(brand_url, name.strip())
    if not brands:
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            brand_url = normalize_brand_url(str(a["href"]))
            if brand_url and a.get_text(strip=True):
                brands.setdefault(brand_url, a.get_text(strip=True))
    return [{"brand_name": n, "brand_url": u} for u, n in sorted(brands.items())]


def parse_brand_products(html: str) -> list[dict]:
    """Products listed on a brand page: linkStore JSON first, then plain links."""
    products: dict[str, str] = {}
    for item in iter_dicts(extract_linkstore(html)):
        code = item.get("productId")
        url = item.get("targetUrl") or item.get("url")
        if isinstance(code, str) and PRODUCT_CODE_RE.fullmatch(code) and isinstance(url, str):
            products.setdefault(code, url)
    if not products:
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            href = str(a["href"])
            code = product_code_from_url(href) if "/product/" in href else None
            if code:
                products.setdefault(code, href)
    return [{"product_code": c, "product_url": u} for c, u in sorted(products.items())]


def product_page_path(product_code: str, product_url: str | None = None) -> str:
    """Canadian product page path; Sephora redirects ``/ca/en/product/P123`` to the slug URL."""
    if product_url:
        path = re.sub(r"^https?://www\.sephora\.com", "", product_url.split("?")[0])
        if not path.startswith(LOCALE_PATH):
            path = f"{LOCALE_PATH}{path}"
        return path
    return f"{LOCALE_PATH}/product/{product_code}"
