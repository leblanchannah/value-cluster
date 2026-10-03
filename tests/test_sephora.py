import gzip
import json
from pathlib import Path

import pytest
import requests

from shelf_life import db_util
from shelf_life.cli import main
from shelf_life.sephora import (
    BlockedError,
    NotCanadaError,
    SephoraClient,
    extract_linkstore,
    is_blocked,
    normalize_brand_url,
    parse_brand_products,
    parse_brands,
    parse_product_page,
    parse_sitemap,
    product_code_from_url,
    product_page_path,
    product_records,
)

BLOCK_PAGE = "<HTML><HEAD>\n<TITLE>Access Denied</TITLE>\n</HEAD><BODY>\n<H1>Access Denied</H1>"


def sku(sku_id, price="$39.00", size="0.3 oz./8.5 g", **extra):
    return {
        "skuId": sku_id,
        "brandName": "Benefit Cosmetics",
        "listPrice": price,
        "size": size,
        "type": "Standard",
        "url": f"https://www.sephora.com/api/v3/catalog/skus/{sku_id}",
        "variationType": "Color",
        "variationValue": f"shade {sku_id}",
        "isLimitedEdition": False,
        "isOutOfStock": False,
        **extra,
    }


def make_product(child_ids=("1", "2", "3", "4", "5"), current="1"):
    return {
        "productId": "P427517",
        "targetUrl": "/ca/en/product/bad-gal-bang-mascara-P427517",
        "productDetails": {
            "displayName": "BADgal BANG! Volumizing 36-Hour Longwear Mascara",
            "lovesCount": 12345,
            "rating": 4.2,
            "reviews": 678,
            "brand": {"brandId": "5694"},
        },
        "parentCategory": {
            "categoryId": "cat1",
            "displayName": "Mascara",
            "targetUrl": "/shop/mascara",
            "parentCategory": {
                "categoryId": "cat2",
                "displayName": "Eye",
                "targetUrl": "/shop/eye",
            },
        },
        "currentSku": sku(current),
        "regularChildSkus": [sku(i) for i in child_ids],
    }


def page(linkstore: dict, body: str = "") -> str:
    return (
        '<html><head><script id="linkStore" type="text/json" data-comp="PageJSON ">'
        f"{json.dumps(linkstore)}</script></head><body>{body}</body></html>"
    )


def response(status=200, text="", server="nginx", country="CA") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = text.encode()
    r.headers["server"] = server
    r.url = "https://www.sephora.com/ca/en/"
    if country:
        r.cookies.set("current_country", country)
    return r


# --- parsing ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, code",
    [
        ("/ca/en/product/bad-gal-bang-mascara-P427517", "P427517"),
        ("https://www.sephora.com/ca/en/product/x-P513304?skuId=2797074", "P513304"),
        ("/product/P123", "P123"),
        ("/ca/en/brand/benefit-cosmetics", None),
    ],
)
def test_product_code_from_url(url, code):
    assert product_code_from_url(url) == code


def test_product_records_one_row_per_sku_without_duplicates():
    rows = product_records(make_product())
    assert [r["sku_id"] for r in rows] == ["1", "2", "3", "4", "5"]
    first = rows[0]
    assert first["product_code"] == "P427517"
    assert first["price"] == "$39.00"
    assert first["size"] == "0.3 oz./8.5 g"
    assert first["category_name"] == "Mascara --- Eye"
    assert first["brand_id"] == "5694"
    assert (first["country"], first["currency"]) == ("CA", "CAD")


def test_product_records_includes_current_sku_when_not_a_child():
    rows = product_records(make_product(child_ids=(), current="9"))
    assert [r["sku_id"] for r in rows] == ["9"]


def test_product_records_rejects_non_dollar_prices():
    product = make_product()
    product["currentSku"]["listPrice"] = "39,00 €"
    with pytest.raises(NotCanadaError):
        product_records(product)


def test_parse_product_page_finds_nested_product():
    html = page({"page": {"product": make_product()}})
    product, rows = parse_product_page(html)
    assert product is not None and product["productId"] == "P427517"
    assert len(rows) == 5


def test_parse_product_page_without_data():
    assert parse_product_page("<html></html>") == (None, [])
    assert extract_linkstore('<script id="linkStore">not json</script>') is None


