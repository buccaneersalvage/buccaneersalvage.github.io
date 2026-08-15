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
# Square titles that contradict the live eBay listing for the same SKU.
# Display-only; next export must keep these (see export_hub_square_catalog.py).
NAME_OVERRIDE = {
    "U7IAHNRLDFHIMBOV75GFFH7W": "Cloyes B-061 Timing Belt NOS Chevy Chevette Pontiac T1000 79-87",
    "OIEKBY47T4B7SOUC5WDL34PA": "Carlson H5764Q Rear Disc Brake Hardware Pro Kit New Chevy Silverado GMC Sierra",
}
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


_LISTING_PN_RES = [
    re.compile(r"\bWIX\s+(\d{4,5}[A-Z]?)\b", re.I),
    re.compile(r"\b(?:MOOG|Moog)\s+(CV\d+)\b", re.I),
    re.compile(r"\bStandard\s+(JH\d+)\b", re.I),
    re.compile(r"\bCloyes\s+([A-Z]-?\d+)\b", re.I),
    re.compile(r"\bPace Setter\s+(DR-?\d+)\b", re.I),
    re.compile(r"\b(8VBB-1100)\b", re.I),
    re.compile(r"\b(160583P2)\b", re.I),
    re.compile(r"\b(780068P?)\b", re.I),
    re.compile(r"\b(FS-HS04)\b", re.I),
    re.compile(r"\b((?:1R|2B|3B)\d{1,2}-\d{2,4}|AB[A-Z0-9][\w./-]{4,}|566\.[\w./-]+)\b", re.I),
]


def extract_listing_pns(title: str) -> list[str]:
    """Brand PNs already printed in a title. Used only to map Square → eBay id."""
    s = title or ""
    out = []
    for rx in _LISTING_PN_RES:
        for m in rx.finditer(s):
            tok = (m.group(1) or m.group(0)).strip().upper().replace(" ", "")
            if tok.endswith("P") and tok[:-1].isdigit() and len(tok) >= 6:
                out.append(tok[:-1])
            out.append(tok)
    cpn = extract_carlson_pn(s)
    if cpn:
        out.append(cpn)
    return uniq(out)


def map_by_title_and_pn(catalog_items: list[dict]) -> dict[str, str]:
    """square id → ebay id from active_listings title / printed PN."""
    active_path = DATA / "active_listings.csv"
    if not active_path.exists():
        return {}
    active = list(csv.DictReader(active_path.open(encoding="utf-8", errors="replace")))
    by_title = {a["title"].strip().lower(): a["item_id"] for a in active if a.get("title")}
    by_pn: dict[str, list[str]] = defaultdict(list)
    for a in active:
        eid = (a.get("item_id") or "").strip()
        if not eid:
            continue
        for pn in extract_listing_pns(a.get("title") or ""):
            if eid not in by_pn[pn]:
                by_pn[pn].append(eid)

    out = {}
    for it in catalog_items:
        sid = it["id"]
        title = (it.get("name") or "").strip()
        if title.lower() in by_title:
            out[sid] = by_title[title.lower()]
            continue
        hits = []
        for pn in extract_listing_pns(title):
            ids = by_pn.get(pn) or []
            if len(ids) == 1:
                hits.append(ids[0])
        hits = uniq(hits)
        if len(hits) == 1:
            out[sid] = hits[0]
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
        key = (make, model)
        years_hit = False
        if year and str(year).isdigit():
            groups[key].add(int(year))
            years_hit = True
        for yk in ("year_from", "year_to"):
            yv = v.get(yk)
            if yv is not None and str(yv).isdigit():
                groups[key].add(int(yv))
                years_hit = True
        if not years_hit:
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
        key = (make, model)
        hit = False
        if year and str(year).isdigit():
            groups[key].add(int(year))
            hit = True
        for yk in ("year_from", "year_to"):
            yv = v.get(yk)
            if yv is not None and str(yv).isdigit():
                groups[key].add(int(yv))
                hit = True
        if not hit:
            groups[key]
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

    vehicles.extend(parse_title_vehicle_notes(title))

    return {
        "part_numbers": uniq(parts),
        "interchange": uniq(xref),
        "vehicles": uniq(vehicles),
        "vehicles_raw": parse_title_vehicles(title),
        "source": "title",
        "confidence": "low",
    }


