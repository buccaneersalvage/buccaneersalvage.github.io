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
