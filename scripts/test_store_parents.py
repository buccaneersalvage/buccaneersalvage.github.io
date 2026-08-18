#!/usr/bin/env python3
"""Hub catalog maps to eBay-store parents (only departments on Buc)."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dept_tree import item_store_tree  # noqa: E402


def store_tree(item: dict) -> tuple[str, str]:
    t = item_store_tree(item)
    return t["parentSlug"], t["subSlug"]


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
