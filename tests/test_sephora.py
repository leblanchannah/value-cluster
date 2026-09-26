import gzip
import json
from pathlib import Path

import pytest
import requests

from value_cluster import db_util
from value_cluster.cli import main
from value_cluster.sephora import (
    BlockedError,
    NotCanadaError,
    SephoraClient,
    extract_linkstore,
    is_blocked,
    normalize_brand_url,
    parse_brand_products,
    parse_brands,
    parse_product_page,
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