_TITLE_MAKES = [
    ("mercedes-benz", "Mercedes-Benz"),
    ("mercedes", "Mercedes-Benz"),
    ("volkswagen", "Volkswagen"),
    ("chevrolet", "Chevrolet"),
    ("chevy", "Chevrolet"),
    ("oldsmobile", "Oldsmobile"),
    ("pontiac", "Pontiac"),
    ("chrysler", "Chrysler"),
    ("plymouth", "Plymouth"),
    ("lincoln", "Lincoln"),
    ("mercury", "Mercury"),
    ("cadillac", "Cadillac"),
    ("buick", "Buick"),
    ("saturn", "Saturn"),
    ("honda", "Honda"),
    ("acura", "Acura"),
    ("toyota", "Toyota"),
    ("lexus", "Lexus"),
    ("nissan", "Nissan"),
    ("datsun", "Datsun"),
    ("infiniti", "Infiniti"),
    ("infinity", "Infiniti"),
    ("mazda", "Mazda"),
    ("subaru", "Subaru"),
    ("isuzu", "Isuzu"),
    ("volvo", "Volvo"),
    ("hyundai", "Hyundai"),
    ("kia", "Kia"),
    ("jeep", "Jeep"),
    ("dodge", "Dodge"),
    ("ram", "Ram"),
    ("ford", "Ford"),
    ("gmc", "GMC"),
    ("gm", "GM"),
    ("mack", "Mack"),
    ("freightliner", "Freightliner"),
    ("kubota", "Kubota"),
    ("new holland", "New Holland"),
    ("mahindra", "Mahindra"),
]

_TITLE_JUNK = {
    "nos", "new", "lot", "of", "fits", "fit", "for", "with", "w", "and",
    "bracket", "microgard", "cross", "inline", "in-line", "diesel",
    "light-duty", "light", "duty", "truck", "trucks", "van", "vans",
    "mini", "car", "cars", "suv", "suvs", "select", "models", "model",
    "class", "oem", "ver", "working", "tested", "housing", "metal",
    "filter", "filters", "oil", "fuel", "air", "outer", "inner", "kit",
    "boot", "cv", "joint", "engine", "timing", "belt", "ignition", "coil",
    "distributor", "cap", "wire", "set", "sohc", "dohc", "v6", "v8",
    "l", "family", "classic", "wagon", "sedan", "coupe", "in-pan",
    "in", "pan", "replacement", "universal", "dash", "dimmer",
    "mid", "early", "late", "1980s", "1990s", "1970s",
}

_MAKE_KEYS = {k for k, _ in _TITLE_MAKES}


def _norm_year_token(s: str) -> int | None:
    if not s or not str(s).isdigit():
        return None
    n = int(s)
    if n < 100:
        return 2000 + n if n <= 29 else 1900 + n
    if 1930 <= n <= 2030:
        return n
    return None


def parse_title_year_range(title: str) -> tuple[int | None, int | None]:
    m = re.search(
        r"\b((?:19|20)\d{2}|\d{2})\s*[-–—/]\s*((?:19|20)\d{2}|\d{2})\b",
        title or "",
    )
    if not m:
        m2 = re.search(r"\b((?:19|20)\d{2})\b", title or "")
        if m2:
            y = _norm_year_token(m2.group(1))
            return y, y
        return None, None
    a, b = _norm_year_token(m.group(1)), _norm_year_token(m.group(2))
    if a and b and a > b:
        a, b = b, a
    return a, b


