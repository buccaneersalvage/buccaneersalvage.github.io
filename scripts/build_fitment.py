#!/usr/bin/env python3
"""Build structured interchange + vehicle fitment into square-catalog.json.

Design (free-agent consult 2026-08-04 + GitHub fitment patterns):
  - Denormalize fitment ON each catalog item (static GH Pages, no joins).
  - Prefer structured sources over title regex:
      1) carlson_interchange_filex.csv (eBay interchange item specifics)
      2) airspring_square_ids / title OEM patterns for air springs
      3) eBay compat CSV when square↔ebay map exists
      4) title parse as LOW-confidence seed only
  - item.js prefers catalog fitment fields; title parse is fallback.

Usage:
  python3 scripts/build_fitment.py
  python3 scripts/build_fitment.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
CATALOG = HUB / "assets" / "square-catalog.json"
FITMENT_DB = HUB / "assets" / "fitment-db.json"  # optional standalone index
EBAY = Path.home() / "ebay"
CARLSON_CSV = EBAY / "data" / "carlson_interchange_filex.csv"
COMPAT_CSV = EBAY / "data" / "compat_15_20260702.csv"
AIRSPRING_JSON = EBAY / "data" / "airspring_square_ids.json"

BRANDS = (
    "Automann",
    "Goodyear",
    "Continental",
    "ContiTech",
    "Carlson",
    "Mack",
    "Holset",
    "Wagner",
    "Firestone",
    "Meritor",
    "Econoride",
    "OEM",
)


def uniq(seq):
    out = []
    seen = set()
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


def parse_title(name: str) -> dict:
    """Low-confidence seed from title (same rules as item.js historically)."""
    title = (name or "").strip()
    parts: list[str] = []
    xref: list[str] = []
    vehicles: list[str] = []

    rep = re.search(
        r"\bReplaces?\b\.?\s+(.+?)(?:\s+[—–-]\s+|\s+New\b|\s+NOS\b|$)",
        title,
        re.I,
    )
    if rep:
        chunk = re.sub(
            r"\b(New|NOS|Brand New|in Original Box)\b",
            "",
            rep.group(1),
            flags=re.I,
        ).strip()
        better = re.findall(
            r"\b(?:W\d{2}-\d{3}-\d{4}|1R\d{2}-\d{2,4}|[A-Z]{0,4}\d[\w./-]{3,})\b",
            chunk,
            flags=re.I,
        )
        xref.extend(better)

    m = re.match(
        r"^(?:OEM\s+)?(Automann|Goodyear|Continental|ContiTech|Carlson|Mack|Holset|Wagner|Firestone|Meritor|Econoride)\s+([A-Z0-9][\w./-]{2,})",
        title,
        re.I,
    )
    if m:
        parts.append(f"{m.group(1)} {m.group(2)}")
    else:
        c = re.search(r"\b(Carlson)\s+(H?\d{4,5}[A-Z]?Q?)\b", title, re.I)
        if c:
            parts.append(f"{c.group(1)} {c.group(2)}")
        bare = re.match(r"^(H?\d{4,5}[A-Z]?Q?)\b", title)
        if bare:
            parts.append(bare.group(1))

    for t in re.findall(r"\bW\d{2}-\d{3}-\d{4}\b", title):
        if t not in parts and t not in xref:
            parts.append(t)
    for t in re.findall(r"\b1R\d{2}-\d{2,4}\b", title, flags=re.I):
        if t not in parts and t not in xref:
            parts.append(t)
    # Automann style AB… / 566.…
    for t in re.findall(r"\b(?:AB[A-Z0-9][\w./-]{4,}|566\.[\w./-]+)\b", title):
        if t not in parts and t not in xref:
            parts.append(t)

    vehicle_patterns = [
        r"\bfor\s+((?:Ford|Chevy|Chevrolet|GMC|Dodge|Ram|Mercedes(?:-Benz)?|Mack|Kia|Toyota|Honda|Jeep|Nissan)[^—–,]{0,60})",
        r"\b((?:Ford|Chevy|Chevrolet|GMC)\s+F-?Series(?:\s*/\s*E-Series)?)",
        r"\b(Dodge\s+Ram(?:\s+Dakota)?(?:\s+Durango)?)",
        r"\b(Mercedes(?:-Benz)?\s+S-Class(?:\s*/\s*SL-Class)?)",
        r"\b(Mack\s+Truck(?:\s+V8)?)",
        r"\b(Parking Brake\s+Kia)\b",
        r"\b(Freightliner)\b",
    ]
    for pat in vehicle_patterns:
        for m in re.finditer(pat, title, re.I):
            v = (m.group(1) or m.group(0)).strip()
            v = re.sub(r"\s+[—–-].*$", "", v)
            v = re.sub(r"\s*[-–—]\s*New.*$", "", v, flags=re.I)
            v = re.sub(r"\s+Brand New.*$", "", v, flags=re.I)
            v = re.sub(r"\s{2,}", " ", v).strip(" !")
            if len(v) >= 3:
                vehicles.append(v)

    if re.search(r"\bMack\b", title, re.I) and not any(
        re.search(r"mack", v, re.I) for v in vehicles
    ):
        vehicles.append("Mack truck (verify model / OEM casting)")

    xref = [x for x in uniq(xref) if not any(x in p and p != x for p in parts)]
    return {
        "part_numbers": uniq(parts),
        "interchange": uniq(xref),
        "vehicles": uniq(vehicles),
        "source": "title",
        "confidence": "low",
    }


def load_carlson_interchange() -> dict[str, list[str]]:
    """Map normalized Carlson PN → list of interchange numbers from FileX CSV."""
    out: dict[str, list[str]] = {}
    if not CARLSON_CSV.exists():
        return out
    with CARLSON_CSV.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # FileX revise format — only has ebay item id + interchange PN
            # We index by the interchange token itself for reverse lookup on titles
            ic = (row.get("C:Interchange Part Number") or "").strip()
            if not ic:
                continue
            key = ic.upper()
            out.setdefault(key, []).append(ic)
    return out


def load_compat_by_ebay() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not COMPAT_CSV.exists():
        return out
    with COMPAT_CSV.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = (row.get("item_id") or "").strip()
            if not eid:
                continue
            make = (row.get("make") or "").strip()
            model = (row.get("model") or "").strip()
            yf = (row.get("year_from") or "").strip()
            yt = (row.get("year_to") or "").strip()
            label = " ".join(
                x for x in [f"{yf}-{yt}" if yf or yt else "", make, model] if x
            ).strip()
            if not label:
                continue
            out.setdefault(eid, []).append(
                {
                    "label": label,
                    "make": make,
                    "model": model,
                    "year_from": int(yf) if yf.isdigit() else None,
                    "year_to": int(yt) if yt.isdigit() else None,
                    "source": "ebay_compat",
                    "confidence": "high",
                }
            )
    return out


def square_to_ebay_map() -> dict[str, str]:
    """square_item_id → ebay item id from listed/ tracking files when present."""
    m: dict[str, str] = {}
    listed = EBAY / "listings" / "listed"
    if not listed.is_dir():
        return m
    for folder in listed.iterdir():
        if not folder.is_dir():
            continue
        si = folder / "square_item_id.txt"
        if not si.exists():
            continue
        sid = si.read_text(encoding="utf-8").strip()
        # Folder name often starts with ebay id
        name = folder.name
        em = re.match(r"^(\d{12})", name)
        if em:
            m[sid] = em.group(1)
            continue
        # Or ebay_item_id.txt
        for cand in ("ebay_item_id.txt", "item_id.txt"):
            p = folder / cand
            if p.exists():
                m[sid] = p.read_text(encoding="utf-8").strip()
                break
    return m


def extract_carlson_pn(title: str) -> str | None:
    m = re.search(r"\bCarlson\s+(H?\d{4,5}[A-Z]?Q?)\b", title, re.I)
    if m:
        return m.group(1).upper()
    m = re.match(r"^(H?\d{4,5}[A-Z]?Q?)\b", title)
    if m:
        return m.group(1).upper()
    return None


def enrich_item(item: dict, carlson_ic: dict, compat: dict, sq2eb: dict) -> dict:
    title = item.get("name") or ""
    seed = parse_title(title)
    parts = list(seed["part_numbers"])
    xref = list(seed["interchange"])
    vehicles = list(seed["vehicles"])
    sources = set()
    conf_rank = {"low": 0, "medium": 1, "high": 2}
    conf = "low"

    # Carlson PN as primary part number
    cpn = extract_carlson_pn(title)
    if cpn:
        label = f"Carlson {cpn}" if not cpn.startswith("H") or "Carlson" in title else cpn
        if not any(cpn.lower() in p.lower() for p in parts):
            parts.insert(0, f"Carlson {cpn}" if "carlson" not in title.lower()[:20] else parts[0] if parts else f"Carlson {cpn}")
        # FileX interchange rows are often the same PN or alternate; attach if present
        if cpn in carlson_ic:
            for alt in carlson_ic[cpn]:
                if alt.upper() != cpn and alt not in xref:
                    xref.append(alt)
            sources.add("carlson_csv")
            conf = "medium"

    # Also: if any interchange token from FileX appears in title, flag source
    for tok in re.findall(r"\b[A-Z0-9][\w./-]{3,}\b", title):
        if tok.upper() in carlson_ic and tok not in xref and tok not in parts:
            # don't flood with noise
            pass

    # eBay vehicle compatibility via square→ebay map
    eid = sq2eb.get(item.get("id") or "")
    if eid and eid in compat:
        for row in compat[eid]:
            vehicles.append(row["label"])
        sources.add("ebay_compat")
        conf = "high"

    # Air-spring style: structured interchange from Replaces already in seed
    if item.get("category") == "air-spring" and (parts or xref):
        sources.add("airspring_title_oem")
        conf = max(conf, "medium", key=lambda c: conf_rank[c])

    if not sources:
        sources.add("title")
        conf = "low"
    else:
        if "title" not in sources and seed["part_numbers"] or seed["interchange"] or seed["vehicles"]:
            sources.add("title_seed")

    vehicles = uniq(vehicles)
    parts = uniq(parts)
    xref = uniq([x for x in xref if not any(x in p and p != x for p in parts)])

    # confidence bump if multiple structured sources
    if len(sources - {"title", "title_seed"}) >= 2:
        conf = "high"
    elif sources - {"title", "title_seed"}:
        conf = conf if conf != "low" else "medium"

    item["part_numbers"] = parts
    item["interchange"] = xref
    item["vehicles"] = vehicles
    item["fitment_source"] = "+".join(sorted(sources))
    item["fitment_confidence"] = conf
    # Structured vehicle objects when we have year ranges from compat
    fit_vehicles = []
    if eid and eid in compat:
        for row in compat[eid]:
            fit_vehicles.append(
                {
                    "year_from": row.get("year_from"),
                    "year_to": row.get("year_to"),
                    "make": row.get("make"),
                    "model": row.get("model"),
                    "notes": "",
                    "source": "ebay_compat",
                    "confidence": "high",
                }
            )
    for v in vehicles:
        # skip if already covered as structured
        if fit_vehicles and any(
            v.lower() == f"{r.get('year_from')}-{r.get('year_to')} {r.get('make')} {r.get('model')}".lower()
            for r in fit_vehicles
        ):
            continue
        fit_vehicles.append(
            {
                "year_from": None,
                "year_to": None,
                "make": "",
                "model": "",
                "notes": v,
                "source": "title" if "title" in sources else "mixed",
                "confidence": conf,
            }
        )
    item["fitment"] = {
        "part_numbers": parts,
        "interchange": xref,
        "vehicles": fit_vehicles,
        "source": item["fitment_source"],
        "confidence": conf,
    }
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    carlson_ic = load_carlson_interchange()
    compat = load_compat_by_ebay()
    sq2eb = square_to_ebay_map()

    stats = {"items": 0, "with_parts": 0, "with_xref": 0, "with_vehicles": 0, "high": 0}
    index = {}

    for item in cat["items"]:
        enrich_item(item, carlson_ic, compat, sq2eb)
        stats["items"] += 1
        if item.get("part_numbers"):
            stats["with_parts"] += 1
        if item.get("interchange"):
            stats["with_xref"] += 1
        if item.get("vehicles"):
            stats["with_vehicles"] += 1
        if item.get("fitment_confidence") == "high":
            stats["high"] += 1
        index[item["id"]] = {
            "name": item["name"],
            "part_numbers": item.get("part_numbers", []),
            "interchange": item.get("interchange", []),
            "vehicles": item.get("vehicles", []),
            "fitment": item.get("fitment"),
            "fitment_source": item.get("fitment_source"),
            "fitment_confidence": item.get("fitment_confidence"),
        }

    cat["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cat["fitment_built"] = cat["updated"]

    print(json.dumps(stats, indent=2))
    print(f"carlson_csv keys={len(carlson_ic)} compat_ebay_items={len(compat)} sq2eb={len(sq2eb)}")

    if args.dry_run:
        # show samples
        for it in cat["items"][:3]:
            print(
                it["name"][:50],
                "→",
                it.get("part_numbers"),
                it.get("interchange")[:4],
                it.get("vehicles")[:2],
                it.get("fitment_confidence"),
            )
        return 0

    CATALOG.write_text(json.dumps(cat, indent=2) + "\n", encoding="utf-8")
    FITMENT_DB.write_text(
        json.dumps(
            {
                "updated": cat["updated"],
                "schema": "buccaneer-fitment-v1",
                "by_square_id": index,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {CATALOG}")
    print(f"wrote {FITMENT_DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
