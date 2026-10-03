"""Turn scraped ``product_details`` rows into an analysis-ready table.

Run it with ``uv run shelf-life preprocess`` (latest details run -> data/processed/).
"""

import pandas as pd

from shelf_life.parsing import parse_price, parse_size

ML_PER_FL_OZ = 29.5735
CATEGORY_LEVELS = 3

# How to bring each unit to the column it's reported in: unit -> (column, multiplier).
UNIT_COLUMNS = {
    "oz": ("size_oz", 1.0),
    "fl oz": ("size_fl_oz", 1.0),
    "mL": ("size_ml", 1.0),
    "L": ("size_ml", 1000.0),
    "g": ("size_g", 1.0),
    "mg": ("size_g", 0.001),
    "kg": ("size_g", 1000.0),
}
SIZE_COLUMNS = ["size_oz", "size_fl_oz", "size_ml", "size_g"]


def split_category_chain(chain: pd.Series, name: str) -> pd.DataFrame:
    """``"Mascara --- Eye --- Makeup"`` -> ``{name}_l1="Makeup", _l2="Eye", _l3="Mascara"``."""
    levels = chain.fillna("").str.split(" --- ").apply(lambda parts: parts[::-1])
    columns = [f"{name}_l{i + 1}" for i in range(CATEGORY_LEVELS)]
    padded = levels.apply(lambda parts: (parts + [None] * CATEGORY_LEVELS)[:CATEGORY_LEVELS])
    return pd.DataFrame(padded.to_list(), columns=columns, index=chain.index).replace("", None)


def size_columns(size: str | None) -> dict:
    """One size string -> the numeric size columns plus phase and leftover text."""
    parsed = parse_size(size)
    row: dict = dict.fromkeys(SIZE_COLUMNS)
    for volume in parsed["parsed_volumes"]:
        if volume["unit"] in UNIT_COLUMNS:
            column, multiplier = UNIT_COLUMNS[volume["unit"]]
            if row[column] is None:
                row[column] = volume["value"] * multiplier
    if row["size_ml"] is None and row["size_fl_oz"] is not None:
        row["size_ml"] = row["size_fl_oz"] * ML_PER_FL_OZ
    row["size_phase"] = parsed["phase"]
    row["size_info"] = parsed["additional_info"]
    return row


def preprocess(details: pd.DataFrame) -> pd.DataFrame:
    """Clean ``product_details`` rows: numeric prices and sizes, split categories, unit prices."""
    df = details.copy()
    df["price"] = df["price"].map(parse_price)
    df["sale_price"] = df["sale_price"].map(parse_price)

    categories = [
        split_category_chain(df[f"category_{key}"], f"category_{key}")
        for key in ("id", "name", "url")
    ]
    sizes = pd.DataFrame(df["size"].map(size_columns).to_list(), index=df.index)
    df = pd.concat([df, *categories, sizes], axis=1)

    for unit in ("oz", "ml", "g"):
        df[f"price_per_{unit}"] = df["price"] / df[f"size_{unit}"]
    return df
