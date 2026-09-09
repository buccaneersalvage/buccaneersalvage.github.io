#!/usr/bin/env python3
"""Store department tree — same rules as store.js itemEbayTree / PARENT_SHORT.

One Python copy of the live store rail. PDPs and drift checks import this
instead of inventing a fourth label table.
"""
from __future__ import annotations

import re

EBAY_SKIP = {
    "ebay motors",
    "parts & accessories",
    "car & truck parts & accessories",
    "commercial truck parts",
}

# Keep pattern strings in lockstep with store.js TYPE_PARENT.
TYPE_PARENT = [
    (r"oil filter|crankcase|breather|timing|sprocket|air injection", "Engines & Engine Parts"),
    (r"fuel filter|air filter", "Air & Fuel Delivery"),
    (r"distributor|ignition|spark plug|vacuum advance|pickup coil|\bhei\b", "Ignition Systems & Components"),
    (r"\bcv\b|boot kit|drivetrain", "Transmission & Drivetrain"),
    (r"brake|caliper", "Brakes & Brake Parts"),
    (r"air spring|rolling lobe|air ride|convoluted", "Suspension & Steering"),
    (r"turbo|injection pump|^pump$", "Cores"),
    (r"exhaust|flange gasket", "Exhaust & Emission Systems"),
    (r"headlight switch|dimmer", "Interior Parts & Accessories"),
    (r"wheelchair", "Mobility"),
    (r"\bbicycle\b|\bbike\b|\bmasi\b", "Cycling"),
    (r"forklift", "Material Handling"),
    (r"capacitor motor|\bcraftsman\b.*\bmotor\b", "Electric Motors"),
]

_TYPE_RX = [(re.compile(pat, re.I), parent) for pat, parent in TYPE_PARENT]

YARD_PARENTS = {
    "mobility",
    "cycling",
    "material-handling",
    "electric-motors",
}

PARENT_SHORT = {
    "suspension-steering": "Suspension",
    "brakes-brake-parts": "Brakes",
    "ignition-systems-components": "Ignition",
    "air-fuel-delivery": "Air & Fuel",
    "engines-engine-parts": "Engines",
    "transmission-drivetrain": "Drivetrain",
    "other-car-truck-parts-accessories": "Other parts",
    "interior-parts-accessories": "Interior",
    "air-conditioning-heating": "HVAC",
    "exhaust-emission-systems": "Exhaust",
    "cores": "Cores",
    "mobility": "Mobility",
    "cycling": "Cycling",
    "material-handling": "Material Handling",
    "electric-motors": "Electric Motors",
}

SUB_CANON = {
    "oil-filters": "oil-filter",
    "fuel-filters": "fuel-filter",
    "air-filters": "air-filter",
    "distributor-caps": "distributor-cap",
    "ignition-coils": "ignition-coil",
    "brake-pads": "brake-pad",
    "transmission-filters": "transmission-filter",
    "exhaust-gaskets": "exhaust-gasket",
    "wheelchairs": "wheelchair",
    "bicycles": "bicycle",
}

SUB_LABEL = {
    "oil-filter": "Oil Filter",
    "fuel-filter": "Fuel Filter",
    "air-filter": "Air Filter",
    "distributor-cap": "Distributor Cap",
    "ignition-coil": "Ignition Coil",
    "brake-pad": "Brake Pad",
    "transmission-filter": "Transmission Filter",
    "exhaust-gasket": "Exhaust Gasket",
    "wheelchair": "Wheelchair",
    "bicycle": "Bicycle",
}


def slug_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def canon_sub_slug(s: str) -> str:
    k = slug_key(s)
    return SUB_CANON.get(k, k)


def type_parent_name(typ: str, name: str) -> str:
    for blob in (typ or "", name or ""):
        if not blob:
            continue
        for rx, parent in _TYPE_RX:
            if rx.search(blob):
                return parent
    return ""


