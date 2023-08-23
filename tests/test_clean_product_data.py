import pytest
import sys
sys.path.insert(0,'../src')
from clean_product_data import (parse_volume_string, pre_parse_product_size_clean, split_product_multiplier,
                                shorthand_numeric_conversion, clean_product_rating, split_sale_and_full_price)

# amount1, unit1, amount2, unit2, trailing_text
@pytest.mark.parametrize("size_value, parsed_size_data", [
    ("helo", (None, None, None, None, 'helo')),
    ('1.0 oz 30 ml', ("1.0", "oz", "30", "ml", "")),
    ('1.0 oz     30 ml', ("1.0", "oz", "30", "ml", "")),
    ("1 oz  30 ml", ("1", "oz", "30", "ml", "")),
    ("1.0 oz 30.0 ml", ("1.0", "oz", "30.0", "ml", "")),
    ("0.5oz  15ml", ("0.5", "oz", "15", "ml","")),
    ("0.5 oz  15 ml", ("0.5", "oz", "15", "ml", "")),
    ("0.5 oz  0.5 ml", ("0.5", "oz", "0.5", "ml", "")),
    ("1 floz 30ml", ("1","floz","30","ml","")),
    ("1 floz 30ml trailing text", ("1","floz","30","ml","trailing text")),
    ("not proper pattern", (None, None, None, None, 'not proper pattern')),
    ("not proper pattern but fivewords", (None, None, None, None, "not proper pattern but fivewords")),
    ("10 dollars 9.0 rupis", ("10","dollars","9.0","rupis","")),
    ('1.0 floz 30 mg', ("1.0", "floz", "30", "mg", "")),
    ('1.0 oz 30 kg', ("1.0", "oz", "30", "kg", "")),
    ('1.0 floz 30 l', ("1.0", "floz", "30", "l", "")),
    ('0.0176 oz0.5 g', ("0.0176","oz","0.5","g",""))
])
def test_parse_volume_string(size_value, parsed_size_data):
    assert parse_volume_string(size_value) == parsed_size_data


@pytest.mark.parametrize("size_value, cleaned_size_data", [
    ("helo", "helo"),
    ('1.0 oz 30 ml', "1.0 oz 30 ml"),
    ('1 x 1 oz 30 ml', "1 x 1 oz 30 ml"),
    ('4 x .25 oz 30 ml', "4 x0.25 oz 30 ml"),
    ('      1.0 oz 30 ml', "1.0 oz 30 ml"),
    ('1.0 oz 30 ml      ', "1.0 oz 30 ml"),
    ('1.0 oz    30 ml      ', "1.0 oz    30 ml"),
    ("1 oz  30 ml", "1 oz  30 ml"),
    ("1.0 oz 30.0 ml", "1.0 oz 30.0 ml"),
    (".5oz  15ml", "0.5oz  15ml"),
    (".5 oz 15 ml", "0.5 oz 15 ml"),
    (" .5 oz 15 ml", "0.5 oz 15 ml"),
    (".5 oz  .5 ml", "0.5 oz 0.5 ml"),
    ("1 oz. 30ml", "1 oz 30ml"),
    ("1 fl oz 30ml", "1 floz 30ml"),
    ("1 fl. oz 30ml", "1 floz 30ml"),
    ("    ",None),
    ("",None)
])
def test_pre_parse_product_size_clean(size_value, cleaned_size_data):
    assert pre_parse_product_size_clean(size_value) == cleaned_size_data


@pytest.mark.parametrize("size_value, cleaned_size_data", [
    ('1 x 1 oz 30 ml', ["1"," 1 oz 30 ml"]),
    ('4 x .25 oz 30 ml', ["4", " .25 oz 30 ml"]),
    ('4 x.25 oz 30 ml', ["4",".25 oz 30 ml"]),
    ('4 x 0.25 ml', ['4',' 0.25 ml']),
    ('1 x2ml', ['1','2ml']),
    ('10 ml', [None,'10 ml']),
    (None, [None, None])
])
def test_split_product_multiplier(size_value, cleaned_size_data):
    assert split_product_multiplier(size_value) == cleaned_size_data


@pytest.mark.parametrize("string_input, numeric_output", [
    ("10K", 10000.0),
    ("1K", 1000.0),
    ("2.4K", 2400.0),
    ("9.9K", 9900.0),
    ("999", 999.0),
    ("0.00", 0.0),
    ("10M", 10000000.0),
    ("1.2M", 1200000.0),
    ("", None),
    ("K",None),
    ("M",None)
])
def test_shorthand_numeric_conversion(string_input, numeric_output):
    assert shorthand_numeric_conversion(string_input) == numeric_output


@pytest.mark.parametrize("rating_as_width, numeric_rating", [
    ("width:100.00%", 5.0),
    ("width:80.00%", 4.0),
    ("width:20.00%", 1.0),
    ("width:0.00%", 0.0),
    ("width:120.00%", 6.0),
    ("", None)
])
def test_clean_product_rating(rating_as_width, numeric_rating):
    assert clean_product_rating(rating_as_width) == numeric_rating


@pytest.mark.parametrize("prices_as_list, prices_to_split", [
    (["$100.00"], ["$100.00","$100.00"]),
    (["$45.00","$60.00"], ["$45.00","$60.00"]),
    (None, ["",""]),
    ([""], ["",""])
])
def test_split_sale_and_full_price(prices_as_list, prices_to_split):
    assert split_sale_and_full_price(prices_as_list) == prices_to_split