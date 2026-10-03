"""Pure helpers for turning Sephora product fields into numbers (prices, sizes)."""

import re


def parse_price(price):
    """``"$43.50"`` -> ``43.5``; empty or missing -> ``None``."""
    if price is None:
        return None
    text = str(price).replace("$", "").replace(",", "").strip()
    return float(text) if text else None


# Canonical spelling for each unit we recognise (keys are lowercase).
SIZE_UNITS = {
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
    [\s\-\u2013,]*(?P<rest>.*?)\s*$
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
