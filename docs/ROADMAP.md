# Roadmap

Code review findings (September 2026) and the plan for modernizing the project. The goal is to scrape Sephora Canada pricing on a schedule, store it in Postgres, and run queries for blog posts about Sephora pricing.

Each phase is its own branch and pull request.

| Phase | Status |
| --- | --- |
| 1. Tooling: pyproject/uv, ruff, ty, pre-commit, CI, package layout | Done |
| 2. Scraper fixes (Sephora Canada) | In review |
| 3. Postgres schema and migrations | Not started |
| 4. Automation and hosting | Not started |
| 5. Analysis and blog | Not started |

## Review findings

### Bugs in the current code

1. **Scraper passes a tuple as the product code.** In `webscraper.py`'s `__main__` block, `for product_code in found_products` gives `('P123',)`, which ends up in the API URL. The January 2025 version used `product_code[0]`, so this is a regression.
2. **Chrome starts at import time.** `webscraper.py` creates a module-level `webdriver.Chrome(...)` that is never closed. `BrandListScraper.get_brand_urls` reads that global `driver` instead of `self.driver`, so it only works because of the stray browser.
3. **`preprocessing.py` expects old column names.** It reads `category_root_id/name/url`, but commit 7332d0f renamed the database columns to `category_id/name/url`. A fresh scrape would fail with a `KeyError`.
4. **Wrong price per ml for solids.** `preprocessing.py` converts oz to ml whenever ml is missing. For sizes like "1.7 oz / 48 g" the oz is a weight, so `value_CAD_ml` is wrong for those products.
5. **Size regex misses "fl oz" and litres.** In `parse_size_data`, the "fl" breaks the match, and `l` is not in the unit list, so the `unit_2 == "l"` branch never runs.
6. **Database connections leak.** Since b261912, `db_util.get_db_connection` returns a bare connection. `with conn:` commits but never closes it, and the "connection closed" log message is logged before anything is used.
7. **No deduplication or scrape runs.** No table has UNIQUE constraints, so every run appends duplicate brands, products, and details. Without a run ID, comparing scrapes over time depends on `created_at`.
8. **`brand_id` can be unset.** In the brand loop, `fetchone()[0]` fails when the brand isn't found, and `brand_id` is undefined if the SQLite call raises.
9. **Fragile API calls.** `ProductScraper.get_product_data_api` creates a new session and loads the homepage for every product, with no timeout, retries, or status check. `response.json()` crashes when Sephora returns an HTML block page.
10. **Crashes on missing HTML elements.** `BrandListScraper` fails if a brand link has no `<span>`. The two spots ty flags are marked with `TODO(roadmap: scraper phase)`.
11. **Dead HTML-scraping code.** About 140 lines of `ProductScraper._get_*` methods are marked "not tested", and one calls `find_elements_by_xpath`, which Selenium 4 removed.
12. **Logging and paths.** Logging is configured at import time in two modules and writes `db_operations.log` to whatever the current directory is. Paths depend on the current directory and disagree (`data/db/products.db` vs `../data/db/products.db`).

Fixed in Phase 1: `clean_product_data.py` imported a function that doesn't exist (`drop_duplicate_product_urls`), so the tests couldn't run. It now lives in `legacy/`, and its helpers and tests are in `shelf_life.parsing` / `tests/test_parsing.py`.

### Housekeeping

- **Data in git.** There's a 27 MB CSV and about 7 MB of PNGs in git. Once the database exists, move the data out (database, GitHub release asset, or Git LFS).
- **Canada.** The brand/product discovery and API calls already target `/ca/en` with `countryCode=CA&loc=en-CA`. But session setup and swatch downloads use the root site, and nothing checks that prices are in CAD.
- **Legacy dashboard.** The Dash apps in `legacy/dash_app` read `agg_prod_data.csv`, which isn't in the repo, and call `app.run_server`, which Dash 3 removed.

## Phase 2: Scraper fixes (Sephora Canada)

**What we found (September 2026):** Sephora's bot protection (Akamai) now returns 403 for the product API, including when it's called from inside Selenium, and for every request from cloud servers. From a home connection, plain requests can load the brands list and product pages, although product pages have also been refused at times. Product pages embed the full product JSON in `<script id="linkStore">`, including every shade and size as a child SKU with its own price, so no swatch clicking is needed. The scraper uses those pages, goes slowly, and stops when blocked. It doesn't try to get around the bot protection.

