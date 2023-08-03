import pytest
import sys
sys.path.insert(0,'../src')
from clean_product_data import parse_volume_string, pre_parse_product_size_clean

# amount1, unit1, amount2, unit2, trailing_text
@pytest.mark.parametrize("size_value, parsed_size_data", [
    ("helo", None),
    ('1.0 oz 30 ml', ("1.0", "oz", "30", "ml", "")),
    ('1.0 oz     30 ml', ("1.0", "oz", "30", "ml", "")),
    ("1 oz  30 ml", ("1", "oz", "30", "ml", "")),
    ("1.0 oz 30.0 ml", ("1.0", "oz", "30.0", "ml", "")),
    ("0.5oz  15ml", ("0.5", "oz", "15", "ml","")),
    ("0.5 oz  15 ml", ("0.5", "oz", "15", "ml", "")),
    ("0.5 oz  0.5 ml", ("0.5", "oz", "0.5", "ml", "")),
    ("1 floz 30ml", ("1","floz","30","ml","")),
    ("1 floz 30ml trailing text", ("1","floz","30","ml","trailing text"))
])
def test_parse_volume_string(size_value, parsed_size_data):
    assert parse_volume_string(size_value) == parsed_size_data

@pytest.mark.parametrize("size_value, cleaned_size_data", [
    ("helo", "helo"),
    ('1.0 oz 30 ml', "1.0 oz 30 ml"),
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
    ("1 fl. oz 30ml", "1 floz 30ml")
])
def test_pre_parse_product_size_clean(size_value, cleaned_size_data):
    assert pre_parse_product_size_clean(size_value) == cleaned_size_data
