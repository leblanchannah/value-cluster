"""SQLite storage for scraped Sephora data.

Every ``details`` scrape is a row in ``scrape_runs``; ``product_details`` rows carry the
``run_id`` so later scrapes can be compared with earlier ones (price history).
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path("data/db/products.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    country TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    ok INTEGER,
    blocked INTEGER,
    not_found INTEGER,
    errors INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL,
    brand_url TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER REFERENCES brands(id),
    product_url TEXT,
    product_code TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES scrape_runs(id),
    country TEXT,
    currency TEXT,
    target_url TEXT,
    full_product_url TEXT,
    product_code TEXT,
    loves_count INTEGER,
    rating REAL,
    reviews INTEGER,
    brand_source_id TEXT,
    category_id TEXT,
    category_name TEXT,
    category_url TEXT,
    sku_id TEXT,
    brand_name TEXT,
    display_name TEXT,
    ingredients TEXT,
    limited_edition BOOLEAN,
    first_access BOOLEAN,
    limited_time_offer BOOLEAN,
    new_product BOOLEAN,
    online_only BOOLEAN,
    few_left BOOLEAN,
    out_of_stock BOOLEAN,
    price TEXT,
    sale_price TEXT,
    max_purchase_quantity INTEGER,
    size TEXT,
    type TEXT,
    url TEXT,
    variation_type TEXT,
    variation_value TEXT,
    returnable BOOLEAN,
    finish_refinement TEXT,
    size_refinement TEXT,
    short_description TEXT,
    long_description TEXT,
    suggested_usage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, sku_id)
);
"""

# product_details column -> key in the records built by sephora.product_records()
DETAIL_COLUMNS = {
    "country": "country",
    "currency": "currency",
    "target_url": "target_url",
    "full_product_url": "full_product_url",
    "product_code": "product_code",
    "loves_count": "loves_count",
    "rating": "rating",
    "reviews": "reviews",
    "brand_source_id": "brand_id",
    "category_id": "category_id",
    "category_name": "category_name",
    "category_url": "category_url",
    "sku_id": "sku_id",
    "brand_name": "brand_name",
    "display_name": "display_name",
    "ingredients": "ingredients",
    "limited_edition": "limited_edition",
    "first_access": "first_access",
    "limited_time_offer": "limited_time_offer",
    "new_product": "new_product",
    "online_only": "online_only",
    "few_left": "few_left",
    "out_of_stock": "out_of_stock",
    "price": "price",
    "sale_price": "sale_price",
    "max_purchase_quantity": "max_purchase_quantity",
    "size": "size",
    "type": "type",
    "url": "url",
    "variation_type": "variation_type",
    "variation_value": "variation_value",
    "returnable": "returnable",
    "finish_refinement": "finish_refinement",
    "size_refinement": "size_refinement",
    "short_description": "short_description",
    "long_description": "long_description",
    "suggested_usage": "suggested_usage",
}


@contextmanager
def connect(db_file: str | Path = DEFAULT_DB) -> Iterator[sqlite3.Connection]:
    """Open the database (creating tables if needed), commit on success, always close."""
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_run(conn: sqlite3.Connection, stage: str, country: str) -> int:
    cursor = conn.execute(
        "INSERT INTO scrape_runs (stage, country) VALUES (?, ?)", (stage, country)
    )
    conn.commit()
    run_id = cursor.lastrowid
    assert run_id is not None
    return run_id


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ok: int,
    blocked: int,
    not_found: int,
    errors: int,
    notes: str = "",
) -> None:
    conn.execute(
        """UPDATE scrape_runs
           SET finished_at = CURRENT_TIMESTAMP, ok = ?, blocked = ?, not_found = ?,
               errors = ?, notes = ?
           WHERE id = ?""",
        (ok, blocked, not_found, errors, notes, run_id),
    )
    conn.commit()


def latest_open_run(conn: sqlite3.Connection, stage: str) -> int | None:
    """The most recent unfinished run for a stage, so an interrupted scrape can resume."""
    row = conn.execute(
        "SELECT id FROM scrape_runs WHERE stage = ? AND finished_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (stage,),
    ).fetchone()
    return row[0] if row else None


def upsert_brands(conn: sqlite3.Connection, brands: list[dict]) -> int:
    conn.executemany(
        """INSERT INTO brands (brand_name, brand_url) VALUES (:brand_name, :brand_url)
           ON CONFLICT (brand_url) DO UPDATE SET brand_name = excluded.brand_name""",
        brands,
    )
    conn.commit()
    return len(brands)


def get_brands(conn: sqlite3.Connection, name: str | None = None) -> list[tuple[int, str, str]]:
    """``(id, brand_name, brand_url)`` rows, optionally filtered by case-insensitive name."""
    query = "SELECT id, brand_name, brand_url FROM brands"
    params: tuple = ()
    if name:
        query += " WHERE lower(brand_name) = lower(?)"
        params = (name,)
    return conn.execute(query + " ORDER BY brand_name", params).fetchall()


def upsert_products(conn: sqlite3.Connection, brand_id: int, products: list[dict]) -> int:
    """Insert ``{"product_code", "product_url"}`` dicts for a brand; existing codes are kept."""
    conn.executemany(
        """INSERT INTO products (brand_id, product_url, product_code)
           VALUES (?, ?, ?)
           ON CONFLICT (product_code) DO UPDATE SET product_url = excluded.product_url""",
        [(brand_id, p["product_url"], p["product_code"]) for p in products],
    )
    conn.commit()
    return len(products)


def get_products(
    conn: sqlite3.Connection, brand: str | None = None, limit: int | None = None
) -> list[tuple[str, str]]:
    """``(product_code, product_url)`` rows, optionally for one brand and/or limited."""
    query = (
        "SELECT p.product_code, p.product_url FROM products p "
        "LEFT JOIN brands b ON b.id = p.brand_id"
    )
    params: list = []
    if brand:
        query += " WHERE lower(b.brand_name) = lower(?)"
        params.append(brand)
    query += " ORDER BY p.product_id"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    return conn.execute(query, params).fetchall()


def fetched_product_codes(conn: sqlite3.Connection, run_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT product_code FROM product_details WHERE run_id = ?", (run_id,)
    ).fetchall()
    return {row[0] for row in rows}


def insert_product_details(conn: sqlite3.Connection, run_id: int, records: list[dict]) -> int:
    columns = ["run_id", *DETAIL_COLUMNS]
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(
        f"INSERT OR REPLACE INTO product_details ({', '.join(columns)}) VALUES ({placeholders})",
        [(run_id, *(r.get(key) for key in DETAIL_COLUMNS.values())) for r in records],
    )
    conn.commit()
    return len(records)
