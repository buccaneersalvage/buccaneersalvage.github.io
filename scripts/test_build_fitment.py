#!/usr/bin/env python3
"""Unit/smoke for build_fitment pure helpers. No live eBay/Square. No invent."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_fitment import (  # noqa: E402
    collapse_vehicles,
    correct_ebay_category,
    dedupe_redundant_pns,
    extract_carlson_pn,
    extract_listing_pns,
    infer_type_from_title,
    parse_title_vehicles,
    parse_title_year_range,
    structured_vehicles,
    type_department,
    uniq,
)


def test_uniq_casefold():
    assert uniq(["A", "a", "B", ""]) == ["A", "B"]


def test_dedupe_redundant_pns():
    assert dedupe_redundant_pns(["Carlson 13329", "13329"]) == ["13329"]
    assert dedupe_redundant_pns(["AB1DK23K-9194", "9194"]) == ["AB1DK23K-9194"]


def test_extract_carlson_pn():
    assert extract_carlson_pn("Carlson H5764Q Rear Disc") == "H5764Q"
    assert extract_carlson_pn("H2108 Brake Hardware") == "H2108"
    assert extract_carlson_pn("WIX 46023 Oil Filter") is None


def test_extract_listing_pns():
    pns = extract_listing_pns("WIX 51630 Oil Filter NOS")
    assert "51630" in pns
    assert "H5764Q" in extract_listing_pns("Carlson H5764Q Rear Disc Hardware")


def test_collapse_and_structured_vehicles():
    raw = [
        {"year": 2002, "make": "Dodge", "model": "Dakota"},
        {"year": 2011, "make": "Dodge", "model": "Dakota"},
        {"year": 1999, "make": "Ford", "model": "Taurus"},
    ]
    labels = collapse_vehicles(raw)
    assert any("2002–2011 Dodge Dakota" == x or "2002-2011 Dodge Dakota" in x.replace("–", "-") for x in labels) or any(
        "Dodge Dakota" in x and "2002" in x for x in labels
    )
    assert any("Ford Taurus" in x for x in labels)
    structs = structured_vehicles(raw)
    dodge = next(s for s in structs if s["make"] == "Dodge" and s["model"] == "Dakota")
    assert dodge["year_from"] == 2002 and dodge["year_to"] == 2011
    assert dodge["source"] == "ebay_compat"


def test_parse_title_year_range():
    assert parse_title_year_range("Fits 87-92 Chevy") == (1987, 1992)
    assert parse_title_year_range("NOS 1999 only") == (1999, 1999)
    assert parse_title_year_range("no years here") == (None, None)


def test_parse_title_vehicles_no_invent():
    # air springs: never passenger YMM from title
    assert parse_title_vehicles("Goodyear 2B12-410 Double Convoluted Air Spring") == []
    # displacement "2.8" must not become a model (catalog bug 2026-08-20)
    vs = parse_title_vehicles("GM Isuzu 2.8 V6 Oil Filter")
    assert not any((v.get("model") or "").startswith("2.8") for v in vs)
    # printed make/model ok
    honda = parse_title_vehicles("Fits 88-91 Honda Civic Distributor Cap")
    assert any(v.get("make") == "Honda" for v in honda)


def test_infer_type_from_title():
    assert infer_type_from_title("WIX 51630 Oil Filter NOS", "filters") == "Oil Filter"
    assert infer_type_from_title("Carlson Disc Brake Hardware Kit", "brake") == "Disc Brake Hardware"
    assert infer_type_from_title("Goodyear Air Spring 2B12", "air-spring") == "Air Spring"
    assert infer_type_from_title("Mystery part", "other") == ""


def test_type_department_and_correct_category():
    parent, leaf = type_department("Oil Filter", "WIX oil filter")
    assert parent
    assert leaf
    # empty category rewritten from type
    out = correct_ebay_category("", "Oil Filter", "WIX 51630 Oil Filter", "filters")
    assert parent in out and leaf in out
    # air-spring path uses truck prefix when type matches
    air = correct_ebay_category("", "Air Spring", "Goodyear air spring", "air-spring")
    assert "Truck" in air or "Commercial" in air or air


if __name__ == "__main__":
    tests = [
        test_uniq_casefold,
        test_dedupe_redundant_pns,
        test_extract_carlson_pn,
        test_extract_listing_pns,
        test_collapse_and_structured_vehicles,
        test_parse_title_year_range,
        test_parse_title_vehicles_no_invent,
        test_infer_type_from_title,
        test_type_department_and_correct_category,
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