**Done in this phase:** `sephora.py` (client and parsers), `browser.py` (Selenium scroll fallback), `cli.py`, and a new SQLite schema with scrape runs, UNIQUE constraints and upserts. The old `webscraper.py` was removed, which fixes bugs 1, 2, and 7–12 above.

**Update (October 2026):** Sephora's product sitemap (`/products-sitemap.xml`) lists every current product, so `shelf-life scrape sitemap` finds products without brand pages.

The original plan for this phase:


- Fix bugs 1, 2, and 8–12 above.
- Add a CLI, for example `uv run shelf-life scrape brands|products|details --limit N --brand NAME`.
- Default to Canada with `--country CA`: use `/ca/en` URLs, set the locale cookies and API params, and check each response's locale/currency. Store `country` and `currency` with every price.
- Reuse one `requests` session with timeouts and retries with backoff. Keep a crawl delay of at least 4 s and respect `robots.txt`.
- Save raw API responses (gzipped JSON), so data can be re-parsed without scraping again.
- Add offline tests using a recorded Canadian API response as a fixture.
- For product discovery, try something lighter than Selenium first (sitemaps or JSON endpoints). If that doesn't work, use Playwright, since Chromium is already installed in Claude cloud sessions.
- Note: the cloud environment's network policy has to allow `www.sephora.com`, and the setting applies to new sessions.

## Phase 3: Postgres schema and migrations

Use SQLAlchemy 2 + Alembic + psycopg 3, with a `docker-compose.yml` Postgres for local development.

Proposed tables:

| Table | Purpose |
| --- | --- |
| `scrape_runs` | one row per scrape: started/finished, country, status, counts |
| `brands` | Sephora brand ID, name, URL |
| `categories` | category tree (self-referencing `parent_id`) |
| `products` | keyed by the Sephora product code (`P513304`); brand, leaf category, name, URL, first/last seen |
| `skus` | keyed by the Sephora SKU ID; product, size text, parsed `size_ml`/`size_g`/`size_floz`, multipack count, SKU type (standard/mini/value/refill) |
| `sku_prices` | time series: run, SKU, list and sale price, currency, stock and limited-edition flags |
| `product_metrics` | time series: run, product, loves, rating, review count |
| `product_content` | ingredients and descriptions, stored only when their hash changes |

Views: `latest_prices`, `unit_prices` (price per ml/g), and `mini_vs_standard`.

Load the January 2025 CSV as run #1 so there's price history from day one. Fix bugs 3–5 when the parsing moves into the loader.

## Phase 4: Automation and hosting

- **Where the scraper runs:** a scheduled GitHub Actions workflow, which is free for public repos. Jobs are capped at 6 hours and the full crawl took about 8 hours, so refresh one-seventh of products each day for full coverage every week.
  - Caveat: Sephora uses bot protection that often blocks datacenter IPs (GitHub Actions, cloud VMs). If that happens, run the scraper with cron on a home machine or Raspberry Pi and write to the hosted database.
- **Claude Code cloud:** Routines can start a Claude session on a schedule. The containers are temporary and limited by the network policy, so they aren't meant to host an 8-hour crawl or a database. They work well for:
  - a weekly scraper health check that opens a fix PR when Sephora changes something
  - querying the database and drafting analysis notes for the blog
- **Database:** Neon's free Postgres tier is recommended (scales to zero, has branching). Supabase's free tier is an alternative, but it pauses when idle. Check current free-tier limits. With long text deduplicated, a price snapshot is a few MB per run, so a year of weekly runs fits in a free tier.
- **Raw JSON archives:** keep them in object storage (e.g. Cloudflare R2), not Postgres.

## Phase 5: Analysis and blog

- **Queries:** DuckDB for local SQL. It can query Postgres directly as well as CSV/Parquet.
- **Publishing:** a Quarto blog on GitHub Pages, which renders Jupyter notebooks as posts.
- **Post ideas:**
  - price changes and shrinkflation from January 2025 to 2026
  - mini vs standard value
  - price per ml by brand and category
  - whether "value size" is actually better value

## Optional

- A SessionStart hook so Claude Code cloud sessions run `uv sync` automatically.
- `nbstripout` to keep notebook diffs small.
- A SQL-backed rewrite of the dashboard once the database exists.
