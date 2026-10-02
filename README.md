# Sephora Value Canvas - Data Visualization Society Project

[Sephora Value Canvas Dashboard](https://leblanchannah.pythonanywhere.com/)

## Overview

Welcome to the Sephora Product Price Comparison Dashboard! This project was created as part of the Data Visualization Society Mentorship Program and serves as a comprehensive tool for analyzing and comparing product prices at Sephora, a popular cosmetics and beauty store. In addition to visualizing product prices, this project includes a Python and Selenium web scraper to extract data from the Sephora website and a Python data science pipeline to clean and process the data.

The primary goal of this dashboard is to help users make informed purchasing decisions by providing insights into product unit prices. Sephora offers products in various sizes, and the unit prices can vary significantly. This dashboard not only compares the prices of different products but also highlights cost-effective options by identifying products with lower unit prices.

This project was inspired by the ["Sephora Minis Math"](https://www.tiktok.com/@michaelamakeup92/video/7237211338618047787") TikTok by @michaelamakeup92


## Features

- **Data Scraper:** This project includes a Python and Selenium web scraper that allows you to extract product data from the Sephora website. You can easily customize the scraper to collect specific information for analysis. Data collected from Sephora Canada (sephora.com/ca, prices in CAD) in January 2025 is provided in `data/preprocessed_data.csv`.

- **Data Cleaning:** Once the data is collected, it goes through a comprehensive data cleaning process to ensure accuracy and consistency.

- **Plotly Dash Dashboard:** The heart of the original 2023 project is the interactive Plotly Dash dashboard that provides various visualizations and tools for product price comparison. Its code is kept in `legacy/dash_app/` (see `legacy/README.md`).

- **Product Price Comparison:** The dashboard allows users to compare the unit prices of different products. It highlights products with multiple size options, enabling users to identify the most cost-effective choice.

- **Recommendations:** In addition to comparing prices, the dashboard provides recommendations for cheaper alternatives, helping users save money while shopping at Sephora.


## Dashboard Usage

The dashboard provides an intuitive interface for users to:

- View product price comparisons.
- Explore unit prices for different product sizes.
- Receive recommendations for cost-effective products.


## Project layout

```
src/value_cluster/   scraper, SQLite helpers, preprocessing, parsing helpers
tests/               pytest tests
notebooks/           exploratory analysis and figures
data/                January 2025 preprocessed data and sample swatches
figures/             exported charts
legacy/              frozen 2023 code (Dash apps, v1 cleaning pipeline)
docs/ROADMAP.md      code review findings and modernization plan
```

## Running the scraper

Sephora blocks requests from cloud servers, so run this on your own computer. The scraper waits 5 seconds between pages and stops if Sephora refuses several requests in a row. Data goes to `data/db/products.db` (SQLite, not committed).

```bash
uv run value-cluster scrape brands            # brands-list page -> brands table
uv run value-cluster scrape sitemap           # every product in Sephora's product sitemap
uv run value-cluster scrape seed              # product list from data/preprocessed_data.csv
uv run value-cluster scrape details --limit 20   # product pages -> one row per SKU
uv run value-cluster scrape details           # resumes the unfinished run
uv run value-cluster export                   # latest run -> data/snapshots/*.csv.gz to commit
```

Brand pages are currently refused by Sephora's bot protection, so products are found another way. `sitemap` reads Sephora's product sitemap (`products-sitemap.xml`), which lists every product currently on the site, including ones added since January 2025. `seed` adds the January 2025 products (5,342), so discontinued ones are checked too. If the script can't fetch the sitemap, save it from your browser and pass the file: `--sitemap ~/Downloads/products-sitemap.xml`. `scrape products --brand benefit-cosmetics` lists a brand's products from its page when that page is available. `--brand` takes the display name or the URL name.

Every product page checked is recorded in `product_fetches` with a status: `ok`, `no_data` (the page loaded but had no product, usually because it was discontinued), or `not_found`. Blocked pages aren't recorded, so they're retried on the next run. A few `no_data` pages are saved in `data/probe/no_data/` so you can check what Sephora showed.

Each `details` run gets a `run_id`, so later scrapes can be compared with earlier ones. Add `--save-raw` to keep each product's JSON in `data/raw/`, and `--headed` to watch Chrome when it's used. `scrape.log` has the details of each request.

## Development

This project uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.

```bash
uv sync                          # create .venv with runtime + dev dependencies
uv sync --group notebook         # add Jupyter, plotly, scikit-learn, etc.
uv run pre-commit install        # run ruff, ty and file checks on every commit

uv run pytest                    # tests
uv run ruff check                # lint
uv run ruff format               # format
uv run ty check                  # type check
uv run pre-commit run --all-files
```

CI (GitHub Actions) runs ruff, ty and pytest on every pull request.

## Contact

If you have any questions or suggestions, please reach out

- Hannah LeBlanc
  - Email: leblanchannahm@gmail.com
  - GitHub: [https://github.com/leblanchannah](https://github.com/leblanchannah)

## Acknowledgments

Thank you to my DVS Mentor Matt!

Happy data exploring and shopping at Sephora! 🛍️
