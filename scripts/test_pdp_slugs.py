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
    SQUARE_ID_RE,
    assign_pdp_slugs,
    is_title_year_pn,
    item_display_pns,
    item_mpn,
    pdp_slug_base,
    pdp_slug_from_name,
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
    assert pdp_slug_base({"id": "AAAAAAAAAAAAAAAA", "name": "x", "part_numbers": []}) == "x"
    store = {
        "id": "AAAAAAAAAAAAAAAA",
        "name": "Mystery gasket",
        "part_numbers": [],
        "ebay_brand": "BuccaneerSalvage Store",
    }
    assert pdp_slug_base(store) == "mystery-gasket"
    assert "buccaneersalvage" not in pdp_slug_base(store)


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
            assert stem != iid
            assert not SQUARE_ID_RE.fullmatch(stem.upper())


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


def test_title_year_not_mpn():
    jeep = {
        "id": "STX3QQ2VRH3VAFUCF55IA3VR",
        "name": "1976-1986 Jeep CJ Clutch Brake Pedal Assembly Manual Transmission OEM",
        "part_numbers": ["1976"],
        "ebay_brand": "Jeep",
    }
    assert is_title_year_pn("1976", jeep["name"])
    assert item_display_pns(jeep) == []
    assert item_mpn(jeep) == ""
    stem = pdp_slug_base(jeep)
    assert stem != "jeep-1976"
    assert "clutch" in stem
    assert "1976" in stem
    national = {
        "id": "BBBBBBBBBBBBBBBB",
        "name": "National 2043 Pinion Seal NOS 88-97 Chevy K1500",
        "part_numbers": ["2043"],
        "ebay_brand": "National",
    }
    assert not is_title_year_pn("2043", national["name"])
    assert item_mpn(national) == "2043"


def test_breadcrumb_is_full_name():
    items = {i["id"]: i for i in load_items()}
    slugs = assign_pdp_slugs(list(items.values()))
    jeep = items["STX3QQ2VRH3VAFUCF55IA3VR"]
    stem = slugs[jeep["id"]]
    page = (HUB / "p" / f"{stem}.html").read_text(encoding="utf-8")
    assert jeep["name"] in page
    assert f'<span>{jeep["name"]}</span>' in page or "Clutch Brake Pedal Assembly" in page
    assert ">1976<" not in page.split("pdp-breadcrumb")[1].split("</nav>")[0]


def test_no_mpn_name_slug_not_square_id():
    coleman = {
        "id": "W54WMQYKJ4OJRLJQRQSYYXHV",
        "name": "Vintage 1972 Coleman 425 2-Burner Camp Stove Green Case Restoration Project",
        "part_numbers": [],
        "ebay_brand": "Coleman",
    }
    stem = pdp_slug_base(coleman)
    assert stem != coleman["id"]
    assert stem.startswith("coleman-1972-425")
    assert "vintage" not in stem
    tile = {
        "id": "76ZJG6NNDY73XL2QXHGWC56L",
        "name": "Vintage 24 Inch Heavy Duty Manual Tile Cutter Ceramic Floor Wall Contractor",
        "part_numbers": [],
        "ebay_brand": "Unbranded",
    }
    tstem = pdp_slug_base(tile)
    assert tstem != tile["id"]
    assert "unbranded" not in tstem
    assert "tile-cutter" in tstem
    empty = {"id": "W54WMQYKJ4OJRLJQRQSYYXHV", "name": "", "part_numbers": []}
    assert pdp_slug_from_name(empty, empty["id"]).startswith("item-")


def test_generated_no_mpn_files():
    items = {i["id"]: i for i in load_items()}
    slugs = assign_pdp_slugs(list(items.values()))
    for iid in (
        "W54WMQYKJ4OJRLJQRQSYYXHV",
        "76ZJG6NNDY73XL2QXHGWC56L",
        "W4MUULZLATJKYPEY6SEKNP25",
    ):
        stem = slugs[iid]
        assert stem != iid
        page = (HUB / "p" / f"{stem}.html").read_text(encoding="utf-8")
        assert f"{BASE}/p/{stem}.html" in page
        assert 'content="noindex"' not in page
        stub = (HUB / "p" / f"{iid}.html").read_text(encoding="utf-8")
        assert "noindex" in stub
        assert f"url={stem}.html" in stub
        if iid == "W54WMQYKJ4OJRLJQRQSYYXHV":
            assert "Sporting Goods" in page
            assert "Camping Stoves" in page
        if iid == "76ZJG6NNDY73XL2QXHGWC56L":
            assert "Home &amp; Garden" in page or "Home & Garden" in page
        if iid == "W4MUULZLATJKYPEY6SEKNP25":
            assert "Rifle Scopes" in page


def test_h1_matches_catalog_name():
    import html as html_lib

    items = {i["id"]: i for i in load_items()}
    slugs = assign_pdp_slugs(list(items.values()))
    # Julian 2026-09-08: hub H1 was short_h1, Square checkout had the listing title.
    iid = "373RPPOCYAZFVEE4KH3VYLOY"
    stem = slugs[iid]
    name = items[iid]["name"]
    page = (HUB / "p" / f"{stem}.html").read_text(encoding="utf-8")
    assert f'<h1 class="pdp-title">{html_lib.escape(name)}</h1>' in page
    assert "Gates 5536 · 160 F" not in page
    t08 = items["BYO4CA2ORO6PIIHKJ6BAJ7Z5"]
    p08 = (HUB / "p" / f"{slugs[t08['id']]}.html").read_text(encoding="utf-8")
    assert f'<h1 class="pdp-title">{html_lib.escape(t08["name"])}</h1>' in p08


if __name__ == "__main__":
    tests = [
        test_slug_charset,
        test_store_brand_omitted,
        test_collision_suffix,
        test_ebay_brand_preferred,
        test_no_ebay_brand_mpn_mpn_in_catalog,
        test_catalog_slugs_unique,
        test_title_year_not_mpn,
        test_no_mpn_name_slug_not_square_id,
        test_generated_files_and_sitemap,
        test_generated_no_mpn_files,
        test_breadcrumb_is_full_name,
        test_h1_matches_catalog_name,
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