def parse_title_vehicles(title: str) -> list[dict]:
    """Makes / models / years already printed in the title. Never invents rows."""
    s = title or ""
    if re.search(r"air spring|rolling lobe|convoluted", s, re.I):
        return []
    y0, y1 = parse_title_year_range(s)
    found: list[dict] = []
    seen = set()
    for key, canon in _TITLE_MAKES:
        rx = re.compile(rf"\b{re.escape(key)}\b", re.I)
        m = rx.search(s)
        if not m:
            continue
        sk = canon.lower()
        if sk in seen:
            continue
        seen.add(sk)
        rest = s[m.end() :]
        model_bits = []
        for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]*", rest):
            low = tok.lower()
            if low in _MAKE_KEYS or low in _TITLE_JUNK:
                break
            if _norm_year_token(tok) or re.fullmatch(r"\d{2,4}[-/]\d{2,4}", tok):
                break
            if re.search(r"(?:19|20)\d{2}", tok):
                break
            if re.fullmatch(r"\d[\d.]*L", tok, re.I):
                break
            model_bits.append(tok)
            if len(model_bits) >= 1:
                break
        found.append(
            {
                "year": None,
                "year_from": y0,
                "year_to": y1,
                "make": canon,
                "model": " ".join(model_bits),
                "notes": "",
                "source": "title",
                "confidence": "low",
            }
        )
    found.extend(scan_known_models(s, found, y0, y1))
    return found


# Models already printed in leftover titles. Never invents a make/model pair
# unless the make is already on the row or in the title (GM family included).
_KNOWN_MODELS = [
    ("civic", "Honda"),
    ("accord", "Honda"),
    ("crx", "Honda"),
    ("prelude", "Honda"),
    ("century", "Buick"),
    ("celebrity", "Chevrolet"),
    ("chevette", "Chevrolet"),
    ("camry", "Toyota"),
    ("corolla", "Toyota"),
    ("taurus", "Ford"),
    ("sable", "Mercury"),
    ("sephia", "Kia"),
    ("spectra", "Kia"),
]
_GM_FAMILY = {"Buick", "Chevrolet", "GMC", "Pontiac", "Oldsmobile", "Cadillac"}


def scan_known_models(title, already, y0, y1):
    have = {(v.get("make") or "").strip() for v in already if v.get("make")}
    have_pairs = {
        ((v.get("make") or "").strip().lower(), (v.get("model") or "").strip().lower())
        for v in already
    }
    extra = []
    for model, make in _KNOWN_MODELS:
        if not re.search(rf"\b{re.escape(model)}\b", title or "", re.I):
            continue
        target = None
        if make in have:
            target = make
        elif "GM" in have and make in _GM_FAMILY:
            target = "GM"
        elif re.search(rf"\b{re.escape(make)}\b", title or "", re.I):
            target = make
        else:
            # Model word is already in the title (Civic, Camry). Use its make.
            target = make
        if not target:
            continue
        label = "CRX" if model == "crx" else model.title()
        if (target.lower(), label.lower()) in have_pairs:
            continue
        have_pairs.add((target.lower(), label.lower()))
        extra.append(
            {
                "year": None,
                "year_from": y0,
                "year_to": y1,
                "make": target,
                "model": label,
                "notes": "",
                "source": "title",
                "confidence": "low",
            }
        )
    return extra


def merge_title_vehicles(vehicles_raw: list[dict], title_vs: list[dict]) -> list[dict]:
    """Fill empty models / add title models onto existing makes. No new invented makes."""
    if not title_vs:
        return vehicles_raw
    have_makes = {(v.get("make") or "").strip() for v in vehicles_raw if v.get("make")}
    have_pairs = {
        ((v.get("make") or "").strip().lower(), (v.get("model") or "").strip().lower())
        for v in vehicles_raw
        if v.get("make")
    }
    out = list(vehicles_raw)
    for tv in title_vs:
        make = (tv.get("make") or "").strip()
        model = (tv.get("model") or "").strip()
        if not make or not model:
            continue
        if make not in have_makes:
            # Title printed this model (Civic, Century). Keep that make+model.
            out.append(tv)
            have_pairs.add((make.lower(), model.lower()))
            have_makes.add(make)
            continue
        key = (make.lower(), model.lower())
        if key in have_pairs:
            continue
        # if this make has only blank-model rows, stamp the first one
        stamped = False
        for v in out:
            if (v.get("make") or "").strip() != make:
                continue
            if (v.get("model") or "").strip():
                continue
            v["model"] = model
            if v.get("year_from") is None and tv.get("year_from") is not None:
                v["year_from"] = tv.get("year_from")
                v["year_to"] = tv.get("year_to")
            stamped = True
            have_pairs.add(key)
            break
        if not stamped:
            out.append(tv)
            have_pairs.add(key)
    return out


