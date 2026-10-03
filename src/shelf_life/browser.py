"""Selenium fallback for pages that only list products after JavaScript runs.

Brand pages lazy-load product tiles as you scroll. This scrolls until no new product
links appear. It uses a normal Chrome session at a slow pace and does not try to hide
that it is automated.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from shelf_life.sephora import BASE_URL, product_code_from_url


@contextmanager
def chrome(headed: bool = False) -> Iterator[webdriver.Chrome]:
    options = Options()
    if not headed:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    try:
        yield driver
    finally:
        driver.quit()


def is_blocked(driver: webdriver.Chrome) -> bool:
    return "Access Denied" in driver.title or "<H1>Access Denied</H1>" in driver.page_source


def scroll_brand_products(
    driver: webdriver.Chrome,
    brand_url: str,
    pause: float = 2.0,
    max_scrolls: int = 60,
) -> list[dict] | None:
    """Scroll a brand page and return ``{"product_code", "product_url"}`` dicts.

    Returns None when the page is blocked.
    """
    driver.get(brand_url if brand_url.startswith("http") else f"{BASE_URL}{brand_url}")
    time.sleep(pause * 2)
    if is_blocked(driver):
        return None

    products: dict[str, str] = {}
    previous_count = -1
    stable_rounds = 0
    for _ in range(max_scrolls):
        for a in driver.find_elements(By.XPATH, '//a[contains(@href, "/product/")]'):
            href = a.get_attribute("href")
            code = product_code_from_url(href) if href else None
            if code and href:
                products.setdefault(code, href)
        stable_rounds = stable_rounds + 1 if len(products) == previous_count else 0
        previous_count = len(products)
        at_bottom = driver.execute_script(
            "return window.innerHeight + window.scrollY >= document.body.scrollHeight - 5;"
        )
        if at_bottom and stable_rounds >= 2:
            break
        _click_show_more(driver)
        driver.execute_script("window.scrollBy(0, 1500);")
        time.sleep(pause)
    return [{"product_code": c, "product_url": u} for c, u in sorted(products.items())]


def _click_show_more(driver: webdriver.Chrome) -> None:
    for button in driver.find_elements(By.XPATH, '//button[contains(., "Show More")]'):
        try:
            button.click()
            time.sleep(1)
        except Exception:  # button not clickable yet; the next scroll retries
            pass