def test_parse_brands_from_linkstore_and_links():
    from_json = page(
        {
            "brands": [
                {"displayName": "Benefit Cosmetics", "targetUrl": "/ca/en/brand/benefit-cosmetics"},
                {"displayName": "AAVRANI", "targetUrl": "/brand/aavrani"},
                {"displayName": "Not a brand", "targetUrl": "/ca/en/shop/makeup"},
            ]
        }
    )
    assert parse_brands(from_json) == [
        {"brand_name": "AAVRANI", "brand_url": "/ca/en/brand/aavrani"},
        {"brand_name": "Benefit Cosmetics", "brand_url": "/ca/en/brand/benefit-cosmetics"},
    ]
    from_links = '<a data-at="brand_link" href="https://www.sephora.com/ca/en/brand/a313"><span>A313</span></a>'
    assert parse_brands(from_links) == [{"brand_name": "A313", "brand_url": "/ca/en/brand/a313"}]


def test_normalize_brand_url():
    assert (
        normalize_brand_url("https://www.sephora.com/ca/en/brand/a313?x=1") == "/ca/en/brand/a313"
    )
    assert normalize_brand_url("/ca/en/product/x-P1") is None


def test_parse_brand_products_from_linkstore_and_links():
    from_json = page(
        {
            "products": [
                {"productId": "P427517", "targetUrl": "/product/bad-gal-bang-mascara-P427517"}
            ]
        }
    )
    assert parse_brand_products(from_json) == [
        {"product_code": "P427517", "product_url": "/product/bad-gal-bang-mascara-P427517"}
    ]
    from_links = '<a href="/ca/en/product/x-P513304?skuId=1">x</a><a href="/ca/en/brand/y">y</a>'
    assert parse_brand_products(from_links) == [
        {"product_code": "P513304", "product_url": "/ca/en/product/x-P513304?skuId=1"}
    ]


def test_product_page_path_is_canadian():
    assert product_page_path("P1", "/product/x-P1") == "/ca/en/product/x-P1"
    assert product_page_path("P1", "https://www.sephora.com/ca/en/product/x-P1?skuId=2") == (
        "/ca/en/product/x-P1"
    )
    assert product_page_path("P1") == "/ca/en/product/P1"


# --- client ----------------------------------------------------------------------------


def test_is_blocked():
    assert is_blocked(response(403, BLOCK_PAGE, server="AkamaiGHost"))
    assert is_blocked(response(200, BLOCK_PAGE, server="AkamaiGHost"))
    assert is_blocked(response(429))
    assert not is_blocked(response(200, "<html>ok</html>"))


class FakeSession(requests.Session):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def make_client(responses, **kwargs):
    sleeps = []
    client = SephoraClient(session=FakeSession(responses), sleep=sleeps.append, **kwargs)
    return client, sleeps


def test_client_backs_off_then_stops_after_consecutive_blocks():
    blocked = response(403, BLOCK_PAGE, server="AkamaiGHost")
    client, _ = make_client([blocked, blocked, blocked], delay=1, max_consecutive_blocks=3)
    assert client.get("/ca/en/a") is None
    assert client.get("/ca/en/b") is None
    with pytest.raises(BlockedError):
        client.get("/ca/en/c")
    assert client.stats.blocked == 3


def test_client_resets_block_count_after_success_and_uses_locale():
    blocked = response(403, BLOCK_PAGE, server="AkamaiGHost")
    client, _ = make_client([blocked, response(200, "ok"), blocked, response(200, "ok")])
    assert client.get("/ca/en/a") is None
    assert client.get("/ca/en/b") is not None
    assert client.get("/ca/en/c") is None
    assert client.get("/ca/en/d") is not None
    assert client.stats.ok == 2
    assert client.session.cookies.get("site_locale") == "ca"
    assert client.session.urls[0] == "https://www.sephora.com/ca/en/a"


def test_client_refuses_non_canadian_pages():
    client, _ = make_client([response(200, "ok", country="US")])
    with pytest.raises(NotCanadaError):
        client.get("/ca/en/")


def test_client_404_is_not_a_block():
    client, _ = make_client([response(404, "gone"), response(404, "gone"), response(404, "gone")])
    for _ in range(3):
        assert client.get("/ca/en/product/P0") is None
    assert client.stats.not_found == 3


# --- database + CLI --------------------------------------------------------------------


