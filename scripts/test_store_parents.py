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


KNOWN_STORE = {
    "carlson-brake-hardware",
    "truck-air-springs",
    "auto-parts",
    "vintage-collectibles",
    "industrial-warehouse",
    "tools",
    "home-garden",
    "sporting-goods",
    "consumer-electronics",
    "movies-tv",
    "computers-tablets-networking",
    "health-beauty",
    "toys-hobbies",
    "jewelry-watches",
    "cameras-photo",
}


def test_only_parents_on_buc():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    items = [i for i in cat["items"] if float(i.get("price") or 0) > 0]
    parents = Counter(store_tree(i)[0] for i in items)
    assert set(parents) <= KNOWN_STORE
    assert "appliance-parts" not in parents
    assert "electronics-electrical" not in parents
    assert parents["industrial-warehouse"] >= 1
    assert parents["vintage-collectibles"] >= 2
    assert parents["truck-air-springs"] >= 40
    assert parents["carlson-brake-hardware"] >= 30
    assert parents["auto-parts"] >= 150
    assert parents["home-garden"] >= 1
    assert parents["sporting-goods"] >= 1
    assert parents["tools"] >= 1
    assert sum(parents.values()) == len(items)


def test_yard_not_dumped_into_auto():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    by = {i["id"]: i for i in cat["items"]}
    assert store_tree(by["W3LT2QSYY5C2YYPE5PYLATNO"])[0] == "vintage-collectibles"  # wheelchair
    assert store_tree(by["7CESL5VZLPSRKJGWUFCHL5R5"])[0] == "tools"  # Craftsman motor
    assert store_tree(by["EZW5JY5PWZJO4PH5R2TQGYC3"])[0] == "industrial-warehouse"  # forklift
    thermo = next(i for i in cat["items"] if "33039" in (i.get("name") or ""))
    assert store_tree(thermo)[0] == "auto-parts"
    air = by["5LLWTR3B27YDLV6ZR6XMBPWL"]
    assert store_tree(air)[0] == "truck-air-springs"
    assert store_tree(by["W54WMQYKJ4OJRLJQRQSYYXHV"]) == ("sporting-goods", "camping-stoves")
    assert store_tree(by["76ZJG6NNDY73XL2QXHGWC56L"]) == ("home-garden", "cutting-tools")
    assert store_tree(by["W4MUULZLATJKYPEY6SEKNP25"]) == ("sporting-goods", "rifle-scopes")


def test_non_motors_not_dumped_in_auto():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    items = [i for i in cat["items"] if float(i.get("price") or 0) > 0]
    dumped = []
    for item in items:
        raw = (item.get("ebay_category") or "").strip()
        first = raw.split(":")[0].strip().lower() if raw else ""
        if first == "ebay motors" or not first:
            continue
        parent = store_tree(item)[0]
        if parent == "auto-parts":
            dumped.append((item["id"], item.get("name"), raw))
    assert not dumped, dumped[:8]


def test_store_js_has_ebay_store_parents():
    js = (HUB / "store.js").read_text(encoding="utf-8")
    for slug in (
        "carlson-brake-hardware",
        "truck-air-springs",
        "auto-parts",
        "vintage-collectibles",
        "industrial-warehouse",
        "tools",
        "home-garden",
        "sporting-goods",
        "consumer-electronics",
        "movies-tv",
        "computers-tablets-networking",
        "health-beauty",
        "toys-hobbies",
        "jewelry-watches",
        "cameras-photo",
    ):
        assert slug in js
    assert "isAutoBrowse" in js
    assert 'catParts[0].toLowerCase() === "ebay motors"' in js


if __name__ == "__main__":
    test_only_parents_on_buc()
    test_yard_not_dumped_into_auto()
    test_non_motors_not_dumped_in_auto()
    test_store_js_has_ebay_store_parents()
    print("test_store_parents: PASS")
