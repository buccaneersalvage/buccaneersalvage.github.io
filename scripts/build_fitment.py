#!/usr/bin/env python3
"""Build real interchange + vehicle fitment into square-catalog.json.

Sources (priority high → low):
  1) Live eBay GetItem ItemSpecifics + ItemCompatibilityList (authoritative)
  2) carlson_specs_report.csv / air_spring_inventory.csv on disk
  3) listed/ 1-listing.txt Item Specifics + Example vehicles
  4) Title parse only as last-resort seed (flagged low confidence)

Maps square catalog rows → eBay item IDs via:
  airspring_square_ids.json, listed/*/square_item_id.txt + ebay_id.txt,
  exact title match on active_listings.csv, Carlson MPN match on active titles.

Usage:
  python3 scripts/build_fitment.py              # full rebuild + eBay API
  python3 scripts/build_fitment.py --offline    # disk sources only
  python3 scripts/build_fitment.py --limit 5    # smoke
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
CATALOG = HUB / "assets" / "square-catalog.json"
FITMENT_DB = HUB / "assets" / "fitment-db.json"
EBAY = Path.home() / "ebay"
SCRIPTS = EBAY / "scripts"
DATA = EBAY / "data"

sys.path.insert(0, str(SCRIPTS))


def uniq(seq):
    out, seen = [], set()
    for x in seq:
        k = str(x).strip()
        if not k:
            continue
        lk = k.lower()
        if lk in seen:
            continue
        seen.add(lk)
        out.append(k)
    return out


_BRAND_PREFIX = re.compile(
    r"^(?:OEM\s+)?(?:Carlson|Automann|Goodyear|Continental|ContiTech|Mack|"
    r"Holset|Wagner|Firestone|Meritor|Econoride|Mercedes(?:-Benz)?)\s+",
    re.I,
)


def dedupe_redundant_pns(parts: list[str]) -> list[str]:
    """Drop Brand+PN when bare PN is already listed (and short suffix-only dups).

    Example: ['Carlson 13329', '13329'] → ['13329']
    Example: ['AB1DK23K-9194', '9194'] → ['AB1DK23K-9194']
    """
    cleaned = uniq(parts)
    bare_set = set()
    for p in cleaned:
        bare = _BRAND_PREFIX.sub("", p).strip()
        if bare:
            bare_set.add(bare.lower())

    out: list[str] = []
    for p in cleaned:
        bare = _BRAND_PREFIX.sub("", p).strip()
        is_branded = bare.lower() != p.lower()
        # Prefer bare token when both "Brand 13329" and "13329" exist
        if is_branded and bare.lower() in bare_set and any(
            x.lower() == bare.lower() for x in cleaned
        ):
            continue
        out.append(p)

    # Drop pure short numeric suffix already covered by a longer PN
    final: list[str] = []
    for p in out:
        pl = p.lower().strip()
        if re.fullmatch(r"\d{3,6}[a-z]?", pl):
            if any(
                q.lower() != pl and re.search(rf"(?:^|[\s\-/]){re.escape(pl)}$", q.lower())
                for q in out
            ):
                continue
        final.append(p)
    return final


def extract_carlson_pn(title: str) -> str | None:
    m = re.search(r"\bCarlson\s+(H?\d{4,5}[A-Z]?Q?)\b", title or "", re.I)
    if m:
        return m.group(1).upper()
    m = re.match(r"^(H?\d{4,5}[A-Z]?Q?)\b", title or "")
    return m.group(1).upper() if m else None


def extract_primary_pn(title: str) -> str | None:
    """Leading brand PN or bare Carlson/Goodyear-style code."""
    m = re.match(
        r"^(?:OEM\s+)?(?:Automann|Goodyear|Continental|ContiTech|Carlson|Mack|"
        r"Holset|Wagner|Firestone|Meritor|Econoride)\s+([A-Z0-9][\w./-]{2,})",
        title or "",
        re.I,
    )
    if m:
        return m.group(1)
    return extract_carlson_pn(title or "")


# ── square → eBay maps ──────────────────────────────────────────────────────


def map_square_to_ebay() -> dict[str, str]:
    """square_item_id → ebay item_id."""
    m: dict[str, str] = {}

    # airspring_square_ids: ebay_id → {item_id: square, ...}
    asp = DATA / "airspring_square_ids.json"
    if asp.exists():
        raw = json.loads(asp.read_text(encoding="utf-8"))
        for ebay_id, info in raw.items():
            if isinstance(info, dict) and info.get("item_id"):
                m[info["item_id"]] = str(ebay_id)

    # listed folders
    listed = EBAY / "listings" / "listed"
    if listed.is_dir():
        for folder in listed.iterdir():
            if not folder.is_dir():
                continue
            si = folder / "square_item_id.txt"
            if not si.exists():
                continue
            sid = si.read_text(encoding="utf-8").strip()
            ebay_id = None
            for cand in ("ebay_id.txt", "ebay_item_id.txt", "item_id.txt"):
                p = folder / cand
                if p.exists():
                    ebay_id = p.read_text(encoding="utf-8").strip()
                    break
            if not ebay_id:
                em = re.match(r"^(\d{12})", folder.name)
                if em:
                    ebay_id = em.group(1)
            if ebay_id:
                m[sid] = ebay_id

    return m


def map_by_title_and_pn(catalog_items: list[dict]) -> dict[str, str]:
    """square id → ebay id from active_listings title / Carlson PN."""
    active_path = DATA / "active_listings.csv"
    if not active_path.exists():
        return {}
    active = list(csv.DictReader(active_path.open(encoding="utf-8", errors="replace")))
    by_title = {a["title"].strip().lower(): a["item_id"] for a in active if a.get("title")}
    by_pn: dict[str, str] = {}
    for a in active:
        pn = extract_carlson_pn(a.get("title") or "")
        if pn:
            by_pn[pn] = a["item_id"]
        # also Goodyear / Automann leading codes
        m = re.search(
            r"\b((?:1R|2B|3B)\d{1,2}-\d{2,4}|AB[A-Z0-9][\w./-]{4,}|566\.[\w./-]+)\b",
            a.get("title") or "",
            re.I,
        )
        if m:
            by_pn[m.group(1).upper()] = a["item_id"]

    out = {}
    for it in catalog_items:
        sid = it["id"]
        title = (it.get("name") or "").strip()
        if title.lower() in by_title:
            out[sid] = by_title[title.lower()]
            continue
        cpn = extract_carlson_pn(title)
        if cpn and cpn in by_pn:
            out[sid] = by_pn[cpn]
            continue
        # try bare primary PN from title against by_pn
        m = re.search(
            r"\b((?:1R|2B|3B)\d{1,2}-\d{2,4}|AB[A-Z0-9][\w./-]{4,}|566\.[\w./-]+)\b",
            title,
            re.I,
        )
        if m and m.group(1).upper() in by_pn:
            out[sid] = by_pn[m.group(1).upper()]
    return out


# ── disk interchange tables ─────────────────────────────────────────────────


def load_carlson_specs() -> dict[str, dict]:
    """SKU/PN upper → {interchange, upc, ebay_id}."""
    out = {}
    p = DATA / "carlson_specs_report.csv"
    if not p.exists():
        return out
    with p.open(encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            sku = (row.get("Custom label (SKU)") or "").strip().upper()
            ich = (row.get("C:Interchange Part Number") or "").strip()
            eid = (row.get("Item ID") or "").strip()
            upc = (row.get("UPC") or "").strip()
            if not sku:
                continue
            out[sku] = {
                "interchange": [ich] if ich else [],
                "upc": upc if upc and upc.lower() != "does not apply" else "",
                "ebay_id": eid,
            }
            # also index without trailing Q
            if sku.endswith("Q"):
                out.setdefault(sku[:-1], out[sku])
    return out


def load_airspring_inventory() -> dict[str, dict]:
    """part_number upper → {firestone_xref, ebay_id, title}."""
    out = {}
    p = DATA / "air_spring_inventory.csv"
    if not p.exists():
        return out
    with p.open(encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            pn = (row.get("part_number") or "").strip()
            if not pn:
                continue
            xref = (row.get("firestone_xref") or "").strip()
            out[pn.upper()] = {
                "part_number": pn,
                "interchange": [xref] if xref else [],
                "ebay_id": (row.get("item_id") or "").strip(),
                "title": row.get("title") or "",
            }
    return out


# ── eBay GetItem ────────────────────────────────────────────────────────────


def fetch_ebay_fitment(token: str, item_id: str) -> dict | None:
    from ebay_api import trading_call

    NS = "{urn:ebay:apis:eBLBaseComponents}"
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <ItemID>{item_id}</ItemID>
  <DetailLevel>ReturnAll</DetailLevel>
  <IncludeItemSpecifics>true</IncludeItemSpecifics>
  <IncludeItemCompatibilityList>true</IncludeItemCompatibilityList>
</GetItemRequest>"""

    root = None
    for site in ("100", "0"):
        try:
            root = trading_call(token, "GetItem", body, site_id=site)
            ack = root.findtext(f".//{NS}Ack") or ""
            if "Failure" not in ack:
                break
        except Exception as exc:
            print(f"  GetItem {item_id} site={site}: {exc}", file=sys.stderr)
            root = None
    if root is None:
        return None
    ack = root.findtext(f".//{NS}Ack") or ""
    if "Failure" in ack:
        return None

    # ItemSpecifics — multi-value aware
    specs: dict[str, list[str]] = {}
    for nvl in root.findall(f".//{NS}ItemSpecifics/{NS}NameValueList"):
        name = nvl.findtext(f"{NS}Name") or ""
        vals = [v.text.strip() for v in nvl.findall(f"{NS}Value") if v.text and v.text.strip()]
        if name and vals:
            specs[name] = vals

    vehicles = []
    for c in root.findall(f".//{NS}ItemCompatibilityList/{NS}Compatibility"):
        nv = {}
        for nvl in c.findall(f"{NS}NameValueList"):
            n = nvl.findtext(f"{NS}Name")
            v = nvl.findtext(f"{NS}Value")
            if n and v:
                nv[n] = v.strip()
        if nv.get("Make") or nv.get("Model"):
            vehicles.append(
                {
                    "year": nv.get("Year"),
                    "make": nv.get("Make") or "",
                    "model": nv.get("Model") or "",
                    "trim": nv.get("Trim") or "",
                    "engine": nv.get("Engine") or "",
                    "source": "ebay_compat",
                    "confidence": "high",
                }
            )

    def first_spec(*names: str) -> str:
        for name in names:
            vals = specs.get(name) or []
            if vals:
                return vals[0]
        return ""

    ebay_type = first_spec("Type", "Filter Type", "Part Type")
    ebay_brand = first_spec("Brand", "Manufacturer")
    ebay_category = (
        root.findtext(f".//{NS}PrimaryCategory/{NS}CategoryName") or ""
    ).strip()

    parts = []
    for key in (
        "Part Number",
        "Manufacturer Part Number",
        "OE/OEM Part Number",
        "Other Part Number",
    ):
        for v in specs.get(key, []):
            parts.append(v)
    # Keep bare MPN only — "Brand 13329" + "13329" was showing as dupe on hub PDP.
    # Brand is already in the product title.

    interchange = []
    for key in ("Interchange Part Number", "Other Part Number", "OE/OEM Part Number"):
        for v in specs.get(key, []):
            # split comma-separated multi
            for piece in re.split(r"[,;/|]+", v):
                piece = piece.strip()
                if piece and piece.lower() not in ("does not apply", "n/a", "na"):
                    interchange.append(piece)

    return {
        "part_numbers": uniq(parts),
        "interchange": uniq(interchange),
        "vehicles_raw": vehicles,
        "ebay_type": ebay_type,
        "ebay_brand": ebay_brand,
        "ebay_category": ebay_category,
        "ebay_id": item_id,
        "source": "ebay_live",
        "confidence": "high" if vehicles or interchange else "medium",
    }


