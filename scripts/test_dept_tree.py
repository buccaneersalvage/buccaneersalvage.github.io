#!/usr/bin/env python3
"""Drift-check: store.js TYPE_PARENT vs dept_tree.py, plus catalog labels."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dept_tree import TYPE_PARENT, dept_label, item_ebay_tree, item_store_tree  # noqa: E402


def test_store_js_type_parent_lockstep():
    js = (HUB / "store.js").read_text(encoding="utf-8")
    block = re.search(r"const TYPE_PARENT = \[(.*?)\];", js, re.S)
    assert block, "TYPE_PARENT missing from store.js"
    js_pats = re.findall(r"/([^/\n]+)/i", block.group(1))
    py_pats = [p for p, _ in TYPE_PARENT]
    assert js_pats == py_pats, (js_pats, py_pats)


def _named(items, needle: str) -> dict:
    needle = needle.lower()
    hit = next((i for i in items if needle in (i.get("name") or "").lower()), None)
    assert hit, needle
    return hit


def test_catalog_dept_labels():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    items = cat["items"]
    by = {i["id"]: i for i in items}
    assert dept_label(_named(items, "wix 33063")) == "Air & Fuel"
    assert dept_label(by["W3LT2QSYY5C2YYPE5PYLATNO"]) == "Mobility"
    assert dept_label(by["EZW5JY5PWZJO4PH5R2TQGYC3"]) == "Material Handling"
    assert dept_label(by["7CESL5VZLPSRKJGWUFCHL5R5"]) == "Electric Motors"
    assert dept_label(_named(items, "ap exhaust 8689")) == "Exhaust"
    assert dept_label(_named(items, "borg warner s-931")) == "Interior"
    assert dept_label(_named(items, "dorman 55114")) == "Engines"
    labels = {dept_label(i) for i in items}
    assert "Filter" not in labels
    assert "Brake hardware" not in labels
    assert "Vintage" not in labels
    assert "Parts" not in labels


def test_electric_motors_from_square_category_not_brand():
    """Shop motor dept label is Square category, not a Craftsman title blob."""
    for pat, _ in TYPE_PARENT:
        assert "craftsman" not in pat.lower()
    motor = {
        "id": "TESTELECTRICMOTOR0001",
        "name": "Baldor 1 HP Shop Motor 1725 RPM 115V",
        "category": "electric-motors",
        "price": 1,
        "ebay_category": "",
    }
    assert dept_label(motor) == "Electric Motors"
    assert item_ebay_tree(motor)["parent"] == "Electric Motors"
    assert item_store_tree(motor)["parent"] == "Tools"
    assert item_store_tree(motor)["sub"] == "Electric Motors"
    py = (HUB / "scripts/dept_tree.py").read_text(encoding="utf-8").lower()
    js = (HUB / "store.js").read_text(encoding="utf-8").lower()
    assert "craftsman" not in py
    assert "craftsman" not in js


def test_store_parent_labels():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    by = {i["id"]: i for i in cat["items"]}
    assert item_store_tree(by["W3LT2QSYY5C2YYPE5PYLATNO"])["parent"] == "Vintage & Collectibles"
    assert item_store_tree(by["7CESL5VZLPSRKJGWUFCHL5R5"])["parent"] == "Tools"
    assert item_store_tree(by["7CESL5VZLPSRKJGWUFCHL5R5"])["sub"] == "Electric Motors"
    assert item_store_tree(by["EZW5JY5PWZJO4PH5R2TQGYC3"])["parent"] == "Industrial & Warehouse"
    assert item_store_tree(by["5LLWTR3B27YDLV6ZR6XMBPWL"])["parent"] == "Truck Air Springs"
    assert item_store_tree(by["BYO4CA2ORO6PIIHKJ6BAJ7Z5"])["parent"] == "Auto Parts & Accessories"
    coleman = item_store_tree(by["W54WMQYKJ4OJRLJQRQSYYXHV"])
    assert coleman["parent"] == "Sporting Goods"
    assert coleman["sub"] == "Camping Stoves"
    tile = item_store_tree(by["76ZJG6NNDY73XL2QXHGWC56L"])
    assert tile["parent"] == "Tools"
    assert tile["sub"] == "Cutting Tools"
    scope = item_store_tree(by["W4MUULZLATJKYPEY6SEKNP25"])
    assert scope["parent"] == "Sporting Goods"
    assert scope["sub"] == "Rifle Scopes"


if __name__ == "__main__":
    test_store_js_type_parent_lockstep()
    test_catalog_dept_labels()
    test_electric_motors_from_square_category_not_brand()
    test_store_parent_labels()
    print("dept_tree ok")
