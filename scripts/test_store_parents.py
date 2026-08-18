#!/usr/bin/env python3
"""Hub catalog maps to eBay-store parents (only departments on Buc)."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]


def _blob(*parts: str) -> str:
    return " ".join(parts).lower()


def store_tree(item: dict) -> tuple[str, str]:
    cat = item.get("category") or ""
    name = item.get("name") or ""
    typ = item.get("ebay_type") or ""
    brand = item.get("ebay_brand") or ""
    blob = _blob(name, typ, brand, cat)

    if cat == "cycling" or re.search(r"\bmasi\b|\bbicycle\b", blob):
        return "vintage-collectibles", "vintage-sports"
    if cat == "mobility" or "wheelchair" in blob:
        return "vintage-collectibles", "household-medical"
    if cat == "electric-motors" or ("craftsman" in blob and "motor" in blob):
        return "vintage-collectibles", "vintage-tools"
    if cat == "material-handling" or "forklift" in blob:
        return "industrial-warehouse", "forklift-warehouse"
    if re.search(r"\bcarlson\b", blob):
        return "carlson-brake-hardware", "carlson"
    if cat == "air-spring" or re.search(r"air spring|rolling lobe|convoluted", blob):
        return "truck-air-springs", "air"
    return "auto-parts", "auto"


def test_only_parents_on_buc():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    items = [i for i in cat["items"] if float(i.get("price") or 0) > 0]
    parents = Counter(store_tree(i)[0] for i in items)
    assert set(parents) <= {
        "carlson-brake-hardware",
        "truck-air-springs",
        "auto-parts",
        "vintage-collectibles",
        "industrial-warehouse",
    }
    assert "appliance-parts" not in parents
    assert "electronics-electrical" not in parents
    assert parents["industrial-warehouse"] == 1
    assert parents["vintage-collectibles"] == 3
    assert parents["truck-air-springs"] >= 40
    assert parents["carlson-brake-hardware"] >= 30
    assert parents["auto-parts"] >= 150
    assert sum(parents.values()) == len(items)


def test_yard_not_dumped_into_auto():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    by = {i["id"]: i for i in cat["items"]}
    assert store_tree(by["WCSSZNLKXNQIOIHDWIOWQCGW"])[0] == "vintage-collectibles"  # Masi
    assert store_tree(by["LI7R7ABGGB2TXJQUEGHG5TRX"])[0] == "vintage-collectibles"  # wheelchair
    assert store_tree(by["7CESL5VZLPSRKJGWUFCHL5R5"])[0] == "vintage-collectibles"  # Craftsman
    assert store_tree(by["EZW5JY5PWZJO4PH5R2TQGYC3"])[0] == "industrial-warehouse"  # forklift
    thermo = next(i for i in cat["items"] if "33039" in (i.get("name") or ""))
    assert store_tree(thermo)[0] == "auto-parts"
    air = by["R6VO2MARXN7GRGTMXVGABLHT"]
    assert store_tree(air)[0] == "truck-air-springs"


def test_store_js_has_ebay_store_parents():
    js = (HUB / "store.js").read_text(encoding="utf-8")
    for slug in (
        "carlson-brake-hardware",
        "truck-air-springs",
        "auto-parts",
        "vintage-collectibles",
        "industrial-warehouse",
    ):
        assert slug in js
    assert "isAutoBrowse" in js


if __name__ == "__main__":
    test_only_parents_on_buc()
    test_yard_not_dumped_into_auto()
    test_store_js_has_ebay_store_parents()
    print("test_store_parents: PASS")