def parse_title_vehicle_notes(title: str) -> list[str]:
    """Readable Fits leftover when no structured make was extracted."""
    s = title or ""
    out = []
    m = re.search(r"\bFits?\b[:\s]+(.+)$", s, re.I)
    if m:
        chunk = re.sub(r"\s+[—–-]\s+.*$", "", m.group(1)).strip(" .")
        chunk = re.sub(r"\b(NOS|New Old Stock|OEM Ver)\b.*$", "", chunk, flags=re.I).strip()
        if 3 <= len(chunk) <= 80:
            out.append(chunk)
    for pat in (
        r"\b(Mack\s+Truck)\b",
        r"\b(Freightliner)\b",
        r"\b((?:Ford|Chevy|Chevrolet|GMC)\s+F-?Series(?:\s*/\s*E-Series)?)",
    ):
        for mm in re.finditer(pat, s, re.I):
            out.append(mm.group(1).strip())
    return uniq(out)


_CAR_TRUCK_PREFIX = "eBay Motors:Parts & Accessories:Car & Truck Parts & Accessories:"
_TRUCK_PREFIX = "eBay Motors:Parts & Accessories:Commercial Truck Parts:"

_TYPE_DEPT = [
    (re.compile(r"oil filter|crankcase|breather", re.I), "Engines & Engine Parts", "Oil Filters"),
    (re.compile(r"timing|sprocket", re.I), "Engines & Engine Parts", "Timing Components & Kits"),
    (re.compile(r"air injection", re.I), "Engines & Engine Parts", "Other Engine Parts"),
    (re.compile(r"fuel filter", re.I), "Air & Fuel Delivery", "Fuel Filters"),
    (re.compile(r"air filter", re.I), "Air & Fuel Delivery", "Air Filters"),
    (re.compile(r"distributor cap", re.I), "Ignition Systems & Components", "Distributor Caps"),
    (re.compile(r"ignition coil", re.I), "Ignition Systems & Components", "Ignition Coils"),
    (re.compile(r"spark plug|ignition wire", re.I), "Ignition Systems & Components", "Ignition Wires & Coil Boots"),
    (re.compile(r"vacuum advance|pickup coil|distributor|ignition", re.I), "Ignition Systems & Components", "Other Ignition Systems & Components"),
    (re.compile(r"\bcv\b|boot kit", re.I), "Transmission & Drivetrain", "CV Joints, Boots & Parts"),
    (re.compile(r"transmission filter", re.I), "Transmission & Drivetrain", "Transmission Filters"),
    (re.compile(r"brake pad", re.I), "Brakes & Brake Parts", "Brake Pads"),
    (re.compile(r"brake|caliper", re.I), "Brakes & Brake Parts", "Brake Pad & Shoe Hardware"),
    (re.compile(r"air spring|rolling lobe|air ride|convoluted", re.I), "Suspension & Steering", "Air Ride Suspension"),
    (re.compile(r"exhaust|flange gasket", re.I), "Exhaust & Emission Systems", "Exhaust Gaskets"),
    (re.compile(r"headlight switch|dimmer", re.I), "Interior Parts & Accessories", "Switches & Controls"),
]


def type_department(ebay_type: str, title: str = "") -> tuple[str, str]:
    for blob in (ebay_type or "", title or ""):
        if not blob:
            continue
        for rx, parent, leaf in _TYPE_DEPT:
            if rx.search(blob):
                return parent, leaf
    return "", ""


def current_ebay_parent(ebay_category: str) -> str:
    skip = {
        "ebay motors",
        "parts & accessories",
        "car & truck parts & accessories",
        "commercial truck parts",
    }
    parts = [p.strip() for p in (ebay_category or "").split(":") if p.strip()]
    kept = [p for p in parts if p.lower() not in skip]
    return kept[0] if kept else ""