def item_ebay_tree(item: dict | None) -> dict:
    if not item:
        return {"parent": "Other", "parentSlug": "other", "sub": "Other", "subSlug": "other"}
    raw = (
        item.get("ebay_category")
        or ((item.get("fitment") or {}).get("ebay_category") if isinstance(item.get("fitment"), dict) else "")
        or ""
    ).strip()
    parts = [p.strip() for p in raw.split(":") if p.strip()] if raw else []
    kept = [p for p in parts if p.lower() not in EBAY_SKIP]
    typ = (
        item.get("ebay_type")
        or ((item.get("fitment") or {}).get("type") if isinstance(item.get("fitment"), dict) else "")
        or ""
    ).strip()
    parent = ""
    sub = ""
    if len(kept) >= 2:
        parent = kept[0]
        sub = kept[-1]
    elif len(kept) == 1:
        parent = kept[0]
        sub = typ or kept[0]
    typed = type_parent_name(typ, item.get("name") or "")
    if typed and slug_key(parent) != slug_key(typed):
        parent = typed
        if typ and not re.match(r"^vintage$", typ, re.I):
            sub = typ
    if not parent:
        if item.get("category") in ("turbo", "pump"):
            parent = "Cores"
        else:
            parent = type_parent_name(typ, item.get("name") or "")
    raw_slug = slug_key(parent)
    if raw_slug == "health-beauty":
        parent = type_parent_name(typ, item.get("name") or "") or "Mobility"
    elif raw_slug == "sporting-goods":
        parent = type_parent_name(typ, item.get("name") or "") or "Cycling"
    elif raw_slug == "business-industrial":
        parent = type_parent_name(typ, item.get("name") or "") or "Material Handling"
    if not sub or re.match(r"^vintage$", sub, re.I):
        if typ and not re.match(r"^vintage$", typ, re.I):
            sub = typ
        else:
            sub = (kept[-1] if kept else parent)
    sub_slug = canon_sub_slug(sub) or "other"
    return {
        "parent": parent,
        "parentSlug": slug_key(parent) or "other",
        "sub": SUB_LABEL.get(sub_slug, sub),
        "subSlug": sub_slug,
    }


def dept_label(item: dict | None) -> str:
    eb = item_ebay_tree(item)
    return PARENT_SHORT.get(eb["parentSlug"], eb["parent"] or "Parts")


def is_yard_dept(item: dict | None) -> bool:
    return item_ebay_tree(item)["parentSlug"] in YARD_PARENTS


STORE_PARENT_LABEL = {
    "carlson-brake-hardware": "Carlson Brake Hardware",
    "truck-air-springs": "Truck Air Springs",
    "auto-parts": "Auto Parts & Accessories",
    "vintage-collectibles": "Vintage & Collectibles",
    "industrial-warehouse": "Industrial & Warehouse",
}


def _blob(*parts: str) -> str:
    return " ".join(p or "" for p in parts).lower()


def _carlson_sub(name: str, typ: str) -> tuple[str, str]:
    blob = f"{name} {typ}".lower()
    if re.search(r"self-adjuster|self adjuster", blob):
        return "self-adjuster-kits", "Self-Adjuster Kits"
    if re.search(r"parking|drum-in-hat|drum in hat", blob):
        return "parking-brake-kits", "Parking Brake Kits"
    if re.search(r"guide pin|caliper pin|caliper bolt", blob):
        return "caliper-pin-guide-kits", "Caliper Pin & Guide Kits"
    if re.search(r"abutment|boot|quietglide", blob):
        return "hardware-boot-kits", "Hardware & Boot Kits"
    if "drum" in blob:
        return "drum-brake-hardware-kits", "Drum Brake Hardware Kits"
    if "disc" in blob:
        return "disc-brake-hardware-kits", "Disc Brake Hardware Kits"
    return "hardware-boot-kits", "Hardware & Boot Kits"


def _air_sub(name: str, typ: str) -> tuple[str, str]:
    blob = f"{name} {typ}".lower()
    if "triple" in blob:
        return "triple-convoluted", "Triple Convoluted"
    if re.search(r"double|2b\d", blob):
        return "double-convoluted", "Double Convoluted"
    if "convoluted" in blob and "rolling" not in blob:
        return "double-convoluted", "Double Convoluted"
    return "rolling-lobe", "Rolling Lobe"


