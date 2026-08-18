#!/usr/bin/env python3
"""Related-item grouping: same application only, not same eBay category."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_static_pdps import (  # noqa: E402
    also_stocked_items,
    listing_photo_files,
    load_ship_map,
    related_card_title,
    related_html,
    related_items,
    safe_checkout,
    safe_image,
    ship_for_item,
    short_h1,
    site_product_url,
    vehicle_keys,
)


def _esc(s):
    return str(s or "")


def load_items():
    cat = json.loads((HUB / "assets/square-catalog.json").read_text(encoding="utf-8"))
    return cat["items"], {i["id"]: i for i in cat["items"]}


def by_name(items, needle):
    for i in items:
        if needle in (i.get("name") or ""):
            return i
    raise AssertionError(f"missing {needle}")


def test_dodge_thermo_siblings_only():
    items, _ = load_items()
    t36 = by_name(items, "33036")
    names = [o.get("name") or "" for o in related_items(t36, items)]
    assert any("33038" in n for n in names), names
    assert any("33039" in n for n in names), names
    assert any("5536" in n for n in names), names
    assert not any("33008" in n for n in names), names
    assert not any("33059" in n for n in names), names


def test_chevy_thermo_does_not_dump_dodge():
    items, _ = load_items()
    t08 = by_name(items, "33008")
    names = [o.get("name") or "" for o in related_items(t08, items)]
    assert not any("33036" in n or "33038" in n or "33059" in n for n in names), names


def test_empty_vehicles_no_category_dump():
    items, _ = load_items()
    t59 = by_name(items, "33059")
    assert not vehicle_keys(t59)
    assert related_items(t59, items) == []


def test_brake_hardware_does_not_lump_parking_brake():
    items, _ = load_items()
    kit = by_name(items, "H5626Q")
    names = [o.get("name") or "" for o in related_items(kit, items)]
    assert not any("17353" in n or "Parking Brake" in n for n in names), names


def test_cv_kit_shares_vw():
    items, by_id = load_items()
    kit = by_id["7G7QMJIPJDP6N2LQV42RQS62"]
    rel = related_items(kit, items)
    assert rel, "103-2250 should still have a VW sibling"
    assert any("CV2485" in (o.get("name") or "") for o in rel)


def test_html_uses_cards_not_title_wall():
    items, by_id = load_items()
    t36 = by_name(items, "33036")
    html = related_html(t36, items, _esc, _esc)
    assert "pdp-rel-card" in html
    assert "Same vehicles in this store" in html
    assert "Related in this store" not in html
    assert "store.html?q=" in html
    assert "33008" not in html
    t08 = by_name(items, "33008")
    html08 = related_html(t08, items, _esc, _esc)
    assert "33036" not in html08
    assert "browse thermostat in the catalog" in html08.lower()
    also = also_stocked_items(by_id["R6VO2MARXN7GRGTMXVGABLHT"], items)
    assert also == []
    html_also = related_html(by_id["R6VO2MARXN7GRGTMXVGABLHT"], items, _esc, _esc)
    assert "Same part number" not in html_also
    assert "$0.00" not in html_also
    assert "G2O3XG6XWRX5K7QT65T7NQZO" not in html_also
    assert related_card_title(t36).startswith("Gates")


def test_listing_gallery_and_zero_price_filter():
    items, by_id = load_items()
    paid = by_id["R6VO2MARXN7GRGTMXVGABLHT"]
    assert "G2O3XG6XWRX5K7QT65T7NQZO" not in by_id
    assert all(float(i.get("price") or 0) > 0 for i in items)
    assert also_stocked_items(paid, items) == []
    ghost = {
        "id": "GHOSTZEROTESTITEM000001",
        "name": paid.get("name"),
        "price": 0,
        "part_numbers": list(paid.get("part_numbers") or []),
        "ebay_item_id": paid.get("ebay_item_id"),
    }
    mixed = items + [ghost]
    assert also_stocked_items(paid, mixed) == []
    hits = also_stocked_items(ghost, mixed)
    assert hits
    assert all(float(o.get("price") or 0) > 0 for o in hits)
    shots = listing_photo_files(paid.get("ebay_item_id"))
    assert len(shots) >= 3
    rel = f"../assets/pdp-gallery/{paid['id']}/02.webp"
    assert safe_image(rel) == rel
    assert safe_image("../assets/pdp-gallery/../02.webp") == ""


def test_ship_snapshot_matches_square_profiles():
    items, by_id = load_items()
    sm = load_ship_map()
    t08 = by_id["BYO4CA2ORO6PIIHKJ6BAJ7Z5"]
    rate, label = ship_for_item(t08["id"], sm)
    assert rate == "4.99", (rate, label)
    assert "4.99" in label
    a3490 = by_id["KTQC3YPSDMZIGSNXVF2NPNNH"]
    rate, label = ship_for_item(a3490["id"], sm)
    assert rate == "6.99", (rate, label)
    arm = by_id["4ZIBBGXFF65NRMKSS3IQ2R3T"]
    rate, label = ship_for_item(arm["id"], sm)
    assert rate == "9.99", (rate, label)
    # Mack turbo core — Square still free; do not invent $40
    mack = by_id.get("AGEWYOLANWBWUWDDESOE3EIG")
    if mack:
        rate, label = ship_for_item(mack["id"], sm)
        assert rate == "0", (rate, label)
    lee = by_name(items, "7146")
    rate, _ = ship_for_item(lee["id"], sm)
    assert rate == "0"


def test_short_h1_and_site_checkout():
    items, by_id = load_items()
    t08 = by_id["BYO4CA2ORO6PIIHKJ6BAJ7Z5"]
    h1 = short_h1(t08)
    assert "Gates" in h1 and "33008" in h1
    assert "Camaro NOS USA" not in h1
    url = site_product_url(t08["id"])
    assert url.endswith("/product/BYO4CA2ORO6PIIHKJ6BAJ7Z5")
    assert safe_checkout(url) == url
    assert safe_checkout("https://evil.example/product/BYO4CA2ORO6PIIHKJ6BAJ7Z5") == ""
    assert safe_checkout("https://square.link/u/kBO2Zgdy").startswith("https://square.link/")
    page = (HUB / "p" / f"{t08['id']}.html").read_text(encoding="utf-8")
    assert f'href="{url}"' in page
    assert 'data-bind="checkout"' in page
    assert "Auto Parts &amp; Accessories" in page or "Auto Parts & Accessories" in page
    air = (HUB / "p" / "R6VO2MARXN7GRGTMXVGABLHT.html").read_text(encoding="utf-8")
    assert "Truck Air Springs" in air
    assert 'href="https://buccaneersalvage.square.site/product/R6VO2MARXN7GRGTMXVGABLHT"' in air
    vintage = (HUB / "p" / "WCSSZNLKXNQIOIHDWIOWQCGW.html").read_text(encoding="utf-8")
    assert "Vintage &amp; Collectibles" in vintage or "Vintage & Collectibles" in vintage


if __name__ == "__main__":
    tests = [
        test_dodge_thermo_siblings_only,
        test_chevy_thermo_does_not_dump_dodge,
        test_empty_vehicles_no_category_dump,
        test_brake_hardware_does_not_lump_parking_brake,
        test_cv_kit_shares_vw,
        test_html_uses_cards_not_title_wall,
        test_listing_gallery_and_zero_price_filter,
        test_ship_snapshot_matches_square_profiles,
        test_short_h1_and_site_checkout,
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
