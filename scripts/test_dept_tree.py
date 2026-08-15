#!/usr/bin/env python3
"""Drift-check: store.js TYPE_PARENT vs dept_tree.py, plus catalog labels."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dept_tree import TYPE_PARENT, dept_label  # noqa: E402


def test_store_js_type_parent_lockstep():
    js = (HUB / "store.js").read_text(encoding="utf-8")
    block = re.search(r"const TYPE_PARENT = \[(.*?)\];", js, re.S)
    assert block, "TYPE_PARENT missing from store.js"
    js_pats = re.findall(r"/([^/\n]+)/i", block.group(1))
    py_pats = [p for p, _ in TYPE_PARENT]
    assert js_pats == py_pats, (js_pats, py_pats)


def test_catalog_dept_labels():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    by = {i["id"]: i for i in cat["items"]}
    assert dept_label(by["DN2MBTK3CTWNW36SMFCLHQBQ"]) == "Air & Fuel"  # WIX 33063
    assert dept_label(by["LI7R7ABGGB2TXJQUEGHG5TRX"]) == "Mobility"
    assert dept_label(by["WCSSZNLKXNQIOIHDWIOWQCGW"]) == "Cycling"
    assert dept_label(by["EZW5JY5PWZJO4PH5R2TQGYC3"]) == "Material Handling"
    assert dept_label(by["7CESL5VZLPSRKJGWUFCHL5R5"]) == "Electric Motors"
    assert dept_label(by["3YKKZSK4N5HMOC7TOVXSFOHH"]) == "Exhaust"
    assert dept_label(by["RLDFAATFFK6423JIPQIQSH3D"]) == "Interior"
    assert dept_label(by["BA22UJLZFQ7RYU42QV7AFD2Y"]) == "Engines"
    labels = {dept_label(i) for i in cat["items"]}
    assert "Filter" not in labels
    assert "Brake hardware" not in labels
    assert "Vintage" not in labels
    assert "Parts" not in labels


if __name__ == "__main__":
    test_store_js_type_parent_lockstep()
    test_catalog_dept_labels()
    print("dept_tree ok")
