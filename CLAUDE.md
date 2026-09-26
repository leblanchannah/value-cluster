# value-cluster

Scrapes Sephora Canada (sephora.com/ca, CAD prices), cleans the data, and analyzes pricing for blog posts. `docs/ROADMAP.md` has the review findings and phased plan. Each phase gets its own branch and PR.

## Layout
- `src/value_cluster/`:
  - `sephora.py`: requests client (slow, backs off and stops when blocked) and parsers for the JSON Sephora embeds in pages (`<script id="linkStore">`)
  - `browser.py`: Selenium fallback that scrolls brand pages
  - `cli.py`: `value-cluster scrape brands|products|details`
  - `db_util.py`: SQLite schema (`scrape_runs`, `brands`, `products`, `product_details`)
  - `preprocessing.py`: 2025 cleaning pipeline
  - `parsing.py`: pure size/price helpers
  - `probe.py`: diagnostic for what Sephora returns to a machine
- `tests/`: pytest
- `notebooks/`: analysis notebook, reads `../data/preprocessed_data.csv`
- `legacy/`: frozen 2023 code (Dash apps, v1 pipeline). Excluded from ruff, ty, and pre-commit. Don't modify it unless asked.

## Commands
- `uv sync` installs runtime + dev dependencies (`--group notebook` for Jupyter)
- `uv run pytest`
- `uv run ruff check` and `uv run ruff format`
- `uv run ty check`
- `uv run pre-commit run --all-files` runs everything CI checks
- `uv run value-cluster scrape details --limit 20` (run locally only)

## Notes
- Sephora's bot protection (Akamai) blocks the product API and all requests from cloud IPs, so scraping only works from Hannah's own machine. Never add ways around it (stealth plugins, faked fingerprints, proxies). The client stops after repeated 403s on purpose.
- Tests are offline. Use fixtures in `tests/fixtures/sephora/` or synthetic pages; never hit sephora.com in tests.
- Always target the Canadian site (`/ca/en`, `countryCode=CA`, `loc=en-CA`).