def test_db_upserts_are_idempotent(tmp_path):
    db = tmp_path / "t.db"
    brands = [{"brand_name": "AAVRANI", "brand_url": "/ca/en/brand/aavrani"}]
    with db_util.connect(db) as conn:
        db_util.upsert_brands(conn, brands)
        db_util.upsert_brands(conn, brands)
        ((brand_id, _, _),) = db_util.get_brands(conn, "aavrani")
        products = [{"product_code": "P513304", "product_url": "/product/x-P513304"}]
        db_util.upsert_products(conn, brand_id, products)
        db_util.upsert_products(conn, brand_id, products)
        assert db_util.get_products(conn, "AAVRANI") == [("P513304", "/product/x-P513304")]

        run_id = db_util.start_run(conn, "details", "CA")
        rows = product_records(make_product())
        db_util.insert_product_details(conn, run_id, rows)
        db_util.insert_product_details(conn, run_id, rows)
        count = conn.execute("SELECT count(*) FROM product_details").fetchone()[0]
        assert count == 5
        assert db_util.fetched_product_codes(conn, run_id) == {"P427517"}
        assert db_util.latest_open_run(conn, "details") == run_id


def test_cli_details_stage_end_to_end(tmp_path, monkeypatch, capsys):
    db = tmp_path / "t.db"
    with db_util.connect(db) as conn:
        db_util.upsert_brands(conn, [{"brand_name": "Benefit", "brand_url": "/ca/en/brand/b"}])
        ((brand_id, _, _),) = db_util.get_brands(conn)
        db_util.upsert_products(
            conn,
            brand_id,
            [
                {"product_code": "P427517", "product_url": "/product/bad-gal-bang-mascara-P427517"},
                {"product_code": "P999", "product_url": "/product/gone-P999"},
            ],
        )

    pages = {
        "/ca/en/product/bad-gal-bang-mascara-P427517": response(
            200, page({"page": {"product": make_product()}})
        ),
        "/ca/en/product/gone-P999": response(404, "gone"),
    }
    monkeypatch.setattr(
        SephoraClient, "get", lambda self, path: pages[path] if pages[path].ok else None
    )
    monkeypatch.chdir(tmp_path)
    main(["scrape", "details", "--db", str(db), "--delay", "0"])

    out = capsys.readouterr().out
    assert "sku_rows=5" in out
    with db_util.connect(db) as conn:
        prices = conn.execute("SELECT DISTINCT price, currency FROM product_details").fetchall()
    assert prices == [("$39.00", "CAD")]


# --- real pages saved by the probe (tests/fixtures/sephora) -----------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "sephora"