def collapse_vehicles(raw: list[dict]) -> list[str]:
    """Collapse Year/Make/Model rows into readable ranges: '2002–2011 Dodge Dakota'."""
    if not raw:
        return []
    # group by make+model → years
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    extras: list[str] = []
    for v in raw:
        make = (v.get("make") or "").strip()
        model = (v.get("model") or "").strip()
        year = v.get("year")
        if not make and v.get("notes"):
            extras.append(v["notes"])
            continue
        if not make:
            continue
        y = None
        if year and str(year).isdigit():
            y = int(year)
        key = (make, model)
        if y:
            groups[key].add(y)
        else:
            groups[key]  # ensure key exists

    labels = []
    for (make, model), years in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        if years:
            y0, y1 = min(years), max(years)
            yr = f"{y0}–{y1}" if y0 != y1 else str(y0)
        else:
            yr = ""
        labels.append(" ".join(x for x in [yr, make, model] if x).strip())
    labels.extend(uniq(extras))
    return labels


def structured_vehicles(raw: list[dict]) -> list[dict]:
    """Year-range objects per make/model for fitment.vehicles."""
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    for v in raw:
        make = (v.get("make") or "").strip()
        model = (v.get("model") or "").strip()
        year = v.get("year")
        if not make:
            continue
        if year and str(year).isdigit():
            groups[(make, model)].add(int(year))
        else:
            groups[(make, model)]
    out = []
    for (make, model), years in sorted(groups.items()):
        out.append(
            {
                "year_from": min(years) if years else None,
                "year_to": max(years) if years else None,
                "make": make,
                "model": model,
                "notes": "",
                "source": "ebay_compat",
                "confidence": "high",
                "trim_count": None,
            }
        )
    return out


