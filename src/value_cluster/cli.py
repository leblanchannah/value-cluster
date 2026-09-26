"""Command line entry point: ``uv run value-cluster scrape brands|products|details``.

Stages, in order:
    brands    brands-list page -> brands table
    seed      product codes from the January 2025 CSV -> products table (no requests)
    products  each brand page -> products table (Selenium fallback if needed)
    details   each product page -> product_details rows for a scrape run (one per SKU)

Each stage is safe to re-run. ``details`` resumes the latest unfinished run unless
``--new-run`` is given.
"""

import argparse
import gzip
import logging
import sys
from contextlib import ExitStack
from datetime import date
from pathlib import Path

from value_cluster import db_util
from value_cluster.sephora import (
    COUNTRY,
    LOCALE_PATH,
    BlockedError,
    NotCanadaError,
    SephoraClient,
    page_title,
    parse_brand_products,
    parse_brands,
    parse_product_page,
    product_page_path,
    save_raw,
)

logger = logging.getLogger("value_cluster")


def scrape_brands(args: argparse.Namespace, client: SephoraClient) -> None:
    response = client.get(f"{LOCALE_PATH}/brands-list")
    brands = parse_brands(response.text) if response else []
    if not brands and args.browser != "never":
        logger.info("no brands in the page HTML; rendering it in Chrome")
        from value_cluster.browser import chrome

        with chrome(headed=args.headed) as driver:
            driver.get(f"https://www.sephora.com{LOCALE_PATH}/brands-list")
            brands = parse_brands(driver.page_source)
    with db_util.connect(args.db) as conn:
        db_util.upsert_brands(conn, brands)
    print(f"brands saved: {len(brands)}")
    for brand in brands[:5]:
        print(f"  {brand['brand_name']}: {brand['brand_url']}")


def scrape_products(args: argparse.Namespace, client: SephoraClient) -> None:
    with db_util.connect(args.db) as conn:
        brands = db_util.get_brands(conn, args.brand)
    if not brands:
        sys.exit("No brands found. Run `value-cluster scrape brands` first (check --brand).")
    if args.limit:
        brands = brands[: args.limit]

    total = 0
    with ExitStack() as stack:
        driver = None
        for brand_id, brand_name, brand_url in brands:
            products = []
            if args.browser != "always":
                response = client.get(brand_url)
                products = parse_brand_products(response.text) if response else []
            if not products and args.browser != "never":
                from value_cluster.browser import chrome, scroll_brand_products

                if driver is None:
                    driver = stack.enter_context(chrome(headed=args.headed))
                client.wait()
                found = scroll_brand_products(driver, brand_url)
                if found is None:
                    print(f"{brand_name}: blocked in Chrome, skipping")
                    continue
                products = found
            with db_util.connect(args.db) as conn:
                db_util.upsert_products(conn, brand_id, products)
            total += len(products)
            print(f"{brand_name}: {len(products)} products")
    print(f"products saved: {total} from {len(brands)} brands")


def scrape_seed(args: argparse.Namespace, client: SephoraClient) -> None:
    """Load product codes and page links from an earlier scrape's CSV (no requests).

    Brand pages are refused by Sephora's bot protection, but product pages load, so
    the January 2025 product list is the starting point. Run ``scrape brands`` first
    so products are linked to brands (unmatched brands are kept without a link).
    """
    import pandas as pd

    df = pd.read_csv(args.csv, usecols=["product_code", "brand_name", "target_url"])
    df = df.dropna(subset=["product_code", "target_url"]).drop_duplicates("product_code")
    with db_util.connect(args.db) as conn:
        brand_ids = {name.lower(): brand_id for brand_id, name, _ in db_util.get_brands(conn)}
        unmatched: set[str] = set()
        for brand_name, group in df.groupby("brand_name", dropna=False):
            name = str(brand_name) if pd.notna(brand_name) else ""
            brand_id = brand_ids.get(name.lower())
            if brand_id is None:
                unmatched.add(name)
            products = [
                {"product_code": code, "product_url": url}
                for code, url in zip(group["product_code"], group["target_url"], strict=True)
            ]
            db_util.upsert_products(conn, brand_id, products)
    print(f"products loaded from {args.csv}: {len(df)} from {df['brand_name'].nunique()} brands")
    if not brand_ids:
        print("No brands in the database yet; run `value-cluster scrape brands` to link them.")
    elif unmatched:
        print(f"{len(unmatched)} brands not on today's brands list (kept without a brand link):")
        print("  " + ", ".join(sorted(unmatched)))


