#!/usr/bin/env python3
"""MPN filename slugs + Square-ID stubs for hub PDPs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_static_pdps import (  # noqa: E402
    BASE,
    assign_pdp_slugs,
    item_mpn,
    pdp_slug_base,
    slug_stem,
)


def load_items():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    return [i for i in cat["items"] if float(i.get("price") or 0) > 0]


def test_slug_charset():
    assert slug_stem("WIX 46-023!!") == "wix-46-023"
    assert slug_stem("  --Foo--  ") == "foo"
    assert len(slug_stem("a" * 200)) == 80


def test_store_brand_omitted():
    item = {
        "id": "AAAAAAAAAAAAAAAA",
        "name": "Mystery gasket",
        "part_numbers": ["ZZ-999"],
        "ebay_brand": "",
    }
    # brand_guess falls back to first PN token or store name; pin store brand
    item["name"] = "Mystery gasket"
    item["part_numbers"] = []
    assert pdp_slug_base({"id": "AAAAAAAAAAAAAAAA", "name": "x", "part_numbers": []}) == "AAAAAAAAAAAAAAAA"


def test_collision_suffix():
    a = {
        "id": "AAAAAAAAAAAAAAAA",
        "name": "Gates 33008 thermostat",
        "part_numbers": ["Gates 33008"],
        "ebay_brand": "Gates",
        "price": 1,
    }
    b = {
        "id": "BBBBBBBBBBBBBBBB",
        "name": "Gates 33008 duplicate",
        "part_numbers": ["Gates 33008"],
        "ebay_brand": "Gates",
        "price": 1,
    }
    slugs = assign_pdp_slugs([a, b])
    assert slugs[a["id"]] != slugs[b["id"]]
    assert slugs[a["id"]] == "gates-33008"
    assert slugs[b["id"]].startswith("gates-33008-")
    assert len(set(slugs.values())) == 2



def test_ebay_brand_preferred():
    item = {
        "id": "CCCCCCCCCCCCCCCC",
        "name": "Beck/Arnley Outer CV Boot Kit 175-5866",
        "part_numbers": ["175-5866"],
        "ebay_brand": "Beck Arnley",
        "price": 1,
    }
    assert pdp_slug_base(item) == "beck-arnley-175-5866"
    # bare PN must not become mpn-mpn when ebay_brand is set
    assert not pdp_slug_base(item).startswith("175-5866-175")


def test_no_ebay_brand_mpn_mpn_in_catalog():
    items = load_items()
    slugs = assign_pdp_slugs(items)
    bad = []
    for item in items:
        eb = str(item.get("ebay_brand") or "").strip()
        if not eb or eb == "BuccaneerSalvage Store":
            continue
        mpn = item_mpn(item)
        if not mpn:
            continue
        stem = slugs[item["id"]]
        s = slug_stem(mpn)
        if s and stem == f"{s}-{s}":
            bad.append((stem, eb, mpn))
    assert not bad, f"ebay_brand+mpn-mpn left: {bad[:5]}"

def test_catalog_slugs_unique():
    items = load_items()
    slugs = assign_pdp_slugs(items)
    assert len(slugs) == len(items)
    assert len(set(slugs.values())) == len(slugs)
    for item in items:
        iid = item["id"]
        stem = slugs[iid]
        mpn = item_mpn(item)
        if mpn:
            assert stem != iid or pdp_slug_base(item) == iid
        else:
            assert stem == iid


def test_generated_files_and_sitemap():
    items = load_items()
    slugs = assign_pdp_slugs(items)
    t08 = "BYO4CA2ORO6PIIHKJ6BAJ7Z5"
    stem = slugs[t08]
    assert "33008" in stem
    page = (HUB / "p" / f"{stem}.html").read_text(encoding="utf-8")
    assert f"{BASE}/p/{stem}.html" in page
    assert 'content="noindex"' not in page
    stub = (HUB / "p" / f"{t08}.html").read_text(encoding="utf-8")
    if stem != t08:
        assert "noindex" in stub
        assert f"url={stem}.html" in stub
        assert f"{BASE}/p/{stem}.html" in stub
    sm = (HUB / "sitemap-store.xml").read_text(encoding="utf-8")
    assert f"{BASE}/p/{stem}.html" in sm
    assert f"{BASE}/p/{t08}.html" not in sm
    map_json = json.loads((HUB / "assets" / "pdp-slugs.json").read_text(encoding="utf-8"))
    assert map_json[t08] == stem
    js = (HUB / "store.js").read_text(encoding="utf-8")
    assert "pdpSlugs" in js
    assert "pdp-slugs.json" in js
    main = (HUB / "main.js").read_text(encoding="utf-8")
    assert "pdpSlugs" in main
    assert "pdpHref" in main
    assert "pdp-slugs.json" in main


if __name__ == "__main__":
    tests = [
        test_slug_charset,
        test_store_brand_omitted,
        test_collision_suffix,
        test_ebay_brand_preferred,
        test_no_ebay_brand_mpn_mpn_in_catalog,
        test_catalog_slugs_unique,
        test_generated_files_and_sitemap,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}  {exc}")
    raise SystemExit(1 if failed else 0)