# ── title seed (last resort) ────────────────────────────────────────────────


def parse_title_seed(name: str) -> dict:
    title = (name or "").strip()
    parts, xref, vehicles = [], [], []

    rep = re.search(
        r"\bReplaces?\b\.?\s+(.+?)(?:\s+[—–-]\s+|\s+New\b|\s+NOS\b|$)",
        title,
        re.I,
    )
    if rep:
        chunk = re.sub(
            r"\b(New|NOS|Brand New|in Original Box)\b", "", rep.group(1), flags=re.I
        ).strip()
        xref.extend(
            re.findall(
                r"\b(?:W\d{2}-\d{3}-\d{4}|1R\d{2}-\d{2,4}|[A-Z]{0,4}\d[\w./-]{3,})\b",
                chunk,
                flags=re.I,
            )
        )

    m = re.match(
        r"^(?:OEM\s+)?(Automann|Goodyear|Continental|ContiTech|Carlson|Mack|Holset|"
        r"Wagner|Firestone|Meritor|Econoride)\s+([A-Z0-9][\w./-]{2,})",
        title,
        re.I,
    )
    if m:
        parts.append(f"{m.group(1)} {m.group(2)}")
    else:
        c = extract_carlson_pn(title)
        if c:
            parts.append(c)

    for t in re.findall(r"\bW\d{2}-\d{3}-\d{4}\b", title):
        if t not in parts:
            parts.append(t) if "W01" in t or t.startswith("W") else xref.append(t)
    for t in re.findall(r"\b1R\d{2}-\d{2,4}\b", title, flags=re.I):
        if t not in parts and t not in xref:
            xref.append(t)

    for pat in (
        r"\bfor\s+((?:Ford|Chevy|Chevrolet|GMC|Dodge|Ram|Mercedes(?:-Benz)?|Mack|Kia)[^—–,]{0,50})",
        r"\b((?:Ford|Chevy|Chevrolet|GMC)\s+F-?Series(?:\s*/\s*E-Series)?)",
        r"\b(Dodge\s+Ram(?:\s+Dakota)?)",
        r"\b(Mercedes(?:-Benz)?\s+S-Class(?:\s*/\s*SL-Class)?)",
        r"\b(Mack\s+Truck)\b",
        r"\b(Parking Brake\s+Kia)\b",
        r"\b(Freightliner)\b",
    ):
        for mm in re.finditer(pat, title, re.I):
            v = re.sub(r"\s+[—–-].*$", "", (mm.group(1) or mm.group(0))).strip()
            v = re.sub(r"\s+Brand New.*$", "", v, flags=re.I).strip(" !")
            if len(v) >= 3:
                vehicles.append(v)

    return {
        "part_numbers": uniq(parts),
        "interchange": uniq(xref),
        "vehicles": uniq(vehicles),
        "source": "title",
        "confidence": "low",
    }


