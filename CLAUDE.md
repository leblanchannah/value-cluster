# value-cluster

Scrapes Sephora Canada (sephora.com/ca, CAD prices), cleans the data, and analyzes pricing for blog posts. `docs/ROADMAP.md` has the review findings and phased plan. Each phase gets its own branch and PR.

## Layout
- `src/value_cluster/`: `webscraper.py` (Selenium brand pages + Sephora product API), `db_util.py` (SQLite), `preprocessing.py` (2025 cleaning pipeline), `parsing.py` (pure size/price helpers)
- `tests/`: pytest
- `notebooks/`: analysis notebook, reads `../data/preprocessed_data.csv`
- `legacy/`: frozen 2023 code (Dash apps, v1 pipeline). Excluded from ruff, ty, and pre-commit. Don't modify it unless asked.

## Commands
- `uv sync` installs runtime + dev dependencies (`--group notebook` for Jupyter)
- `uv run pytest`
- `uv run ruff check` and `uv run ruff format`
- `uv run ty check`
- `uv run pre-commit run --all-files` runs everything CI checks

## Notes
- Importing `value_cluster.webscraper` launches Chrome (module-level driver, fixed in the scraper phase). Don't import it in tests.
- Importing `value_cluster.db_util` or `webscraper` writes `db_operations.log` to the current directory (ignored by git).
- Always target the Canadian site (`/ca/en`, `countryCode=CA`, `loc=en-CA`).
