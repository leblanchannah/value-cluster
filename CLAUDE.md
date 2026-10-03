# shelf-life

Scrapes Sephora Canada (sephora.com/ca, CAD prices), cleans the data, and analyzes pricing for blog posts. `docs/ROADMAP.md` has the review findings and phased plan. Each phase gets its own branch and PR.

## Layout
- `src/shelf_life/`:
  - `sephora.py`: requests client (slow, backs off and stops when blocked) and parsers for the JSON Sephora embeds in pages (`<script id="linkStore">`)
  - `cli.py`: `shelf-life scrape brands|sitemap|seed|products|details`, `export`, `preprocess`
  - `db_util.py`: SQLite schema (`scrape_runs`, `brands`, `products`, `product_details`)
  - `preprocessing.py`: `product_details` rows -> analysis table (numeric prices/sizes, category levels, unit prices)
  - `parsing.py`: pure `parse_price` / `parse_size` helpers
- `tests/`: pytest
- `notebooks/`: analysis notebook, reads `../data/preprocessed_data.csv`
- `legacy/`: frozen 2023 code (Dash apps, v1 pipeline). Excluded from ruff, ty, and pre-commit. Don't modify it unless asked.

## Commands
- `uv sync` installs runtime + dev dependencies (`--group notebook` for Jupyter)
- `uv run pytest`
- `uv run ruff check` and `uv run ruff format`
- `uv run ty check`
- `uv run pre-commit run --all-files` runs everything CI checks
- `uv run shelf-life scrape details --limit 20` (run locally only)

## Notes
- Sephora's bot protection (Akamai) blocks the product API and all requests from cloud IPs, so scraping only works from Hannah's own machine. Never add ways around it (stealth plugins, faked fingerprints, proxies). The client stops after repeated 403s on purpose.
- Tests are offline. Use fixtures in `tests/fixtures/sephora/` or synthetic pages; never hit sephora.com in tests.
- Always target the Canadian site (`/ca/en`, `countryCode=CA`, `loc=en-CA`).