# ── merge / enrich ──────────────────────────────────────────────────────────


def enrich_item(
    item: dict,
    *,
    ebay_id: str | None,
    live: dict | None,
    carlson: dict,
    airspring: dict,
) -> dict:
    parts: list[str] = []
    xref: list[str] = []
    vehicles_raw: list[dict] = []
    sources: list[str] = []
    conf = "low"
    title = item.get("name") or ""

    ebay_type = ""
    ebay_brand = ""
    ebay_category = ""
    if live:
        parts.extend(live.get("part_numbers") or [])
        xref.extend(live.get("interchange") or [])
        vehicles_raw.extend(live.get("vehicles_raw") or [])
        ebay_type = (live.get("ebay_type") or "").strip()
        ebay_brand = (live.get("ebay_brand") or "").strip()
        ebay_category = (live.get("ebay_category") or "").strip()
        sources.append("ebay_listing")
        conf = live.get("confidence") or "high"

    # disk: Carlson specs by MPN
    cpn = extract_carlson_pn(title)
    if cpn and cpn in carlson:
        info = carlson[cpn]
        xref.extend(info.get("interchange") or [])
        if info.get("interchange"):
            sources.append("carlson_specs")
            if conf == "low":
                conf = "medium"
        if not ebay_id and info.get("ebay_id"):
            ebay_id = info["ebay_id"]
        if cpn and not any(cpn.lower() in p.lower() for p in parts):
            parts.insert(0, cpn)

    # disk: air spring inventory
    for token in re.findall(
        r"\b((?:1R|2B|3B)\d{1,2}-\d{2,4}|AB[A-Z0-9][\w./-]{4,}|566\.[\w./-]+)\b",
        title,
        re.I,
    ):
        key = token.upper()
        if key in airspring:
            info = airspring[key]
            if info.get("part_number") and not any(
                info["part_number"].lower() in p.lower() for p in parts
            ):
                parts.append(info["part_number"])
            xref.extend(info.get("interchange") or [])
            sources.append("airspring_inventory")
            if conf == "low":
                conf = "medium"
            if not ebay_id and info.get("ebay_id"):
                ebay_id = info["ebay_id"]

    # title seed only if still thin
    seed = parse_title_seed(title)
    if not parts:
        parts = seed["part_numbers"]
        if seed["part_numbers"]:
            sources.append("title")
    else:
        # still pick up Replaces: tokens not already present
        for x in seed["interchange"]:
            if x not in xref and not any(x in p for p in parts):
                xref.append(x)
        if seed["interchange"] and "title" not in sources and not live:
            sources.append("title")
    if not vehicles_raw and seed["vehicles"]:
        for v in seed["vehicles"]:
            vehicles_raw.append(
                {
                    "year": None,
                    "make": "",
                    "model": "",
                    "notes": v,
                    "source": "title",
                    "confidence": "low",
                }
            )
        if "title" not in sources:
            sources.append("title")
        if conf == "high" and not live:
            pass
        elif conf == "low":
            conf = "low"

    if vehicles_raw and any(v.get("source") == "ebay_compat" for v in vehicles_raw):
        conf = "high"
    if not sources:
        sources = ["title"]

    vehicle_labels = collapse_vehicles(vehicles_raw)
    fit_vehicles = structured_vehicles(
        [v for v in vehicles_raw if v.get("make")]
    )
    # note-only vehicles as free-text entries
    for v in vehicles_raw:
        if v.get("notes") and not v.get("make"):
            fit_vehicles.append(
                {
                    "year_from": None,
                    "year_to": None,
                    "make": "",
                    "model": "",
                    "notes": v["notes"],
                    "source": v.get("source") or "title",
                    "confidence": v.get("confidence") or "low",
                }
            )

    parts = dedupe_redundant_pns(parts)
    xref = uniq([x for x in xref if not any(x == p or x in p for p in parts)])
    xref = dedupe_redundant_pns(xref)

    if not ebay_type:
        ebay_type = infer_type_from_title(title, item.get("category") or "")

    item["part_numbers"] = parts
    item["interchange"] = xref
    item["vehicles"] = vehicle_labels
    item["vehicle_count_raw"] = len(vehicles_raw)
    item["ebay_item_id"] = ebay_id or ""
    item["ebay_type"] = ebay_type
    item["ebay_brand"] = ebay_brand
    item["ebay_category"] = ebay_category
    item["fitment_source"] = "+".join(dict.fromkeys(sources))  # ordered unique
    item["fitment_confidence"] = conf
    item["fitment"] = {
        "part_numbers": parts,
        "interchange": xref,
        "vehicles": fit_vehicles,
        "vehicle_labels": vehicle_labels,
        "raw_compat_rows": len(vehicles_raw),
        "source": item["fitment_source"],
        "confidence": conf,
        "ebay_item_id": ebay_id or "",
        "type": ebay_type,
        "brand": ebay_brand,
        "ebay_category": ebay_category,
    }
    return item


