#!/usr/bin/env python3
"""Hub catalog maps to eBay-store parents (only departments on Buc)."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dept_tree import ebay_category_parts, is_workshop_tools, item_store_tree  # noqa: E402


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
    assert store_tree(by["76ZJG6NNDY73XL2QXHGWC56L"]) == ("tools", "cutting-tools")
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


def test_workshop_tools_class_not_craftsman_blob():
    """Tools parent from ebay_category / Square category, not a Craftsman substring."""
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    items = [i for i in cat["items"] if float(i.get("price") or 0) > 0]
    by = {i["id"]: i for i in items}

    py_src = (HUB / "scripts/dept_tree.py").read_text(encoding="utf-8")
    py_fn = re.search(r"def item_store_tree\([\s\S]+", py_src)
    assert py_fn, "item_store_tree missing"
    assert "craftsman" not in py_fn.group(0).lower()
    assert "is_workshop_tools" in py_fn.group(0)
    js_src = (HUB / "store.js").read_text(encoding="utf-8")
    js_fn = re.search(
        r"function itemStoreTree\(item\) \{.*?\n  function displayHyphen",
        js_src,
        re.S,
    )
    assert js_fn, "itemStoreTree missing"
    assert "craftsman" not in js_fn.group(0).lower()
    assert "isWorkshopTools" in js_fn.group(0)
    assert "tools & workshop equipment" in py_src.lower()
    assert "tools, hardware & locks" in py_src.lower()
    assert "tools & workshop equipment" in js_src.lower()
    assert "tools, hardware & locks" in js_src.lower()

    class_hits = []
    missed = []
    for item in items:
        _parts, kept, motors = ebay_category_parts(item)
        catg = item.get("category") or ""
        if is_workshop_tools(catg, kept, motors):
            class_hits.append(item)
            parent = store_tree(item)[0]
            if parent != "tools":
                missed.append((item["id"], item.get("name"), parent, item.get("ebay_category")))
    assert not missed, missed[:8]
    assert len(class_hits) >= 2, [i.get("name") for i in class_hits]

    motor = by["7CESL5VZLPSRKJGWUFCHL5R5"]
    assert store_tree(motor)[0] == "tools"
    assert motor.get("category") == "electric-motors"
    others = [i for i in class_hits if i["id"] != motor["id"]]
    assert others, "Tools would be Craftsman-only"
    assert store_tree(by["76ZJG6NNDY73XL2QXHGWC56L"])[0] == "tools"
    wrench = next(i for i in items if "stillson" in (i.get("name") or "").lower())
    assert store_tree(wrench)[0] == "tools"
    dryer = next(i for i in items if "ge dryer motor" in (i.get("name") or "").lower())
    assert store_tree(dryer)[0] == "home-garden"
    blower = next(i for i in items if "furnace blower" in (i.get("name") or "").lower())
    assert store_tree(blower)[0] == "industrial-warehouse"
    fox = next(i for i in items if "fox head" in (i.get("name") or "").lower())
    assert store_tree(fox)[0] == "vintage-collectibles"
    threader = next(i for i in items if "pipe threader" in (i.get("name") or "").lower())
    assert store_tree(threader)[0] == "industrial-warehouse"
    assert store_tree(by["W3LT2QSYY5C2YYPE5PYLATNO"])[0] == "vintage-collectibles"


def test_python_js_parent_lockstep():
    import subprocess

    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    items = [i for i in cat["items"] if float(i.get("price") or 0) > 0]
    py_map = {i["id"]: item_store_tree(i)["parentSlug"] for i in items}
    slim = [
        {
            "id": i.get("id"),
            "name": i.get("name"),
            "category": i.get("category"),
            "ebay_category": i.get("ebay_category"),
            "ebay_type": i.get("ebay_type"),
            "ebay_brand": i.get("ebay_brand"),
            "price": i.get("price"),
            "fitment": i.get("fitment") if isinstance(i.get("fitment"), dict) else None,
        }
        for i in items
    ]
    js_src = (HUB / "store.js").read_text(encoding="utf-8")
    js_src = js_src.replace(
        "function itemStoreTree(item)",
        "globalThis.itemStoreTree = function itemStoreTree(item)",
        1,
    )
    runner = (
        "globalThis.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null; } };\n"
        + js_src
        + "\nconst catalog = "
        + json.dumps(slim)
        + ";\nconst out = {};\n"
        "for (const i of catalog) { out[i.id] = globalThis.itemStoreTree(i).parentSlug; }\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
        tmp.write(runner)
        tmp_path = tmp.name
    proc = subprocess.run(
        ["node", tmp_path],
        cwd=str(HUB),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    js_map = json.loads(proc.stdout)
    mismatches = [
        (iid, py_map[iid], js_map.get(iid))
        for iid in py_map
        if js_map.get(iid) != py_map[iid]
    ]
    assert not mismatches, mismatches[:12]


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
    test_workshop_tools_class_not_craftsman_blob()
    test_python_js_parent_lockstep()
    test_store_js_has_ebay_store_parents()
    print("test_store_parents: PASS")