def scrape_details(args: argparse.Namespace, client: SephoraClient) -> None:
    with db_util.connect(args.db) as conn:
        products = db_util.get_products(conn, args.brand, None)
        if not products:
            sys.exit(
                "No products found. Run `value-cluster scrape seed` (products from the "
                "January 2025 CSV) or `value-cluster scrape products` first (check --brand)."
            )
        run_id = None if args.new_run else db_util.latest_open_run(conn, "details")
        if run_id is None:
            run_id = db_util.start_run(conn, "details", COUNTRY)
            done: set[str] = set()
        else:
            done = db_util.fetched_product_codes(conn, run_id)
            print(f"resuming run {run_id}: {len(done)} products already fetched")

    todo = [(code, url) for code, url in products if code not in done]
    if args.limit:
        todo = todo[: args.limit]
    raw_dir = Path("data/raw") / date.today().isoformat() if args.save_raw else None
    print(
        f"run {run_id}: fetching {len(todo)} product pages (~{len(todo) * client.delay / 60:.0f} min)"
    )

    rows_saved = 0
    missing: list[str] = []
    notes = ""
    no_data_dir = Path("data/probe/no_data")
    try:
        for i, (code, url) in enumerate(todo, 1):
            response = client.get(product_page_path(code, url))
            if response is None:
                if client.last_status == 404:
                    with db_util.connect(args.db) as conn:
                        db_util.record_fetch(conn, run_id, code, "not_found")
                continue  # blocked or network error: retried on the next run
            product, rows = parse_product_page(response.text)
            title = page_title(response.text)
            if not rows:
                missing.append(code)
                logger.warning(
                    "no product data for %s (landed on %s, title %r)", code, response.url, title
                )
                if len(missing) <= 5:  # keep a few pages to check what Sephora served
                    no_data_dir.mkdir(parents=True, exist_ok=True)
                    (no_data_dir / f"{code}.html.gz").write_bytes(gzip.compress(response.content))
                with db_util.connect(args.db) as conn:
                    db_util.record_fetch(conn, run_id, code, "no_data", response.url, title)
                continue
            if raw_dir and product:
                save_raw(product, raw_dir)
            with db_util.connect(args.db) as conn:
                rows_saved += db_util.insert_product_details(conn, run_id, rows)
                db_util.record_fetch(conn, run_id, code, "ok", response.url, title)
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} products, {rows_saved} SKU rows")
    except (BlockedError, NotCanadaError) as e:
        notes = str(e)
        print(f"\nStopped: {e}")
    except KeyboardInterrupt:
        notes = "interrupted"
        print("\nInterrupted; re-run the same command to resume.")
    finally:
        stats = client.stats
        with db_util.connect(args.db) as conn:
            fetched = len(db_util.fetched_product_codes(conn, run_id))
            if fetched >= len(products) or args.finish:
                db_util.finish_run(
                    conn,
                    run_id,
                    ok=stats.ok,
                    blocked=stats.blocked,
                    not_found=stats.not_found,
                    errors=stats.errors,
                    notes=notes,
                )
            sample = conn.execute(
                "SELECT product_code, brand_name, display_name, size, price, variation_value "
                "FROM product_details WHERE run_id = ? ORDER BY id DESC LIMIT 5",
                (run_id,),
            ).fetchall()
        print(
            f"\nSummary for run {run_id}: ok={stats.ok} blocked={stats.blocked} "
            f"not_found={stats.not_found} errors={stats.errors} no_data={len(missing)} "
            f"sku_rows={rows_saved}"
        )
        with db_util.connect(args.db) as conn:
            counts = db_util.fetch_status_counts(conn, run_id)
        print(f"products checked in this run so far: {fetched}/{len(products)} {counts}")
        for row in sample:
            print(f"  {row}")