def infer_type_from_title(title: str, category: str) -> str:
    """Last-resort Type from words already in the listing title. Never invents fitment."""
    n = (title or "").lower()
    cat = (category or "").lower()
    if cat == "filters" or "filter" in n:
        if "oil" in n:
            return "Oil Filter"
        if "fuel" in n:
            return "Fuel Filter"
        if "cabin" in n or "pollen" in n:
            return "Cabin Air Filter"
        if "trans" in n:
            return "Transmission Filter"
        if "air" in n:
            return "Air Filter"
        return "Filter"
    if cat == "ignition" or any(k in n for k in ("distributor", "ignition", "coil")):
        if "distributor" in n and "cap" in n:
            return "Distributor Cap"
        if "distributor" in n:
            return "Distributor"
        if "rotor" in n:
            return "Distributor Rotor"
        if "wire" in n:
            return "Spark Plug Wire"
        if "coil" in n:
            return "Ignition Coil"
        if "vacuum" in n:
            return "Vacuum Advance"
        if "cap" in n:
            return "Distributor Cap"
        return "Ignition"
    if cat == "brake" or "brake" in n:
        if "caliper" in n and "pin" in n:
            return "Caliper Guide Pin"
        if "hardware" in n and "drum" in n:
            return "Drum Brake Hardware"
        if "hardware" in n:
            return "Disc Brake Hardware"
        if "parking" in n:
            return "Parking Brake Hardware"
        return "Brake Hardware"
    if cat == "air-spring" or "air spring" in n or "air bag" in n:
        return "Air Spring"
    if cat == "driveline":
        if "cv" in n or "boot" in n:
            return "CV Boot"
        if "timing" in n:
            return "Timing Belt"
        if "axle" in n:
            return "Axle"
        return "Driveline"
    if cat == "turbo":
        return "Turbocharger"
    if cat == "pump":
        return "Pump"
    if cat == "vintage":
        return "Vintage"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true", help="skip eBay API")
    ap.add_argument("--limit", type=int, default=0, help="max items to enrich via API")
    ap.add_argument("--sleep", type=float, default=0.35)
    args = ap.parse_args()

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = cat["items"]

    sq2eb = map_square_to_ebay()
    title_map = map_by_title_and_pn(items)
    for sid, eid in title_map.items():
        sq2eb.setdefault(sid, eid)

    # reverse: also fill from carlson/airspring tables
    carlson = load_carlson_specs()
    airspring = load_airspring_inventory()
    for it in items:
        if it["id"] in sq2eb:
            continue
        cpn = extract_carlson_pn(it.get("name") or "")
        if cpn and cpn in carlson and carlson[cpn].get("ebay_id"):
            sq2eb[it["id"]] = carlson[cpn]["ebay_id"]

    print(f"mapped square→ebay: {len(sq2eb)} / {len(items)}")

    token = None
    if not args.offline:
        try:
            from ebay_api import get_token

            token = get_token()
        except Exception as exc:
            print(f"WARN: no eBay token ({exc}) — offline mode", file=sys.stderr)
            args.offline = True

    live_cache: dict[str, dict] = {}
    api_n = 0
    for it in items:
        eid = sq2eb.get(it["id"])
        if args.offline or not token or not eid:
            continue
        if args.limit and api_n >= args.limit:
            break
        if eid in live_cache:
            continue
        print(f"  GetItem {eid} ← {it['name'][:50]}")
        data = fetch_ebay_fitment(token, eid)
        if data:
            live_cache[eid] = data
            print(
                f"    parts={data['part_numbers'][:3]} xref={data['interchange'][:4]} "
                f"vehicles={len(data['vehicles_raw'])}"
            )
        else:
            print("    (no data)")
        api_n += 1
        time.sleep(args.sleep)

    stats = {
        "items": 0,
        "with_parts": 0,
        "with_xref": 0,
        "with_vehicles": 0,
        "high": 0,
        "ebay_live": 0,
        "total_compat_rows": 0,
    }
    index = {}

    for it in items:
        eid = sq2eb.get(it["id"])
        live = live_cache.get(eid) if eid else None
        enrich_item(it, ebay_id=eid, live=live, carlson=carlson, airspring=airspring)
        stats["items"] += 1
        if it.get("part_numbers"):
            stats["with_parts"] += 1
        if it.get("interchange"):
            stats["with_xref"] += 1
        if it.get("vehicles"):
            stats["with_vehicles"] += 1
        if it.get("fitment_confidence") == "high":
            stats["high"] += 1
        if live:
            stats["ebay_live"] += 1
        stats["total_compat_rows"] += int(it.get("vehicle_count_raw") or 0)
        index[it["id"]] = {
            "name": it["name"],
            "ebay_item_id": it.get("ebay_item_id"),
            "part_numbers": it.get("part_numbers"),
            "interchange": it.get("interchange"),
            "vehicles": it.get("vehicles"),
            "fitment": it.get("fitment"),
            "fitment_source": it.get("fitment_source"),
            "fitment_confidence": it.get("fitment_confidence"),
        }

    cat["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cat["fitment_built"] = cat["updated"]
    CATALOG.write_text(json.dumps(cat, indent=2) + "\n", encoding="utf-8")
    FITMENT_DB.write_text(
        json.dumps(
            {
                "updated": cat["updated"],
                "schema": "buccaneer-fitment-v2",
                "stats": stats,
                "by_square_id": index,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(stats, indent=2))
    print(f"wrote {CATALOG}")
    print(f"wrote {FITMENT_DB}")
    # sample
    for it in items:
        if it.get("vehicle_count_raw", 0) > 10:
            print(
                "SAMPLE",
                it["name"][:45],
                "xref",
                it.get("interchange"),
                "veh_labels",
                len(it.get("vehicles") or []),
                "raw",
                it.get("vehicle_count_raw"),
                "→",
                (it.get("vehicles") or [])[:4],
            )
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
