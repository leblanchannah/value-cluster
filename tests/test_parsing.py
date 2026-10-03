import pandas as pd
import pytest

from shelf_life.parsing import parse_price, parse_size
from shelf_life.preprocessing import preprocess, size_columns


@pytest.mark.parametrize(
    "price, expected",
    [("$43.50", 43.5), (" $1,200.00", 1200.0), ("", None), (None, None)],
)
def test_parse_price(price, expected):
    assert parse_price(price) == expected


def _vols(*pairs):
    return [{"value": value, "unit": unit} for value, unit in pairs]


@pytest.mark.parametrize(
    "size_value, phase, volumes, additional_info",
    [
        ("0.32 oz / 9 g", "solid", _vols((0.32, "oz"), (9, "g")), None),
        (".1 / 3g", "solid", _vols((0.1, None), (3, "g")), None),
        (".27 oz/8 mL", "both", _vols((0.27, "oz"), (8, "mL")), None),
        ("1.7 oz/ 50 mL", "both", _vols((1.7, "oz"), (50, "mL")), None),
        ("1.01 oz/ 30 ml", "both", _vols((1.01, "oz"), (30, "mL")), None),
        ("5 oz/150 ml Refill", "both", _vols((5, "oz"), (150, "mL")), "Refill"),
        ("0.003 oz / fillsizesequence:1", "solid", _vols((0.003, "oz")), "fillsizesequence:1"),
        ("0.15 oz / 4.5 mL", "both", _vols((0.15, "oz"), (4.5, "mL")), None),
        ("0.002 / 0.08g", "solid", _vols((0.002, None), (0.08, "g")), None),
        ("0.003 oz / 0.1 g", "solid", _vols((0.003, "oz"), (0.1, "g")), None),
        ("0.14 oz/ 4.1 g", "solid", _vols((0.14, "oz"), (4.1, "g")), None),
        ("0.22 oz / 6.3 g", "solid", _vols((0.22, "oz"), (6.3, "g")), None),
        ("0.2 oz", "solid", _vols((0.2, "oz")), None),
        ("0.003 oz/ 0.085 g", "solid", _vols((0.003, "oz"), (0.085, "g")), None),
        ("1.69 oz / 50 mL", "both", _vols((1.69, "oz"), (50, "mL")), None),
        ("1.0 oz/30 mL", "both", _vols((1.0, "oz"), (30, "mL")), None),
        ("0.007 oz/ 0.2 g", "solid", _vols((0.007, "oz"), (0.2, "g")), None),
        ("0.4 oz/ 12 mL", "both", _vols((0.4, "oz"), (12, "mL")), None),
        ("0.001 Oz. / fillsizesequence:1", "solid", _vols((0.001, "oz")), "fillsizesequence:1"),
        ("1.6/50", "unknown", _vols((1.6, None), (50, None)), None),
        (".2 / 6g", "solid", _vols((0.2, None), (6, "g")), None),
        ("0.03 oz/ 2 x 0.8 g", "solid", _vols((0.03, "oz"), (0.8, "g")), "x2"),
        ("2 oz / 60 ml - 4 Month Supply", "both", _vols((2, "oz"), (60, "mL")), "4 Month Supply"),
        ("", "unknown", [], None),
    ],
)
def test_parse_size(size_value, phase, volumes, additional_info):
    assert parse_size(size_value) == {
        "phase": phase,
        "parsed_volumes": volumes,
        "additional_info": additional_info,
    }


@pytest.mark.parametrize(
    "size_value, expected",
    [
        ("1.7 fl oz / 50 mL", (None, 1.7, 50.0, None)),
        ("1 floz", (None, 1.0, 29.5735, None)),
        ("0.053 oz./1.5g", (0.053, None, None, 1.5)),
        ("0.5 L", (None, None, 500.0, None)),
        ("250 mg", (None, None, None, 0.25)),
    ],
)
def test_size_columns(size_value, expected):
    row = size_columns(size_value)
    assert (row["size_oz"], row["size_fl_oz"], row["size_ml"], row["size_g"]) == pytest.approx(
        expected
    )


def test_preprocess():
    details = pd.DataFrame(
        {
            "price": ["$30.00", "$20.00"],
            "sale_price": [None, "$15.00"],
            "size": ["1 oz / 30 mL Refill", "0.2 oz / 6 g"],
            "category_id": ["cat1 --- cat2 --- cat3", "cat9"],
            "category_name": ["Moisturizers --- Skincare", "Makeup"],
            "category_url": ["/a --- /b", "/c"],
        }
    )
    df = preprocess(details)
    assert df["price"].tolist() == [30.0, 20.0]
    assert df["sale_price"].iloc[1] == 15.0
    assert df["category_name_l1"].tolist() == ["Skincare", "Makeup"]
    assert df["category_name_l2"].iloc[0] == "Moisturizers"
    assert df["category_id_l3"].iloc[0] == "cat1"
    assert df[["category_name_l2", "category_id_l3"]].iloc[1].isna().all()
    assert df["size_info"].iloc[0] == "Refill"
    assert pd.isna(df["size_info"].iloc[1])
    assert df["price_per_ml"].iloc[0] == 1.0
    assert df["price_per_g"].iloc[1] == pytest.approx(20 / 6)
    assert pd.isna(df["price_per_g"].iloc[0])
