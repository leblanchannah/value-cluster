"""Pure helpers for parsing Sephora product text (sizes, counts, ratings, prices).

Originally part of the 2023 cleaning pipeline (legacy/clean_product_data.py).
"""

import re


def shorthand_numeric_conversion(count_val):
    """
    amount of loves or reviews is in format 3.2K or 1.1M for example
    """
    if count_val == "":
        return None
    if "K" in count_val:
        count_val = count_val.replace("K", "")
        if count_val != "":
            return float(count_val) * 1000
    elif "M" in count_val:
        count_val = count_val.replace("M", "")
        if count_val != "":
            return float(count_val) * 1000000
    else:
        return float(count_val)


def clean_product_rating(rating):
    """
    Expects format "Width: %00.00"
    puts rating on scale of 0-5, although no products have score < 1
    """
    if rating:
        rating = rating.replace("width:", "")
        rating = rating.replace("%", "")
        rating = float(rating) / 100 * 5
        return rating
    return None


def pre_parse_product_size_clean(input_string):
    """ """
    input_string = input_string.strip()
    if len(input_string) < 1:
        return None
    if input_string[0] == ".":
        input_string = "0" + input_string
    input_string = input_string.replace(" .", "0.")
    input_string = input_string.replace("fl oz", "floz")
    input_string = input_string.replace("fl. oz", "floz")
    input_string = input_string.replace("oz.", "oz")
    return input_string


def parse_volume_string(input_string):
    r"""
    volume formatted like "misc string amount_a unit_a \ amount_b unit_b misc text"
    """
    if not input_string:
        return None
    pattern = r"(?:(\d+(?:\.\d+)?)\s*([a-zA-Z]+))?\s*(?:(\d+(?:\.\d+)?)\s*([a-zA-Z]+))?\s*(.*)"
    match = re.match(pattern, input_string)
    if match:
        amount_a, unit_a, amount_b, unit_b, trailing_text = match.groups()
        return amount_a, unit_a, amount_b, unit_b, trailing_text
    return None, "", None, "", input_string


def parse_single_volume(input_string):
    """
    case where volume is only shown in one measurement system
    """
    pattern = r"\s*(\d+(\.\d*)?|\.\d+)\s*(\w+)\s*"
    matches = re.match(pattern, input_string)
    if matches:
        amount = matches.group(1)
        unit = matches.group(3)
        return amount, unit
    return None


def split_product_multiplier(input_string):
    """ """
    if not input_string:
        return [None, None]
    if " x" not in input_string:
        return [None, input_string]
    input_string = input_string.split(" x", 1)
    if len(input_string) == 1:
        input_string = [None, *input_string]
    return input_string


def split_sale_and_full_price(price):
    if price:
        n_prices = len(price)
        if n_prices == 1:
            return [price[0], price[0]]
        if n_prices == 2:
            return price
    return ["", ""]


def strip_non_numeric(input_str):
    """
    returns only numeric portions of string
    used to clean sku
    """
    if input_str:
        numeric_str = "".join(filter(str.isdigit, input_str))
        if numeric_str:
            return numeric_str
    return None


# Canonical spelling for each unit we recognise (keys are lowercase).
SIZE_UNITS = {
    "fl oz": "fl oz",
    "floz": "fl oz",
    "oz": "oz",
    "ml": "mL",
    "l": "L",
    "g": "g",
    "mg": "mg",
    "kg": "kg",
}

# One "/"-separated chunk of a size string: optional "2 x" multiplier, a number
# (".1", "9", "0.32"), an optional unit (with optional trailing "."), then any
# leftover text.
_SIZE_PART = re.compile(
    r"""
    ^\s*
    (?:(?P<count>\d+)\s*x\s*)?
    (?P<value>\d*\.?\d+)
    \s*
    (?:(?P<unit>fl\.?\s*oz|oz|ml|mg|kg|g|l)\b\.?)?
    \s*(?P<rest>.*?)\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _size_phase(units):
    """mL/L means the size was given as a volume ('both'); weight units mean 'solid'."""
    if units & {"mL", "L", "fl oz"}:
        return "both"
    if units & {"oz", "g", "mg", "kg"}:
        return "solid"
    return "unknown"


def parse_size(input_string):
    """
    Parse a Sephora size string like "1.7 oz/ 50 mL" or "0.03 oz/ 2 x 0.8 g".

    Returns {"phase", "parsed_volumes", "additional_info"} where parsed_volumes
    is a list of {"value": float, "unit": str | None} and additional_info holds
    any text that isn't an amount (e.g. "Refill", "fillsizesequence:1", "x2").
    """
    if not input_string or not input_string.strip():
        return {"phase": "unknown", "parsed_volumes": [], "additional_info": None}

    volumes = []
    extra = []
    for part in input_string.split("/"):
        part = part.strip()
        if not part:
            continue
        match = _SIZE_PART.match(part)
        if not match:
            extra.append(part)
            continue
        unit = match["unit"]
        if unit:
            unit = SIZE_UNITS[re.sub(r"[.\s]", "", unit.lower())]
        volumes.append({"value": float(match["value"]), "unit": unit})
        if match["count"]:
            extra.append(f"x{match['count']}")
        if match["rest"]:
            extra.append(match["rest"])

    units = {v["unit"] for v in volumes if v["unit"]}
    return {
        "phase": _size_phase(units),
        "parsed_volumes": volumes,
        "additional_info": " ".join(extra) or None,
    }