def fixture_html(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.html.gz").read_bytes()).decode()


def test_real_brands_list_has_all_brands():
    brands = parse_brands(fixture_html("brands_list"))
    assert len(brands) == 272
    assert {
        "brand_name": "Benefit Cosmetics",
        "brand_url": "/ca/en/brand/benefit-cosmetics",
    } in brands
    # Sub-pages linked from the menu (e.g. /brand/sephora-collection/skincare) are not brands.
    assert all(b["brand_url"].count("/") == 4 for b in brands)


def test_real_product_page_single_sku():
    product, rows = parse_product_page(fixture_html("product_page_P513304"))
    assert product is not None
    assert [(r["sku_id"], r["price"], r["size"]) for r in rows] == [
        ("2797074", "$51.00", "8.4 oz / 250 ml")
    ]
    assert rows[0]["brand_name"] == "AAVRANI"
    assert rows[0]["category_name"] == "Shampoo --- Shampoo & Conditioner --- Hair"


def test_real_product_page_every_shade_and_size():
    _, rows = parse_product_page(fixture_html("product_page_P427517"))
    by_sku = {r["sku_id"]: r for r in rows}
    assert len(rows) == 5
    assert by_sku["2031649"]["price"] == "$39.00"
    assert by_sku["2031813"]["price"] == "$22.00"  # the mini
    assert "Mini" in by_sku["2031813"]["size"]
    assert {r["display_name"] for r in rows} == {"BADgal BANG! Volumizing 36-Hour Longwear Mascara"}
    assert {r["currency"] for r in rows} == {"CAD"}


def test_brand_filter_accepts_display_or_url_name(tmp_path):
    with db_util.connect(tmp_path / "t.db") as conn:
        db_util.upsert_brands(
            conn,
            [{"brand_name": "Benefit Cosmetics", "brand_url": "/ca/en/brand/benefit-cosmetics"}],
        )
        assert len(db_util.get_brands(conn, "benefit cosmetics")) == 1
        assert len(db_util.get_brands(conn, "Benefit-Cosmetics")) == 1
        assert db_util.get_brands(conn, "benefit") == []


def test_cli_seed_loads_products_from_csv(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "t.db"
    csv = tmp_path / "old.csv"
    csv.write_text(
        "product_code,brand_name,target_url,price\n"
        "P427517,Benefit Cosmetics,/product/bad-gal-bang-mascara-P427517,39\n"
        "P427517,Benefit Cosmetics,/product/bad-gal-bang-mascara-P427517,22\n"
        "P1,Gone Brand,/product/gone-P1,10\n"
    )
    with db_util.connect(db) as conn:
        db_util.upsert_brands(
            conn,
            [{"brand_name": "Benefit Cosmetics", "brand_url": "/ca/en/brand/benefit-cosmetics"}],
        )
    main(["scrape", "seed", "--db", str(db), "--csv", str(csv)])
    out = capsys.readouterr().out
    assert "products loaded" in out and ": 2 from 2 brands" in out
    assert "Gone Brand" in out
    with db_util.connect(db) as conn:
        assert db_util.get_products(conn, "benefit-cosmetics") == [
            ("P427517", "/product/bad-gal-bang-mascara-P427517")
        ]
        assert len(db_util.get_products(conn)) == 2


def test_cli_details_without_products_does_not_open_a_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "t.db"
    with pytest.raises(SystemExit):
        main(["scrape", "details", "--db", str(db)])
    with db_util.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM scrape_runs").fetchone()[0] == 0


def test_cli_details_records_every_page_resumes_and_exports(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "t.db"
    with db_util.connect(db) as conn:
        db_util.upsert_products(
            conn,
            None,
            [
                {"product_code": "P427517", "product_url": "/product/bad-gal-bang-mascara-P427517"},
                {"product_code": "P2", "product_url": "/product/discontinued-P2"},
                {"product_code": "P3", "product_url": "/product/gone-P3"},
            ],
        )

    no_data = response(200, "<html><title>Search Results | Sephora</title></html>")
    no_data.url = "https://www.sephora.com/ca/en/search?keyword=discontinued"
    pages = {
        "/ca/en/product/bad-gal-bang-mascara-P427517": response(
            200, page({"page": {"product": make_product()}})
        ),
        "/ca/en/product/discontinued-P2": no_data,
        "/ca/en/product/gone-P3": response(404, "gone"),
    }
    calls = []

    def fake_get(self, path):
        calls.append(path)
        r = pages[path]
        self.last_status = r.status_code
        return r if r.ok else None

    monkeypatch.setattr(SephoraClient, "get", fake_get)
    main(["scrape", "details", "--db", str(db), "--delay", "0"])
    out = capsys.readouterr().out
    assert "{'no_data': 1, 'not_found': 1, 'ok': 1}" in out
    assert (tmp_path / "data/probe/no_data/P2.html.gz").exists()
    with db_util.connect(db) as conn:
        fetch = conn.execute(
            "SELECT status, final_url, title FROM product_fetches WHERE product_code = 'P2'"
        ).fetchone()
        run_finished = conn.execute("SELECT finished_at FROM scrape_runs").fetchone()[0]
    assert fetch == ("no_data", no_data.url, "Search Results | Sephora")
    assert run_finished is not None  # every product was checked

    calls.clear()
    main(["scrape", "details", "--db", str(db), "--delay", "0"])  # new run: fetches again
    assert len(calls) == 3

    main(["export", "--db", str(db), "--run", "1"])
    out = capsys.readouterr().out
    assert "_run1_skus.csv.gz (5 rows)" in out
    assert "_run1_pages.csv.gz (3 rows)" in out


# --- sitemaps --------------------------------------------------------------------------

URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url><loc>https://www.sephora.com/product/bad-gal-bang-mascara-P427517</loc>
    <xhtml:link rel="alternate" hreflang="en-CA"
      href="https://www.sephora.com/ca/en/product/bad-gal-bang-mascara-P427517"/></url>
  <url><loc>https://www.sephora.com/product/aavrani-jelly-shampoo-P513304</loc></url>
  <url><loc>https://www.sephora.com/product/bad-gal-bang-mascara-P427517?skuId=2031649</loc></url>
  <url><loc>https://www.sephora.com/shop/makeup-cosmetics</loc></url>
</urlset>"""


def test_parse_sitemap_urlset():
    sitemap = parse_sitemap(URLSET)
    assert sitemap.sitemaps == []
    assert sitemap.products == [
        {
            "product_code": "P427517",
            "product_url": "https://www.sephora.com/product/bad-gal-bang-mascara-P427517",
        },
        {
            "product_code": "P513304",
            "product_url": "https://www.sephora.com/product/aavrani-jelly-shampoo-P513304",
        },
    ]
    assert product_page_path("P427517", sitemap.products[0]["product_url"]) == (
        "/ca/en/product/bad-gal-bang-mascara-P427517"
    )


def test_parse_sitemap_index_and_gzip():
    index = b"""<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://www.sephora.com/products-sitemap_1.xml.gz</loc></sitemap>
      <sitemap><loc>https://www.sephora.com/products-sitemap_2.xml.gz</loc></sitemap>
    </sitemapindex>"""
    parsed = parse_sitemap(gzip.compress(index))
    assert parsed.sitemaps == [
        "https://www.sephora.com/products-sitemap_1.xml.gz",
        "https://www.sephora.com/products-sitemap_2.xml.gz",
    ]
    assert parsed.products == []
    assert len(parse_sitemap(gzip.compress(URLSET)).products) == 2


def test_cli_sitemap_from_saved_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "t.db"
    child = tmp_path / "products-1.xml.gz"
    child.write_bytes(gzip.compress(URLSET))
    index = tmp_path / "products-sitemap.xml"
    index.write_text(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<sitemap><loc>{child}</loc></sitemap></sitemapindex>"
    )
    with db_util.connect(db) as conn:
        db_util.upsert_brands(
            conn, [{"brand_name": "AAVRANI", "brand_url": "/ca/en/brand/aavrani"}]
        )
        ((brand_id, _, _),) = db_util.get_brands(conn)
        db_util.upsert_products(
            conn, brand_id, [{"product_code": "P513304", "product_url": "/product/old-P513304"}]
        )

    main(["scrape", "sitemap", "--db", str(db), "--sitemap", str(index)])
    out = capsys.readouterr().out
    assert "products in sitemap: 2 (1 new, 1 already known)" in out
    with db_util.connect(db) as conn:
        # the known product keeps its brand link
        assert [code for code, _ in db_util.get_products(conn, "aavrani")] == ["P513304"]
        assert len(db_util.get_products(conn)) == 2


def test_details_checks_only_latest_sitemap_products(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "t.db"
    sitemap = tmp_path / "products-sitemap.xml"
    sitemap.write_bytes(URLSET)  # lists P427517 and P513304
    with db_util.connect(db) as conn:
        db_util.upsert_products(
            conn, None, [{"product_code": "P1", "product_url": "/product/old-jan-2025-P1"}]
        )
    main(["scrape", "sitemap", "--db", str(db), "--sitemap", str(sitemap)])

    checked = []

    def fake_get(self, path):
        checked.append(path)
        self.last_status = 404
        return None

    monkeypatch.setattr(SephoraClient, "get", fake_get)
    main(["scrape", "details", "--db", str(db), "--delay", "0"])
    assert sorted(checked) == [
        "/ca/en/product/aavrani-jelly-shampoo-P513304",
        "/ca/en/product/bad-gal-bang-mascara-P427517",
    ]
    assert "products checked in this run so far: 2/2" in capsys.readouterr().out

    checked.clear()
    main(["scrape", "details", "--db", str(db), "--delay", "0", "--new-run", "--all-products"])
    assert len(checked) == 3


def test_old_database_gets_sitemap_column(tmp_path):
    db = tmp_path / "old.db"
    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE products (product_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id INTEGER,"
        " product_url TEXT, product_code TEXT NOT NULL UNIQUE, created_at TIMESTAMP)"
    )
    conn.execute("INSERT INTO products (product_url, product_code) VALUES ('/product/x-P1', 'P1')")
    conn.commit()
    conn.close()
    with db_util.connect(db) as conn:
        assert not db_util.has_sitemap(conn)
        assert db_util.get_products(conn) == [("P1", "/product/x-P1")]
