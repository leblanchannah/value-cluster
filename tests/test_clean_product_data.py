import pytest
import sys
sys.path.insert(0,'../src')
from clean_product_data import parse_volume_string

# amount1, unit1, amount2, unit2, trailing_text
@pytest.mark.parametrize("size_value, parsed_size_data", [
    ("helo", None),
    ('1.0 oz 30 ml', ("1.0", "oz", "30", "ml", "")),
    ("1 oz  30 ml", ("1", "oz", "30", "ml", "")),
    ("1.0 oz 30.0 ml", ("1.0", "oz", "30.0", "ml", "")),
    (".5oz  15ml", ("0.5", "oz", "15", "ml","")),
    (".5 oz  15 ml", ("0.5", "oz", "15", "ml", "")),
    (" .5 oz  15 ml", ("0.5", "oz", "15", "ml", "")),
    (".5 oz  .5 ml", ("0.5", "oz", "0.5", "ml", "")),
    ("1 oz. 30ml", ("1","oz","30","ml","")),
    ("1 fl oz 30ml", ("1","floz","30","ml","")),
    ("1 fl. oz 30ml", ("1","floz","30","ml",""))
])
def test_parse_volume_string(size_value, parsed_size_data):
    print(parse_volume_string(size_value))
    assert parse_volume_string(size_value) == parsed_size_data