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
