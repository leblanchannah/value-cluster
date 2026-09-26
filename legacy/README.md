# Legacy (2023) code

Frozen code from the original 2023 Data Visualization Society project. It is kept for reference and is not linted, type-checked, or tested in CI.

- `dash_app/`: the Plotly Dash dashboards (`app.py`, `app_v2.py`, `app_mobile.py`) behind the original "Sephora Value Canvas" site.
- `clean_product_data.py`: the v1 cleaning pipeline for the HTML-scraped 2023 data.

Both read `data/agg_prod_data.csv` / `data/products_format_v2/*`, which are produced by the 2023 scraper and are not in the repo. The 2025+ pipeline lives in `src/value_cluster/`.

The pure parsing helpers that used to live in `clean_product_data.py` moved to `src/value_cluster/parsing.py` (with their tests in `tests/test_parsing.py`). `clean_product_data.py` imports them from there.

Known issues if you try to run this code again:
- `clean_product_data.main()` unpacks `Series.str` into tuples, which pandas 2+ no longer supports.
- The Dash apps call `app.run_server`, which Dash 3 removed (use `app.run`).