def export(args: argparse.Namespace) -> None:
    """Write a run's SKU rows and page checks to gzipped CSVs that can be committed."""
    import pandas as pd

    with db_util.connect(args.db) as conn:
        run = conn.execute(
            "SELECT id, date(started_at) FROM scrape_runs WHERE stage = 'details' "
            + ("AND id = ? " if args.run else "")
            + "ORDER BY id DESC LIMIT 1",
            (args.run,) if args.run else (),
        ).fetchone()
        if run is None:
            sys.exit("No details run found to export.")
        run_id, started = run
        details = pd.read_sql_query(
            "SELECT * FROM product_details WHERE run_id = ? ORDER BY product_code, sku_id",
            conn,
            params=(run_id,),
        )
        fetches = pd.read_sql_query(
            "SELECT * FROM product_fetches WHERE run_id = ? ORDER BY product_code",
            conn,
            params=(run_id,),
        )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"sephora_ca_{started}_run{run_id}"
    for name, frame in [("skus", details), ("pages", fetches)]:
        path = args.out_dir / f"{stem}_{name}.csv.gz"
        frame.to_csv(path, index=False, compression="gzip")
        print(f"wrote {path} ({len(frame)} rows)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="value-cluster", description="Scrape and analyze Sephora Canada pricing."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    commands = parser.add_subparsers(dest="command", required=True)

    export_cmd = commands.add_parser("export", help="write a scrape run to data/snapshots/")
    export_cmd.add_argument("--db", type=Path, default=db_util.DEFAULT_DB, help="SQLite file")
    export_cmd.add_argument("--run", type=int, help="run id (default: latest details run)")
    export_cmd.add_argument("--out-dir", type=Path, default=Path("data/snapshots"))

    scrape = commands.add_parser("scrape", help="scrape Sephora Canada")
    scrape.add_argument("stage", choices=["brands", "seed", "products", "details"])
    scrape.add_argument(
        "--csv",
        type=Path,
        default=Path("data/preprocessed_data.csv"),
        help="seed: CSV with product_code, brand_name, target_url columns",
    )
    scrape.add_argument("--db", type=Path, default=db_util.DEFAULT_DB, help="SQLite file")
    scrape.add_argument(
        "--brand", help='only this brand: "Benefit Cosmetics" or benefit-cosmetics (any case)'
    )
    scrape.add_argument(
        "--limit", type=int, help="max brands (products stage) or product pages (details stage)"
    )
    scrape.add_argument(
        "--delay", type=float, default=5.0, help="seconds between requests (default 5)"
    )
    scrape.add_argument(
        "--browser",
        choices=["auto", "never", "always"],
        default="auto",
        help="use Chrome when a page has no data without JavaScript (default auto)",
    )
    scrape.add_argument("--headed", action="store_true", help="show the Chrome window")
    scrape.add_argument("--new-run", action="store_true", help="details: start a new run")
    scrape.add_argument(
        "--finish", action="store_true", help="details: mark the run finished even if partial"
    )
    scrape.add_argument(
        "--save-raw", action="store_true", help="details: save product JSON to data/raw/"
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("scrape.log")],
    )
    if args.command == "export":
        export(args)
        return
    client = SephoraClient(delay=args.delay)
    stages = {
        "brands": scrape_brands,
        "seed": scrape_seed,
        "products": scrape_products,
        "details": scrape_details,
    }
    try:
        stages[args.stage](args, client)
    except (BlockedError, NotCanadaError) as e:
        sys.exit(f"Stopped: {e}")


if __name__ == "__main__":
    main()