def correct_ebay_category(ebay_category: str, ebay_type: str, title: str, square_cat: str) -> str:
    """Rewrite a wrong or empty PrimaryCategory from Type / title. Store-only."""
    parent, leaf = type_department(ebay_type, title)
    if not parent:
        return ebay_category or ""
    have = current_ebay_parent(ebay_category)
    if have.lower() == parent.lower() and ebay_category:
        return ebay_category
    if square_cat == "air-spring" or re.search(r"air spring|rolling lobe", title or "", re.I):
        return f"{_TRUCK_PREFIX}{parent}:{leaf}"
    return f"{_CAR_TRUCK_PREFIX}{parent}:{leaf}"


def existing_live(item: dict) -> dict | None:
    """Reuse last catalog GetItem so a missing-only run does not wipe fitment."""
    if not (item.get("ebay_category") or item.get("ebay_item_id") or item.get("vehicles")):
        return None
    raw: list[dict] = []
    fit = item.get("fitment") if isinstance(item.get("fitment"), dict) else {}
    for v in fit.get("vehicles") or []:
        if not isinstance(v, dict):
            continue
        if v.get("make"):
            y0, y1 = v.get("year_from"), v.get("year_to")
            if y0 and y1 and str(y0) != str(y1):
                raw.append({"year": y0, "make": v["make"], "model": v.get("model") or ""})
                raw.append({"year": y1, "make": v["make"], "model": v.get("model") or ""})
            else:
                raw.append({"year": y0 or y1, "make": v["make"], "model": v.get("model") or ""})
        elif v.get("notes"):
            raw.append({"year": None, "make": "", "model": "", "notes": v["notes"]})
    return {
        "part_numbers": item.get("part_numbers") or [],
        "interchange": item.get("interchange") or [],
        "vehicles_raw": raw,
        "ebay_type": item.get("ebay_type") or "",
        "ebay_brand": item.get("ebay_brand") or "",
        "ebay_category": item.get("ebay_category") or "",
        "confidence": item.get("fitment_confidence") or "medium",
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
    title_vs = list(seed.get("vehicles_raw") or [])
    y0, y1 = parse_title_year_range(title)
    title_vs.extend(scan_known_models(title, vehicles_raw + title_vs, y0, y1))
    if vehicles_raw:
        merged = merge_title_vehicles(vehicles_raw, title_vs)
        if merged != vehicles_raw:
            vehicles_raw = merged
            if "title" not in sources:
                sources.append("title")
    else:
        for v in title_vs:
            vehicles_raw.append(v)
        if not vehicles_raw:
            for v in seed.get("vehicles") or []:
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
        if vehicles_raw:
            if "title" not in sources:
                sources.append("title")
            if conf == "high" and live:
                conf = "medium"

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

    _drop = {"does not apply", "n/a", "na"}
    parts = [p for p in parts if str(p).strip().lower() not in _drop]
    xref = [x for x in xref if str(x).strip().lower() not in _drop]
    parts = dedupe_redundant_pns(parts)
    xref = uniq([x for x in xref if not any(x == p or x in p for p in parts)])
    xref = dedupe_redundant_pns(xref)

    override = NAME_OVERRIDE.get(item.get("id") or "")
    if override:
        item["name"] = override
        title = override

    if not ebay_type:
        ebay_type = infer_type_from_title(title, item.get("category") or "")

    ebay_category = correct_ebay_category(
        ebay_category, ebay_type, title, item.get("category") or ""
    )

    item["part_numbers"] = parts
    item["interchange"] = xref
    item["vehicles"] = vehicle_labels
    prev_raw = item.get("vehicle_count_raw")
    raw_n = len(vehicles_raw)
    if isinstance(prev_raw, int) and prev_raw > raw_n:
        raw_n = prev_raw
    item["vehicle_count_raw"] = raw_n
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
        "raw_compat_rows": raw_n,
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
        # Keep last good GetItem unless this row never got a category / id.
        if it.get("ebay_category") and it.get("ebay_item_id"):
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
        eid = sq2eb.get(it["id"]) or (it.get("ebay_item_id") or "") or None
        live = live_cache.get(eid) if eid else None
        if live is None:
            live = existing_live(it)
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