def _auto_sub(cat: str, typ: str, name: str) -> tuple[str, str]:
    blob = f"{cat} {typ} {name}".lower()
    if re.search(r"oil filter|transmission filter|lube filter", blob):
        return "oil-filters", "Oil Filters"
    if re.search(r"fuel filter|fuel strainer|sediment", blob):
        return "fuel-filters", "Fuel Filters"
    if re.search(r"air filter|crankcase|breather", blob):
        return "air-filters", "Air Filters"
    if re.search(
        r"distributor|ignition|spark plug|rotor|coil|vacuum advance|wire set|pickup|\bhei\b",
        blob,
    ):
        return "ignition-tune-up", "Ignition & Tune-Up"
    if re.search(r"\bcv\b|boot kit|drivetrain|transmission", blob) and "filter" not in blob:
        return "transmission-drivetrain", "Transmission & Drivetrain"
    if re.search(r"headlight switch|dimmer", blob):
        return "headlight-switches", "Headlight Switches"
    if re.search(r"exhaust|flange gasket", blob):
        return "exhaust-parts", "Exhaust Parts"
    if re.search(r"turbo|injection pump|holset|mack diesel", blob):
        return "heavy-truck-diesel", "Heavy Truck & Diesel Parts"
    if re.search(r"solenoid|regulator|map sensor|oxygen|o2 sensor|sealed beam|headlamp|alternator", blob):
        return "electrical-sensors", "Electrical & Sensors"
    if re.search(r"brake|caliper|wagner|lee ", blob):
        return "brakes-suspension", "Brakes & Suspension"
    if re.search(r"control arm|ball joint|tie rod|idler|sway", blob):
        return "suspension-steering", "Suspension & Steering"
    if re.search(r"timing|thermostat|gasket|sprocket|air injection", blob):
        return "engine-parts", "Engine Parts"
    if cat == "filters":
        return "oil-filters", "Oil Filters"
    if cat == "ignition":
        return "ignition-tune-up", "Ignition & Tune-Up"
    if cat == "driveline":
        return "transmission-drivetrain", "Transmission & Drivetrain"
    if cat == "brake":
        return "brakes-suspension", "Brakes & Suspension"
    return "engine-parts", "Engine Parts"


def item_store_tree(item: dict | None) -> dict:
    """eBay-store parent + child. Same rules as store.js itemStoreTree()."""
    if not item:
        return {
            "parentSlug": "auto-parts",
            "parent": "Auto Parts & Accessories",
            "subSlug": "engine-parts",
            "sub": "Engine Parts",
        }
    cat = item.get("category") or ""
    name = item.get("name") or ""
    typ = item.get("ebay_type") or ""
    brand = item.get("ebay_brand") or ""
    blob = _blob(name, typ, brand, cat)

    if cat == "cycling" or re.search(r"\bmasi\b|\bbicycle\b", blob):
        return {
            "parentSlug": "vintage-collectibles",
            "parent": "Vintage & Collectibles",
            "subSlug": "vintage-sports",
            "sub": "Vintage Sports & Recreation",
        }
    if cat == "mobility" or "wheelchair" in blob:
        return {
            "parentSlug": "vintage-collectibles",
            "parent": "Vintage & Collectibles",
            "subSlug": "household-medical",
            "sub": "Household & Medical",
        }
    if cat == "electric-motors" or ("craftsman" in blob and "motor" in blob):
        return {
            "parentSlug": "vintage-collectibles",
            "parent": "Vintage & Collectibles",
            "subSlug": "vintage-tools",
            "sub": "Vintage Tools & Hardware",
        }
    if cat == "material-handling" or "forklift" in blob:
        return {
            "parentSlug": "industrial-warehouse",
            "parent": "Industrial & Warehouse",
            "subSlug": "forklift-warehouse",
            "sub": "Forklift & Warehouse Parts",
        }
    if re.search(r"\bcarlson\b", blob):
        sub_slug, sub = _carlson_sub(name, typ)
        return {
            "parentSlug": "carlson-brake-hardware",
            "parent": "Carlson Brake Hardware",
            "subSlug": sub_slug,
            "sub": sub,
        }
    if cat == "air-spring" or re.search(r"air spring|rolling lobe|convoluted", blob):
        sub_slug, sub = _air_sub(name, typ)
        return {
            "parentSlug": "truck-air-springs",
            "parent": "Truck Air Springs",
            "subSlug": sub_slug,
            "sub": sub,
        }
    sub_slug, sub = _auto_sub(cat, typ, name)
    return {
        "parentSlug": "auto-parts",
        "parent": "Auto Parts & Accessories",
        "subSlug": sub_slug,
        "sub": sub,
    }
