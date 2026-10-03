import pytest

from shelf_life.parsing import (
    clean_product_rating,
    parse_size,
    parse_volume_string,
    pre_parse_product_size_clean,
    shorthand_numeric_conversion,
    split_product_multiplier,
    split_sale_and_full_price,
    strip_non_numeric,
)


# amount1, unit1, amount2, unit2, trailing_text
@pytest.mark.parametrize(
    "size_value, parsed_size_data",
    [
        ("helo", (None, None, None, None, "helo")),
        ("1.0 oz 30 ml", ("1.0", "oz", "30", "ml", "")),
        ("1.0 oz     30 ml", ("1.0", "oz", "30", "ml", "")),
        ("1 oz  30 ml", ("1", "oz", "30", "ml", "")),
        ("1.0 oz 30.0 ml", ("1.0", "oz", "30.0", "ml", "")),
        ("0.5oz  15ml", ("0.5", "oz", "15", "ml", "")),
        ("0.5 oz  15 ml", ("0.5", "oz", "15", "ml", "")),
        ("0.5 oz  0.5 ml", ("0.5", "oz", "0.5", "ml", "")),
        ("1 floz 30ml", ("1", "floz", "30", "ml", "")),
        ("1 floz 30ml trailing text", ("1", "floz", "30", "ml", "trailing text")),
        ("not proper pattern", (None, None, None, None, "not proper pattern")),
        (
            "not proper pattern but fivewords",
            (None, None, None, None, "not proper pattern but fivewords"),
        ),
        ("10 dollars 9.0 rupis", ("10", "dollars", "9.0", "rupis", "")),
        ("1.0 floz 30 mg", ("1.0", "floz", "30", "mg", "")),
        ("1.0 oz 30 kg", ("1.0", "oz", "30", "kg", "")),
        ("1.0 floz 30 l", ("1.0", "floz", "30", "l", "")),
        ("0.0176 oz0.5 g", ("0.0176", "oz", "0.5", "g", "")),
    ],
)
def test_parse_volume_string(size_value, parsed_size_data):
    assert parse_volume_string(size_value) == parsed_size_data


@pytest.mark.parametrize(
    "size_value, cleaned_size_data",
    [
        ("helo", "helo"),
        ("1.0 oz 30 ml", "1.0 oz 30 ml"),
        ("1 x 1 oz 30 ml", "1 x 1 oz 30 ml"),
        ("4 x .25 oz 30 ml", "4 x0.25 oz 30 ml"),
        ("      1.0 oz 30 ml", "1.0 oz 30 ml"),
        ("1.0 oz 30 ml      ", "1.0 oz 30 ml"),
        ("1.0 oz    30 ml      ", "1.0 oz    30 ml"),
        ("1 oz  30 ml", "1 oz  30 ml"),
        ("1.0 oz 30.0 ml", "1.0 oz 30.0 ml"),
        (".5oz  15ml", "0.5oz  15ml"),
        (".5 oz 15 ml", "0.5 oz 15 ml"),
        (" .5 oz 15 ml", "0.5 oz 15 ml"),
        (".5 oz  .5 ml", "0.5 oz 0.5 ml"),
        ("1 oz. 30ml", "1 oz 30ml"),
        ("1 fl oz 30ml", "1 floz 30ml"),
        ("1 fl. oz 30ml", "1 floz 30ml"),
        ("    ", None),
        ("", None),
    ],
)
def test_pre_parse_product_size_clean(size_value, cleaned_size_data):
    assert pre_parse_product_size_clean(size_value) == cleaned_size_data


@pytest.mark.parametrize(
    "size_value, cleaned_size_data",
    [
        ("1 x 1 oz 30 ml", ["1", " 1 oz 30 ml"]),
        ("4 x .25 oz 30 ml", ["4", " .25 oz 30 ml"]),
        ("4 x.25 oz 30 ml", ["4", ".25 oz 30 ml"]),
        ("4 x 0.25 ml", ["4", " 0.25 ml"]),
        ("1 x2ml", ["1", "2ml"]),
        ("10 ml", [None, "10 ml"]),
        (None, [None, None]),
    ],
)
def test_split_product_multiplier(size_value, cleaned_size_data):
    assert split_product_multiplier(size_value) == cleaned_size_data


@pytest.mark.parametrize(
    "string_input, numeric_output",
    [
        ("10K", 10000.0),
        ("1K", 1000.0),
        ("2.4K", 2400.0),
        ("9.9K", 9900.0),
        ("999", 999.0),
        ("0.00", 0.0),
        ("10M", 10000000.0),
        ("1.2M", 1200000.0),
        ("", None),
        ("K", None),
        ("M", None),
    ],
)
def test_shorthand_numeric_conversion(string_input, numeric_output):
    assert shorthand_numeric_conversion(string_input) == numeric_output


@pytest.mark.parametrize(
    "rating_as_width, numeric_rating",
    [
        ("width:100.00%", 5.0),
        ("width:80.00%", 4.0),
        ("width:20.00%", 1.0),
        ("width:0.00%", 0.0),
        ("width:120.00%", 6.0),
        ("", None),
    ],
)
def test_clean_product_rating(rating_as_width, numeric_rating):
    assert clean_product_rating(rating_as_width) == numeric_rating


@pytest.mark.parametrize(
    "prices_as_list, prices_to_split",
    [
        (["$100.00"], ["$100.00", "$100.00"]),
        (["$45.00", "$60.00"], ["$45.00", "$60.00"]),
        (None, ["", ""]),
        ([""], ["", ""]),
    ],
)
def test_split_sale_and_full_price(prices_as_list, prices_to_split):
    assert split_sale_and_full_price(prices_as_list) == prices_to_split


@pytest.mark.parametrize(
    "input_str, output_str",
    [("ITEM: 1234", "1234"), ("item: 0000", "0000"), ("1a2d3", "123"), ("", None), (None, None)],
)
def test_strip_non_numeric(input_str, output_str):
    assert strip_non_numeric(input_str) == output_str


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
        ("", "unknown", [], None),
    ],
)
def test_parse_size(size_value, phase, volumes, additional_info):
    assert parse_size(size_value) == {
        "phase": phase,
        "parsed_volumes": volumes,
        "additional_info": additional_info,
    }
