#!/usr/bin/env python3
"""Regenerate static PDP pages under p/{brand-mpn}.html for no-JS crawler SEO.

Square catalog ids stay on sku and as noindex meta-refresh stubs when the
canonical filename is a brand-mpn slug. GitHub Pages has no HTTP 301.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dept_tree import dept_label, item_ebay_tree, item_store_tree

HUB = Path(__file__).resolve().parents[1]
BASE = "https://buccaneersalvage.github.io"


def money(n):
    try:
        return f"${float(n):,.2f}"
    except Exception:
        return ""


def has_sale_price(item):
    """Square ghost variations land at $0.00 — not a second unit for sale."""
    try:
        return float(item.get("price") or 0) > 0
    except (TypeError, ValueError):
        return False


def pdp_desc(item, name, catl, price, custom_warn):
    """Per-item meta/schema copy from real catalog fields — not one identical
    'Browse and secure checkout' line on all 198 pages."""
    brand = brand_guess(item)
    if custom_warn:
        cond = custom_warn.replace(" — ", ". ").replace(" · ", ". ")
        lead = f"{name}. {cond}."
    elif is_core(item.get("category")):
        lead = f"{name}. Untested {catl.lower()} core for parts or rebuild. No returns."
    elif brand and brand != "BuccaneerSalvage Store" and brand.lower() not in name.lower():
        lead = f"{name}. {brand} {catl.lower()} from BuccaneerSalvage yard stock."
    else:
        lead = f"{name}. {catl} from BuccaneerSalvage yard stock."
    if price:
        lead = f"{lead} {price}."
    if pickup_only(custom_warn, name):
        return f"{lead} Pickup only by appointment in Carbondale, PA."
    return f"{lead} Ships US-wide or pickup by appointment in Carbondale, PA."


def pickup_only(*texts):
    blob = " ".join(str(t or "") for t in texts)
    return bool(re.search(r"pickup only|no shipping", blob, re.I))


def cat_label(c):
    return {
        "air-spring": "Air spring",
        "brake": "Brake hardware",
        "filters": "Filter",
        "ignition": "Ignition",
        "driveline": "Driveline",
        "turbo": "Turbo core",
        "pump": "Pump core",
        "mobility": "Mobility",
        "cycling": "Cycling",
        "material-handling": "Material Handling",
        "electric-motors": "Electric Motors",
        "interior": "Interior",
        "exhaust": "Exhaust",
        "engines": "Engines",
    }.get(c, "Parts")


def is_core(c):
    return c in ("turbo", "pump")


def _uniq_keep(seq):
    out = []
    seen = set()
    for x in seq:
        s = str(x or "").strip()
        if not s or s.lower() in ("does not apply", "n/a", "na"):
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _split_pns(val):
    if val is None:
        return []
    if isinstance(val, list):
        bits = []
        for v in val:
            bits.extend(_split_pns(v))
        return bits
    return [p.strip() for p in re.split(r"[,;/|]+", str(val)) if p.strip()]


_NAME_PN_RES = (
    re.compile(r"\bWIX\s+\d{4,6}\b", re.I),
    re.compile(r"\bMOOG\s+CV\d+\b", re.I),
    re.compile(r"\bCloyes\s+[A-Z]-?\d{2,4}\b", re.I),
    re.compile(r"\bStandard\s+JH\d+\b", re.I),
    re.compile(r"\bPace\s*Setter\s+DR-?\d+\b", re.I),
    re.compile(r"\b8VBB-1100\b", re.I),
    re.compile(r"\b780068P\b", re.I),
    re.compile(r"\bKW14\b", re.I),
)


def pns_from_name(name):
    """PNs already printed in the listing title. Display only. Not vehicle fitment."""
    s = str(name or "")
    out = []
    for rx in _NAME_PN_RES:
        out.extend(m.group(0).strip() for m in rx.finditer(s))
    return _uniq_keep(out)


def is_title_year_pn(pn, name) -> bool:
    """Square often stores the title's leading year as part_numbers (1976-1986 → '1976')."""
    s = str(pn or "").strip()
    if not re.fullmatch(r"(19|20)\d{2}", s):
        return False
    n = str(name or "").strip()
    return bool(re.match(rf"^{re.escape(s)}(?:\s|-(?:19|20)\d{{2}}\b|$)", n))


def _real_pns(seq, name):
    return [p for p in _uniq_keep(seq) if not is_title_year_pn(p, name)]


def item_part_numbers(item):
    fit = item.get("fitment") if isinstance(item.get("fitment"), dict) else {}
    name = item.get("name")
    return _real_pns(
        _split_pns(item.get("part_numbers"))
        + _split_pns(fit.get("part_numbers"))
        + pns_from_name(name),
        name,
    )


def item_display_pns(item):
    """Primary part numbers only. Extra comma-blobs in later list entries are xrefs."""
    name = item.get("name")
    raw = item.get("part_numbers")
    if isinstance(raw, list) and raw:
        first = _real_pns(_split_pns(raw[0]), name)
        if first:
            return first
    named = _real_pns(pns_from_name(name), name)
    if named:
        return named
    all_pns = item_part_numbers(item)
    return all_pns[:1] if all_pns else []


def item_mpn(item):
    """Manufacturer PN for Product JSON-LD. Brand lives in schema.brand."""
    pns = item_display_pns(item)
    if not pns:
        return ""
    pn = pns[0]
    brand = brand_guess(item)
    if brand and brand != "BuccaneerSalvage Store":
        prefix = re.compile(rf"^{re.escape(brand)}\s+", re.I)
        stripped = prefix.sub("", pn).strip(" -")
        if stripped:
            return stripped
    return pn


def item_interchange(item):
    """Catalog interchange plus leftover part_numbers tokens (display only)."""
    fit = item.get("fitment") if isinstance(item.get("fitment"), dict) else {}
    primary = {p.lower() for p in item_display_pns(item)}
    xref = _uniq_keep(_split_pns(item.get("interchange")) + _split_pns(fit.get("interchange")))
    extras = [p for p in item_part_numbers(item) if p.lower() not in primary]
    return [x for x in _uniq_keep(xref + extras) if x.lower() not in primary]


def item_vehicles(item):
    return [s.replace("\u2013", "-").replace("\u2014", "-") for s in _uniq_keep(item.get("vehicles") or [])]


def pdp_fitment_html(item, esc_t):
    """Catalog Fits / interchange on the PDP — same data as store cards, full lists."""
    vehs = item_vehicles(item)
    pns = item_display_pns(item)
    xref = item_interchange(item)
    if not vehs and not pns and not xref:
        return ""
    blocks = []
    if pns:
        lis = "".join(f"<li>{esc_t(p)}</li>" for p in pns)
        blocks.append(
            '<div class="pdp-fitment-block">'
            '<p class="pdp-fitment-h">Part numbers</p>'
            f'<ul class="pdp-fitment-list">{lis}</ul></div>'
        )
    if xref:
        lis = "".join(f"<li>{esc_t(x)}</li>" for x in xref)
        blocks.append(
            '<div class="pdp-fitment-block">'
            '<p class="pdp-fitment-h">Interchange</p>'
            f'<ul class="pdp-fitment-list">{lis}</ul></div>'
        )
    if vehs:
        lis = "".join(f"<li>{esc_t(v)}</li>" for v in vehs)
        raw = item.get("vehicle_count_raw")
        extra = ""
        if isinstance(raw, int) and raw > len(vehs):
            extra = (
                f'<p class="pdp-fitment-note">{esc_t(str(raw))} eBay compatibility '
                "rows collapsed to these ranges.</p>"
            )
        blocks.append(
            '<div class="pdp-fitment-block">'
            '<p class="pdp-fitment-h">Fits (examples)</p>'
            f'<ul class="pdp-fitment-list">{lis}</ul>{extra}</div>'
        )
    note = (
        '<p class="pdp-fitment-note">Confirm the part fits your application before you order. '
        "Part numbers and example vehicles are aids, not a guarantee.</p>"
    )
    return (
        '<details class="pdp-fitment">'
        '<summary class="pdp-fitment-title">Fitment</summary>'
        + "".join(blocks)
        + note
        + "</details>"
    )


_VEH_YEAR_RE = re.compile(r"^(?:\d{4}\s*[-–—]\s*\d{4}|\d{4})\s+")
_TYPE_ALIAS = {
    "cv boot kit": "cv joint boot kit",
    "rolling lobe": "rolling lobe air spring",
}


def item_type_key(item):
    t = re.sub(r"\s+", " ", (item.get("ebay_type") or "").strip().lower())
    return _TYPE_ALIAS.get(t, t)


def _vehicle_key(v):
    s = _VEH_YEAR_RE.sub("", str(v or "").replace("\u2013", "-").replace("\u2014", "-"))
    return re.sub(r"\s+", " ", s).strip().lower()


def vehicle_keys(item):
    """Make+model tokens only. Year ranges do not make two SKUs the same part."""
    keys = set()
    for v in item.get("vehicles") or []:
        s = _vehicle_key(v)
        if s:
            keys.add(s)
    fit = item.get("fitment") if isinstance(item.get("fitment"), dict) else {}
    for row in fit.get("vehicles") or []:
        if not isinstance(row, dict):
            continue
        make = str(row.get("make") or "").strip().lower()
        model = str(row.get("model") or "").strip().lower()
        if make and model:
            keys.add(f"{make} {model}")
    return keys


def display_vehicle_keys(item, limit=3):
    """On-card applications only. Default first 3 (page headline). limit=None = full display list.

    Never walk fitment.vehicles — that is the 32-row eBay dump and matches Subaru
    Brat to a Chevy LUV cap.
    """
    keys = set()
    vehs = item_vehicles(item)
    if limit is not None:
        vehs = vehs[:limit]
    for v in vehs:
        s = _vehicle_key(v)
        if s:
            keys.add(s)
    return keys


def related_items(item, items, limit=4):
    """Same type, and a headline vehicle of THIS page appears on the sibling's display list."""
    typ = item_type_key(item)
    vehs = display_vehicle_keys(item)
    if not typ or not vehs:
        return []
    scored = []
    for other in items:
        if other.get("id") == item.get("id"):
            continue
        if not has_sale_price(other):
            continue
        if item_type_key(other) != typ:
            continue
        shared = vehs & display_vehicle_keys(other, limit=None)
        if not shared:
            continue
        scored.append((len(shared), other.get("name") or "", other))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[:limit]]


def also_stocked_items(item, items, limit=4):
    tokens = {p.lower() for p in item_part_numbers(item) + item_interchange(item) if len(p) >= 5}
    if not tokens:
        return []
    hits = []
    for other in items:
        if other.get("id") == item.get("id"):
            continue
        if not has_sale_price(other):
            continue
        ot = {p.lower() for p in item_part_numbers(other) + item_interchange(other) if len(p) >= 5}
        if tokens & ot:
            hits.append(other)
        if len(hits) >= limit:
            break
    return hits


def related_thumb(item):
    iid = str(item.get("id") or "")
    if re.fullmatch(r"[A-Z0-9]{16,32}", iid):
        local = HUB / "assets" / "product-thumbs" / f"{iid}.webp"
        if local.is_file():
            return f"../assets/product-thumbs/{iid}.webp"
    return safe_image(item.get("image")) or f"{BASE}/assets/og-share.jpg"


def related_card_title(item):
    name = str(item.get("name") or "Part")
    pns = item_display_pns(item)
    pn = pns[0] if pns else ""
    if pn:
        m = re.search(rf"\b{re.escape(pn)}\b", name, re.I)
        if m:
            prefix = name[: m.end()].strip(" -–—,")
            if 2 <= len(prefix) <= 42:
                return prefix
        brand = brand_guess(item)
        if brand and brand != "BuccaneerSalvage Store" and brand.lower() not in pn.lower():
            return f"{brand} {pn}"
        return pn
    return name if len(name) <= 42 else name[:39] + "..."


def related_card_note(item, shared_keys=None):
    typ = (item.get("ebay_type") or "").strip().lower()
    name = str(item.get("name") or "")
    bits = []
    temp = re.search(r"\b(1[5-9]\d|20[05])\b", name)
    if temp and "thermostat" in typ:
        bits.append(f"{temp.group(1)} F")
    vehs = item_vehicles(item)
    picked = ""
    if shared_keys:
        for v in vehs:
            if _vehicle_key(v) in shared_keys:
                picked = v
                break
    if not picked and vehs:
        picked = vehs[0]
    if picked:
        bits.append(picked)
    return " - ".join(bits[:2])


def related_card_html(other, esc, esc_t, shared_keys=None, slug=None):
    iid = str(other.get("id") or "")
    if not SQUARE_ID_RE.fullmatch(iid):
        return ""
    stem = slug or iid
    src = related_thumb(other)
    title = related_card_title(other)
    note = related_card_note(other, shared_keys=shared_keys)
    price = money(other.get("price"))
    note_html = f'<p class="pdp-rel-note">{esc_t(note)}</p>' if note else ""
    price_html = f'<p class="pdp-rel-price">{esc_t(price)}</p>' if price else ""
    return (
        f'<a class="pdp-rel-card" href="{esc(stem)}.html">'
        f'<span class="pdp-rel-media"><img src="{esc(src)}" alt="" width="200" height="200" loading="lazy" /></span>'
        f'<span class="pdp-rel-body">'
        f'<span class="pdp-rel-title">{esc_t(title)}</span>'
        f"{note_html}{price_html}"
        f"</span></a>"
    )


def catalog_browse_href(item):
    typ = (item.get("ebay_type") or "").strip()
    if typ:
        return f"../store.html?q={quote(typ)}"
    return "../store.html"


def related_html(item, items, esc, esc_t, slug_by_id=None):
    slug_by_id = slug_by_id or {}
    also = also_stocked_items(item, items)
    also_ids = {o.get("id") for o in also}
    related = [o for o in related_items(item, items) if o.get("id") not in also_ids]
    typ = (item.get("ebay_type") or "").strip()
    if not also and not related and not typ:
        return ""

    def _stem(other):
        oid = other.get("id")
        return slug_by_id.get(oid, oid)

    blocks = []
    if also:
        cards = "".join(related_card_html(o, esc, esc_t, slug=_stem(o)) for o in also)
        blocks.append(
            '<div class="pdp-related-block">'
            '<p class="pdp-related-h">Same part number</p>'
            f'<div class="pdp-related-grid">{cards}</div></div>'
        )
    if related:
        head = display_vehicle_keys(item)
        cards = "".join(
            related_card_html(
                o,
                esc,
                esc_t,
                shared_keys=head & display_vehicle_keys(o, limit=None),
                slug=_stem(o),
            )
            for o in related
        )
        blocks.append(
            '<div class="pdp-related-block">'
            '<p class="pdp-related-h">Same vehicles in this store</p>'
            f'<div class="pdp-related-grid">{cards}</div></div>'
        )
    if typ:
        label = f"Browse {typ.lower()} in the catalog"
        blocks.append(
            f'<p class="pdp-related-more"><a href="{esc(catalog_browse_href(item))}">{esc_t(label)}</a></p>'
        )
    return (
        '<section class="pdp-related" aria-label="Related parts">'
        + "".join(blocks)
        + "</section>"
    )


_BRAND_RE = re.compile(
    r"^(?:OEM\s+)?(Carlson|Automann|Goodyear|Continental|ContiTech|Firestone|Holset|"
    r"Mack|Wagner|Econoride|WIX|Gates|Mighty|Lee|NAPA|Parts\s+Master|Stant|Motorad|"
    r"Standard(?:\s+Motor\s+Products)?|Moog|Beck/Arnley|"
    r"Cloyes|Pace\s?Setter|AP\s+Exhaust|Medline|Masi)\b",
    re.I,
)


def brand_guess(item):
    """Real manufacturer brand for schema.org, not the seller name. Catalog
    part_numbers[0] is inconsistently brand-prefixed ("Holset X63" some
    items, bare "H2623" others) — checking the brand regex against it first
    would return "H2623" as a fake brand name for the second case. Try the
    regex against part_numbers[0] AND the title first; only fall back to
    treating part_numbers[0]'s raw first token as the brand when nothing
    recognizable matched (schema.org still requires *some* Brand)."""
    name = str(item.get("name") or "")
    parts = item.get("part_numbers")
    pn0 = str(parts[0]) if isinstance(parts, list) and parts and parts[0] else ""
    m = _BRAND_RE.match(pn0) or _BRAND_RE.match(name)
    if m:
        return m.group(1)
    if pn0:
        return pn0.split()[0]
    return "BuccaneerSalvage Store"


def offer_shipping_details(pickup=False, rate_value="0"):
    """GSC Merchant listings require shippingDetails on every Offer.

    rate_value is the live Square Ground snapshot ($4.99 / $6.99 / $9.99 / $0).
    Pickup-only: $0 local PA, not a missing field. Mack $40 is NOT applied —
    Square still ships those free until a $40 profile exists.
    """
    rate = "0" if pickup else str(rate_value or "0")
    if pickup:
        dest = {
            "@type": "DefinedRegion",
            "addressCountry": "US",
            "addressRegion": "PA",
        }
        handle = (0, 1)
        transit = (0, 1)
    else:
        dest = {"@type": "DefinedRegion", "addressCountry": "US"}
        handle = (1, 3)
        transit = (2, 7)
    return {
        "@type": "OfferShippingDetails",
        "shippingRate": {
            "@type": "MonetaryAmount",
            "value": rate,
            "currency": "USD",
        },
        "shippingDestination": dest,
        "deliveryTime": {
            "@type": "ShippingDeliveryTime",
            "handlingTime": {
                "@type": "QuantitativeValue",
                "minValue": handle[0],
                "maxValue": handle[1],
                "unitCode": "DAY",
            },
            "transitTime": {
                "@type": "QuantitativeValue",
                "minValue": transit[0],
                "maxValue": transit[1],
                "unitCode": "DAY",
            },
        },
    }


def offer_return_policy(category, force_no_returns=False):
    """Cores (or any item manually flagged via condition_warning): no returns.
    Other stock: 7-day unused mail return, buyer pays (hub store terms)."""
    if is_core(category) or force_no_returns:
        return {
            "@type": "MerchantReturnPolicy",
            "applicableCountry": "US",
            "returnPolicyCategory": "https://schema.org/MerchantReturnNotPermitted",
            "merchantReturnLink": "https://buccaneersalvage.github.io/terms.html#no-return",
        }
    return {
        "@type": "MerchantReturnPolicy",
        "applicableCountry": "US",
        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
        "merchantReturnDays": 7,
        "returnMethod": "https://schema.org/ReturnByMail",
        "returnFees": "https://schema.org/ReturnFeesCustomerResponsibility",
        "merchantReturnLink": "https://buccaneersalvage.github.io/terms.html#returns",
    }


SQUARE_ID_RE = re.compile(r"^[A-Z0-9]{16,32}$")
_SLUG_JUNK_RE = re.compile(r"[^a-z0-9]+")
_STORE_BRAND = "BuccaneerSalvage Store"
_SKIP_BRANDS = {_STORE_BRAND.lower(), "unbranded", "unknown", "n/a", "na", "none"}
_SLUG_STOP = {
    "vintage",
    "the",
    "a",
    "an",
    "and",
    "or",
    "for",
    "with",
    "from",
    "of",
    "to",
    "in",
    "on",
    "by",
    "nos",
    "oem",
    "new",
    "used",
    "original",
    "unboxed",
    "boxed",
    "as",
    "is",
    "asis",
    "untested",
    "tested",
    "working",
    "lot",
}
SLUG_MAX = 80


def slug_stem(text: str) -> str:
    s = _SLUG_JUNK_RE.sub("-", (text or "").lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:SLUG_MAX].strip("-")


def _slug_brand(item) -> str:
    brand = str(item.get("ebay_brand") or "").strip()
    if brand.lower() in _SKIP_BRANDS:
        return ""
    return brand


def pdp_slug_from_name(item, iid: str) -> str:
    """Canonical stem when there is no manufacturer PN. Never the Square id."""
    brand = _slug_brand(item)
    brand_stem = slug_stem(brand)
    brand_parts = set(brand_stem.split("-")) if brand_stem else set()
    tokens = []
    if brand_stem:
        tokens.append(brand_stem)
    for tok in re.split(r"[^a-z0-9]+", str(item.get("name") or "").lower()):
        if not tok or tok in _SLUG_STOP or tok in brand_parts:
            continue
        tokens.append(tok)
    stem = slug_stem("-".join(tokens))
    if stem and not SQUARE_ID_RE.fullmatch(stem.upper()):
        return stem
    fallback = slug_stem(f"item-{iid[:8].lower()}")
    return fallback or iid


def pdp_slug_base(item) -> str:
    iid = str(item.get("id") or "")
    mpn = item_mpn(item)
    if not mpn:
        return pdp_slug_from_name(item, iid)
    # Prefer ebay_brand (same as short_h1). brand_guess alone often returns the
    # PN token when the catalog PN is bare → mpn-mpn URLs (175-5866-175-5866).
    brand = str(item.get("ebay_brand") or brand_guess(item) or "").strip()
    if brand == _STORE_BRAND:
        brand = ""
    if brand and slug_stem(brand) == slug_stem(mpn):
        brand = ""
    if brand:
        stem = slug_stem(f"{brand}-{mpn}")
    else:
        stem = slug_stem(mpn)
    return stem or pdp_slug_from_name(item, iid)


def assign_pdp_slugs(items) -> dict:
    """Map Square catalog id → PDP filename stem (no .html)."""
    used = {"index"}
    out = {}
    for item in items:
        iid = str(item.get("id") or "")
        if not SQUARE_ID_RE.fullmatch(iid):
            continue
        base = pdp_slug_base(item)
        if base not in used:
            out[iid] = base
            used.add(base)
            continue
        n = 6
        stem = f"{base}-{iid[:n].lower()}"
        while stem in used:
            n += 2
            extra = iid[: min(n, len(iid))].lower()
            stem = f"{base}-{extra}"
            if n >= len(iid):
                break
        if stem in used:
            stem = iid.lower()
            while stem in used:
                stem = f"{stem}-x"
        used.add(stem)
        out[iid] = stem
    return out


def redirect_stub(slug: str) -> str:
    dest = f"{slug}.html"
    canonical = f"{BASE}/p/{slug}.html"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head>\n'
        '<meta charset="UTF-8" />\n'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'self'; form-action 'self'; object-src 'none'; frame-src 'none';\" />\n"
        '<meta name="referrer" content="strict-origin-when-cross-origin" />\n'
        f'<meta http-equiv="refresh" content="0;url={html.escape(dest, quote=True)}" />\n'
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}" />\n'
        '<meta name="robots" content="noindex" />\n'
        "<title>Redirecting</title>\n"
        "</head><body>"
        f'<p><a href="{html.escape(dest, quote=True)}">Continue to product</a></p>'
        "</body></html>\n"
    )
LISTED_DIR = Path.home() / "ebay" / "listings" / "listed"
# Paid Ground on Square today. Mack 255310368025 stays $0 until a $40 profile exists.
POLICY_SHIP = {
    "255700469025": "4.99",
    "255698066025": "6.99",
    "255699762025": "9.99",
    "255310368025": "0",
}
SHIP_LABEL = {
    "4.99": "USPS Ground $4.99",
    "6.99": "USPS Ground $6.99",
    "9.99": "USPS Ground $9.99",
    "0": "Free UPS Ground",
}
# Fallback if this box has no listing archive. Overlay from 1-listing.txt when present.
HARD_SHIP = {
    "BYO4CA2ORO6PIIHKJ6BAJ7Z5": "4.99",
    "RKN2JXFL3XHP336C6I2YOVYM": "4.99",
    "3HECI35NLXOYFBNMJGGQQMUZ": "4.99",
    "GVRZ63WJMUPNZMLBI7E7T4IL": "4.99",
    "373RPPOCYAZFVEE4KH3VYLOY": "4.99",
    "KWUGHUPGLK47T522IA5P64RO": "4.99",
    "EEUYTJ4KFBEUW5XH5XRUB7MY": "4.99",
    "H6Q3563YMDVDRCI5XLGMRMT4": "4.99",
    "OTIMLXHJMRAYFTXR75WVSIJB": "4.99",
    "EMXCDDO3NAY5ZYHOO65VXABA": "4.99",
    "DP5UVELMRAQLBRRNSJS3XJGW": "4.99",
    "TYCTXARZCA52YYA77WU4XAXK": "4.99",
    "5G7Z5QJDPCHBUW2RVCMEPSUF": "4.99",
    "3Z3CTEYBJDYCBIMPPBFXDWUJ": "4.99",
    "3OWZS3ISWMJZVCMUFT6OS3KN": "4.99",
    "EHUOULWBV4R75M7XZ637YI53": "4.99",
    "L2WKO2ULQ7O5QGGG5EUEGBUS": "4.99",
    "HEJTHZORA24YEBW7HUDRXTC7": "4.99",
    "LGZZPJQWT53QGCJJGEC7WEQY": "4.99",
    "H2KTSFW7IOZFKZ7KKIZ5XH5E": "4.99",
    "MGEJQB5FNUM2OD3WUEXA4O5E": "4.99",
    "VILXTGQE22JC74IXOZVYGRZ7": "4.99",
    "SOVPCCSZ73M64UEM44DEPXZV": "4.99",
    "AUOSVBXBNJOIRGAAZUG3QROD": "4.99",
    "KBKJI6VPGFJ2ZZTFUNNPRVYF": "4.99",
    "WSR2S2C5RX72S2HL6DGJAVIZ": "4.99",
    "2IGN4TREF7DNKIIYWCK3U4BR": "4.99",
    "KTQC3YPSDMZIGSNXVF2NPNNH": "6.99",
    "63OAZL34SLIPTN2MLXG3LDPV": "6.99",
    "MMRUWQ4EHOC5PLIMLAR6TNQH": "6.99",
    "4ZIBBGXFF65NRMKSS3IQ2R3T": "9.99",
}


def load_ship_map():
    """Square id -> rate string. Listing archive wins; HARD_SHIP fills gaps."""
    out = dict(HARD_SHIP)
    if LISTED_DIR.is_dir():
        for d in LISTED_DIR.iterdir():
            if not d.is_dir():
                continue
            sid = d / "square_item_id.txt"
            lst = d / "1-listing.txt"
            if not sid.is_file() or not lst.is_file():
                continue
            iid = sid.read_text(encoding="utf-8", errors="ignore").strip()
            if not SQUARE_ID_RE.fullmatch(iid):
                continue
            text = lst.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^SHIPPING POLICY:\s*(\d+)", text, re.M)
            if not m:
                continue
            out[iid] = POLICY_SHIP.get(m.group(1), "0")
    return out


def ship_for_item(iid, ship_map, pickup=False):
    if pickup:
        return "0", "Pickup only — Carbondale, PA"
    rate = str((ship_map or {}).get(iid) or "0")
    if rate not in SHIP_LABEL:
        rate = "0"
    return rate, SHIP_LABEL[rate]


def site_product_url(iid):
    s = str(iid or "").strip()
    if not SQUARE_ID_RE.fullmatch(s):
        return ""
    return f"https://buccaneersalvage.square.site/product/{s}"


def short_h1(item):
    """Brand + PN + one hook. Long eBay title stays in <title>/meta/schema."""
    brand = str(item.get("ebay_brand") or brand_guess(item) or "").strip()
    if brand == "BuccaneerSalvage Store":
        brand = ""
    pns = item_display_pns(item)
    pn = pns[0] if pns else ""
    name = str(item.get("name") or "")
    typ = str(item.get("ebay_type") or "").lower()
    hook = ""
    temp = re.search(r"\b(1[5-9]\d|20[05])\b", name)
    if temp and "thermostat" in typ:
        hook = f"{temp.group(1)} F"
    else:
        vehs = item_vehicles(item)
        if vehs:
            hook = vehs[0]
    bits = []
    if brand:
        bits.append(brand)
    if pn and pn.lower() not in " ".join(bits).lower():
        bits.append(pn)
    if not bits:
        return name if len(name) <= 72 else name[:69] + "…"
    head = " ".join(bits)
    return f"{head} · {hook}" if hook else head


def breadcrumb_json(canonical, catl, typ, leaf):
    items = [
        {"@type": "ListItem", "position": 1, "name": "Store", "item": f"{BASE}/store.html"},
    ]
    parent = (typ or catl or "").strip()
    if parent:
        items.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": parent,
                "item": f"{BASE}/store.html?q={quote(parent)}",
            }
        )
    items.append(
        {
            "@type": "ListItem",
            "position": len(items) + 1,
            "name": leaf,
            "item": canonical,
        }
    )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def safe_item_id(iid):
    s = str(iid or "").strip()
    if not SQUARE_ID_RE.fullmatch(s):
        raise SystemExit(f"ERROR: catalog id is not a Square id: {iid!r}")
    return s


def safe_checkout(u):
    s = str(u or "").strip()
    if not s.startswith("https://"):
        return ""
    try:
        parsed = urlparse(s)
        if parsed.scheme != "https":
            return ""
        host = (parsed.hostname or "").lower()
        if host == "buccaneersalvage.square.site":
            parts = [p for p in (parsed.path or "").split("/") if p]
            if len(parts) >= 2 and parts[0] == "product" and SQUARE_ID_RE.fullmatch(parts[-1]):
                return f"https://buccaneersalvage.square.site/product/{parts[-1]}"
            return ""
        if host == "square.link" or host.endswith(".square.link"):
            return s
    except Exception:
        pass
    return ""


def safe_video(u):
    """Self-hosted only — a relative path under assets/videos/, never an external URL.
    Square/eBay have no video field to trust; this only ever comes from a manual
    catalog.json patch, so keep it locked to our own repo path as defense in depth."""
    s = str(u or "").strip()
    if not s or s.startswith(("http://", "https://", "//")) or ".." in s:
        return ""
    if not re.match(r"^assets/videos/[\w.\-]+\.(mp4|webm)$", s):
        return ""
    return s


_LOCAL_GALLERY_RE = re.compile(r"^\.\./assets/pdp-gallery/[A-Z0-9]{16,32}/\d{2}\.webp$")
_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_GALLERY_MAX = 6
_GALLERY_EDGE = 1400
LISTED = Path.home() / "ebay" / "listings" / "listed"
GALLERY_DIR = HUB / "assets" / "pdp-gallery"


def listing_photo_files(ebay_item_id):
    eid = str(ebay_item_id or "").strip()
    if not eid.isdigit() or not LISTED.is_dir():
        return []
    best = []
    for folder in sorted(LISTED.glob(f"{eid}-*")):
        photos = folder / "photos"
        if not photos.is_dir():
            continue
        files = sorted(
            p for p in photos.iterdir() if p.is_file() and p.suffix.lower() in _PHOTO_EXTS
        )
        if len(files) > len(best):
            best = files
    return best


def _save_webp(src, dest):
    from PIL import Image
    im = Image.open(src)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    elif im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (12, 10, 8))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im.thumbnail((_GALLERY_EDGE, _GALLERY_EDGE), Image.Resampling.LANCZOS)
    im.save(dest, format="WEBP", quality=78, method=4)


def ensure_hero_webp(item, fallback):
    """Local optimized 01.webp hero when a gallery dir already exists for the item."""
    iid = safe_item_id(item.get("id"))
    dest_dir = GALLERY_DIR / iid
    if not dest_dir.is_dir():
        return fallback
    files = listing_photo_files(item.get("ebay_item_id"))
    if not files:
        return fallback
    try:
        from PIL import Image
    except ImportError:
        return fallback
    dest = dest_dir / "01.webp"
    if not dest.is_file() or dest.stat().st_mtime < files[0].stat().st_mtime:
        _save_webp(files[0], dest)
    return f"../assets/pdp-gallery/{iid}/01.webp"


def ensure_listing_gallery(item):
    """Extra shots from the eBay listing folder. Skip photo-01 (usually the Square hero)."""
    iid = safe_item_id(item.get("id"))
    if not iid:
        return []
    extras = listing_photo_files(item.get("ebay_item_id"))[1 : 1 + _GALLERY_MAX]
    if not extras:
        return []
    try:
        from PIL import Image  # noqa: F401 — availability check only
    except ImportError:
        return []
    dest_dir = GALLERY_DIR / iid
    dest_dir.mkdir(parents=True, exist_ok=True)
    urls = []
    for i, src in enumerate(extras, start=2):
        dest = dest_dir / f"{i:02d}.webp"
        if not dest.is_file() or dest.stat().st_mtime < src.stat().st_mtime:
            _save_webp(src, dest)
        urls.append(f"../assets/pdp-gallery/{iid}/{i:02d}.webp")
    return urls


def schema_image_url(u):
    s = str(u or "")
    if s.startswith("../"):
        return f"{BASE}/{s[3:]}"
    return s


def safe_image(u):
    s = str(u or "").strip()
    if _LOCAL_GALLERY_RE.fullmatch(s):
        return s
    if not s.startswith("https://"):
        return ""
    try:
        parsed = urlparse(s)
        if parsed.scheme != "https":
            return ""
        host = (parsed.hostname or "").lower()
        if (
            host == "buccaneersalvage.github.io"
            or host.endswith(".squareup.com")
            or host.endswith(".squarecdn.com")
            or host == "items-images-production.s3.us-west-2.amazonaws.com"
        ):
            return s
    except Exception:
        pass
    return ""


def main() -> None:
    cat = json.loads((HUB / "assets/square-catalog.json").read_text())
    items = [i for i in cat["items"] if has_sale_price(i)]
    out_dir = HUB / "p"
    out_dir.mkdir(exist_ok=True)
    ship_map = load_ship_map()
    slugs_path = HUB / "assets" / "pdp-slugs.json"
    prev_slugs = {}
    if slugs_path.is_file():
        try:
            prev = json.loads(slugs_path.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                prev_slugs = prev
        except (json.JSONDecodeError, OSError):
            prev_slugs = {}
    slug_by_id = assign_pdp_slugs(items)
    slugs_path.write_text(
        json.dumps(slug_by_id, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    written = []
    stubs = []
    for item in items:
        iid = safe_item_id(item.get("id"))
        slug = slug_by_id[iid]
        name = item.get("name") or "Product"
        price_n = item.get("price")
        price = money(price_n)
        try:
            stock_n = int(item.get("stock"))
        except (TypeError, ValueError):
            stock_n = None
        sold_out = stock_n is not None and stock_n <= 0
        catl = dept_label(item)
        desc_kind = item_ebay_tree(item).get("sub") or cat_label(item.get("category"))
        img = safe_image(item.get("image")) or f"{BASE}/assets/og-share.jpg"
        img = ensure_hero_webp(item, img)
        gallery_raw = [safe_image(u) for u in (item.get("images") or [])]
        gallery = [u for u in gallery_raw if u and u != img]
        if not gallery:
            gallery = [u for u in (safe_image(u) for u in ensure_listing_gallery(item)) if u]
        video = safe_video(item.get("video"))
        # square.site/product/{catalogId} is a dead Square SPA shell ($0.00).
        # Real checkout is the catalog square.link payment URL.
        checkout = safe_checkout(item.get("url"))
        store = item_store_tree(item)
        store_parent = store["parent"]
        # Manual per-item override (Square/eBay have no such field) — same
        # preserved-across-resync pattern as video/images. Lets a specific
        # item state its real condition (e.g. "tested, sold for parts/repair,
        # no returns") instead of the generic turbo/pump core warning, which
        # would say "UNTESTED" even on an item that was run on video.
        custom_warn = str(item.get("condition_warning") or "").strip()
        pickup = pickup_only(custom_warn, name)
        no_returns = is_core(item.get("category")) or bool(custom_warn) or pickup
        ship_from = (
            "Pickup only - Carbondale, PA 18407. No shipping."
            if pickup
            else "Carbondale, PA 18407"
        )
        ship_rate, ship_label = ship_for_item(iid, ship_map, pickup=pickup)
        # On-page H1 matches Square/eBay catalog name. short_h1 dropped type +
        # YMM ("Gates 5536 · 160 F") while checkout still showed the full title.
        heading = name.strip() or short_h1(item)
        ebay_type = str(item.get("ebay_type") or "").strip()
        leaf_crumb = heading
        # Google truncates SERP titles around ~60 chars. Catalog product names
        # (sourced from eBay listing titles) commonly run 60-100+ chars on
        # their own — appending " | BuccaneerSalvage Store" (24 chars) to an
        # already-long name only pushed the truncation point further into the
        # name itself while burying the brand suffix nobody sees anyway.
        # Drop the suffix once it would put the title over budget; the store
        # name still appears via og:site_name / structured data either way.
        _BRAND_SUFFIX = " | BuccaneerSalvage Store"
        title = name if len(name) + len(_BRAND_SUFFIX) > 60 else f"{name}{_BRAND_SUFFIX}"
        desc = pdp_desc(item, name, desc_kind, price, custom_warn)
        canonical = f"{BASE}/p/{slug}.html"
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "@id": f"{canonical}#product",
            "name": name,
            "description": desc,
            "image": [schema_image_url(u) for u in ([img, *gallery] if gallery else [img])],
            "sku": iid,
            "brand": {"@type": "Brand", "name": brand_guess(item)},
            "isPartOf": {
                "@type": "WebSite",
                "@id": f"{BASE}/store.html#website",
                "name": "BuccaneerSalvage Store",
                "url": f"{BASE}/store.html",
            },
            "offers": {
                "@type": "Offer",
                "url": checkout or canonical,
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
                "seller": {
                    "@type": "Store",
                    "@id": f"{BASE}/store.html#store",
                    "name": "BuccaneerSalvage Store",
                    "url": f"{BASE}/store.html",
                },
                "hasMerchantReturnPolicy": offer_return_policy(item.get("category"), force_no_returns=no_returns),
                "shippingDetails": offer_shipping_details(pickup=pickup, rate_value=ship_rate),
            },
        }
        if pickup:
            schema["offers"]["availableDeliveryMethod"] = "https://schema.org/OnSitePickup"
        if re.search(r"\bNOS\b", name):
            schema["itemCondition"] = "https://schema.org/NewCondition"
        mpn = item_mpn(item)
        if mpn:
            schema["mpn"] = mpn
        if price_n is not None:
            schema["offers"]["price"] = str(price_n)
        if video:
            clip = HUB / video
            schema["video"] = {
                "@type": "VideoObject",
                "name": f"{name} - test run",
                "description": f"Test-run clip of {name}.",
                "thumbnailUrl": [img],
                "contentUrl": f"{BASE}/{video}",
            }
            if clip.is_file():
                schema["video"]["uploadDate"] = datetime.fromtimestamp(
                    clip.stat().st_mtime, tz=ZoneInfo("America/New_York")
                ).isoformat()

        # json.dumps does not escape "<" — a catalog item `name` containing
        # "</script><script>..." (or just "</script><meta http-equiv=refresh...")
        # would close this tag early and get parsed as raw HTML. name/description
        # come straight from Square with no validation (unlike image/url, which
        # go through safe_image()/safe_checkout()). Standard JSON-in-HTML
        # mitigation: escape "<" as its unicode form, which is a no-op for JSON
        # parsers but stops the browser's HTML tokenizer from ever seeing "</script>".
        schema_json = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")
        crumbs_json = json.dumps(
            breadcrumb_json(canonical, catl, store_parent, leaf_crumb),
            ensure_ascii=False,
        ).replace("<", "\\u003c")

        def esc(s):
            return html.escape(str(s or ""), quote=True)

        def esc_t(s):
            return html.escape(str(s or ""))

        if checkout and not sold_out:
            nav_cta = f'<a class="nav-cta" href="{esc(checkout)}" target="_blank" rel="noopener noreferrer">Buy now</a>'
            add_attrs = (
                f' class="btn btn-primary pdp-add-cart" type="button"'
                f' data-id="{esc(iid)}" data-photo="{esc(img)}" data-title="{esc(heading)}"'
                f' data-price="{esc(price or "Contact for price")}"'
                f' data-ship="{esc(ship_label)}" data-checkout="{esc(checkout)}"'
                + (f' data-stock="{esc(stock_n)}"' if stock_n is not None else "")
            )
            cta = f'<button{add_attrs}>Add to cart</button>'
            buybar_cta = f'<button{add_attrs}>Add to cart</button>'
        elif checkout and sold_out:
            nav_cta = '<a class="nav-cta is-disabled" href="../store.html">Buy now</a>'
            cta = '<span class="btn btn-primary is-disabled" aria-disabled="true">Out of stock</span>'
            buybar_cta = cta
        else:
            nav_cta = '<a class="nav-cta is-disabled" href="../store.html">Buy now</a>'
            cta = '<span class="btn btn-primary is-disabled" aria-disabled="true">Not available for purchase</span>'
            buybar_cta = cta
        if stock_n is None:
            stock_html = ""
        elif stock_n <= 0:
            stock_html = '<p class="pdp-stock is-out">Out of stock</p>'
        elif stock_n == 1:
            stock_html = '<p class="pdp-stock is-low">Only 1 left</p>'
        else:
            stock_html = f'<p class="pdp-stock">{stock_n} in stock</p>'
        crumb_mid = (
            f'<span aria-hidden="true">/</span><span>{esc_t(store_parent)}</span>'
            if store_parent
            else ""
        )
        checkout_href = f' href="{esc(checkout)}"' if checkout else ""
        if custom_warn:
            warn = f'<p class="pdp-warn">{esc_t(custom_warn)}</p>'
        elif is_core(item.get("category")):
            warn = '<p class="pdp-warn">FOR PARTS OR REBUILD · UNTESTED · NO RETURNS</p>'
        else:
            warn = ""
        fitment = pdp_fitment_html(item, esc_t)
        related = related_html(item, items, esc, esc_t, slug_by_id=slug_by_id)
        img_tag = f'<img id="pdpMainImage" class="pdp-image" src="{esc(img)}" alt="{esc(name)}" width="600" height="600" />'
        video_el = (
            f'<video id="pdpMainVideo" class="pdp-video" controls preload="metadata" '
            f'poster="{esc(img)}" hidden><source src="{esc(f"../{video}")}" type="video/mp4" />'
            f"Your browser doesn't support embedded video.</video>"
            if video
            else ""
        )
        # Thumbnails are buttons, not links — clicking swaps the stage in place
        # (pdp-gallery.js) instead of opening a new tab. Hero photo first
        # (starts active), then the rest of the gallery, then video last.
        thumbs = (
            f'<button type="button" class="pdp-thumb-btn is-active" data-type="image" '
            f'data-src="{esc(img)}" aria-label="{esc_t(name)} - main photo">'
            f'<img class="pdp-thumb" src="{esc(img)}" alt="" width="100" height="100" loading="lazy" /></button>'
        )
        thumbs += "".join(
            f'<button type="button" class="pdp-thumb-btn" data-type="image" data-src="{esc(u)}" '
            f'aria-label="{esc_t(name)} - additional photo">'
            f'<img class="pdp-thumb" src="{esc(u)}" alt="" width="100" height="100" loading="lazy" /></button>'
            for u in gallery
        )
        if video:
            thumbs += (
                f'<button type="button" class="pdp-thumb-btn pdp-thumb-video" data-type="video" '
                f'aria-label="{esc_t(name)} - test-run video">'
                f'<img class="pdp-thumb" src="{esc(img)}" alt="" width="100" height="100" loading="lazy" />'
                f'<span class="pdp-thumb-play" aria-hidden="true">&#9654;</span></button>'
            )
        gallery_tag = (
            f'<div class="pdp-gallery" role="group" aria-label="Product photos and video">{thumbs}</div>'
            if (gallery or video)
            else ""
        )
        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{esc_t(title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
  <meta name="theme-color" content="#0c0a08" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://items-images-production.s3.us-west-2.amazonaws.com https://*.squareup.com https://*.squarecdn.com; media-src 'self'; font-src 'self' data:; connect-src 'self' https://buc-square-checkout.jollyroger1480.workers.dev; base-uri 'self'; form-action 'self'; object-src 'none'; frame-src 'none';" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <link rel="canonical" href="{esc(canonical)}" />
  <meta property="og:type" content="product" />
  <meta property="og:site_name" content="BuccaneerSalvage Store" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(desc)}" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta property="og:image" content="{esc(img)}" />
  <meta property="og:locale" content="en_US" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc(title)}" />
  <meta name="twitter:description" content="{esc(desc)}" />
  <meta name="twitter:image" content="{esc(img)}" />
  <link rel="icon" type="image/jpeg" href="../assets/crest-rustjack-web.jpg" />
  <link rel="stylesheet" href="../assets/fonts.css?v=d1b92d3ff4" integrity="sha384-IDnmxIHyfCaSAssmrqXZbMSqgbRm8AATad26bBSjsyTVbgLbsvJXqeQW642rJQFS" />
  <link rel="stylesheet" href="../styles.css?v=e9c261a233" integrity="sha384-8+UN2qmZ2NC8GALGJsiKUYqzm3NU+kF92hNA/r4yhornXJOiFInzs9lHrvwv4K9q" />
  <script type="application/ld+json">{schema_json}</script>
  <script type="application/ld+json">{crumbs_json}</script>
  <script src="../pdp-gallery.js?v=c0683cc878" integrity="sha384-Nj6Y6bFnU9x3YJ9AyAWSOJX+uvPDgCk5a/sSqAuEm5Q4zqfdhyfQMQg8SrGb8Goq" defer></script>
  <script src="../main.js?v=d62911a0a1" integrity="sha384-bjTL+oi4j/tRjU7Pb35mIoEkSoQBENgMgmuTO+kkh1Uy+OYkHUlFwJpFWzgPZoME" defer></script>
</head>
<body class="page-item">
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav is-solid" role="banner" id="nav">
    <div class="nav-inner">
      <a class="nav-brand" href="../store.html" aria-label="BuccaneerSalvage Store home">
        <picture><source type="image/webp" srcset="../assets/crest-rustjack-web.webp" /><img class="nav-mark" src="../assets/crest-rustjack-web.jpg" width="38" height="38" alt="BuccaneerSalvage Jolly Roger logo" /></picture>
        <span class="nav-word">BuccaneerSalvage Store</span>
      </a>
      <nav class="nav-links" aria-label="Primary">
        <a href="../index.html">Home</a>
        <a href="../store.html">Store</a>
      </nav>
      <button type="button" class="nav-cart" aria-label="Cart">Cart<span class="nav-cart-count" hidden></span></button>
      {nav_cta}
      <button class="nav-toggle" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="drawer" id="navToggle">
        <span></span>
      </button>
    </div>
    <div class="nav-drawer" id="drawer" hidden>
      <a href="../index.html">Home</a>
      <a href="../store.html">Store catalog</a>
      <a href="../terms.html">Terms &amp; returns</a>
      <a href="../privacy.html">Privacy</a>
      <a href="../shame.html">Buyer hall of shame</a>
      <a href="../videos.html">Music</a>
      <a href="../ukiri/">Ukiri warning</a>
    </div>
  </header>
  <main id="main">
    <section class="pdp-hero">
      <div class="shell pdp-hero-inner">
        <nav class="pdp-breadcrumb" aria-label="Breadcrumb">
          <a href="../store.html">Store</a>
          {crumb_mid}
          <span aria-hidden="true">/</span>
          <span>{esc_t(leaf_crumb)}</span>
        </nav>
      </div>
    </section>
    <section class="pdp-content">
      <div class="shell pdp-layout">
        <div class="pdp-media">
          <div class="pdp-stage">{img_tag}{video_el}</div>
          {gallery_tag}
        </div>
        <div class="pdp-info pdp-rail">
          <h1 class="pdp-title">{esc_t(heading)}</h1>
          <p class="pdp-category">{esc_t(store_parent)}</p>
          <p class="pdp-price">{esc_t(price or "Contact for price")}</p>
          <p class="pdp-ship"><strong>Shipping:</strong> {esc_t(ship_label)}</p>
          {stock_html}
          {warn}
          <div class="pdp-cta-group">
            {cta}
            <a href="../store.html" class="btn btn-secondary">Back to store</a>
          </div>
          {fitment}
          <div class="pdp-meta">
            <p><strong>Secure checkout:</strong> Card processing off-site on Square</p>
            <p><strong>Ships from:</strong> {esc_t(ship_from)}</p>
            <p><strong>Local pickup:</strong> By appointment</p>
            <p><strong>Returns:</strong> {esc_t("Sold as-is, no returns." if no_returns else "7 days on most unused parts. Buyer remorse: 15% restocking. Cores, opened, and used items: no returns.")} <a href="../terms.html#{'no-return' if no_returns else 'returns'}">Store terms</a>.</p>
          </div>
        </div>
        {related}
      </div>
    </section>
  </main>
  <div class="pdp-buybar" aria-label="Buy">
    <span class="pdp-buybar-price">{esc_t(price or "")}</span>
    {buybar_cta}
  </div>
  <div id="pdpCartOverlay" class="pdp-cart-overlay" hidden></div>
  <aside id="pdpCartDrawer" class="pdp-cart-drawer" hidden aria-label="Cart">
    <button type="button" class="pdp-cart-close" aria-label="Close">×</button>
    <div id="pdpCartBody"></div>
    <p class="pdp-cart-note">Local pickup by appointment in Carbondale, PA. Checkout opens the Square cart with this item&apos;s real shipping.</p>
    <a class="btn btn-primary" data-bind="checkout"{checkout_href} target="_blank" rel="noopener noreferrer">Continue to checkout</a>
  </aside>
  <div id="pdpLightbox" class="pdp-lightbox" hidden>
    <button type="button" class="pdp-lightbox-close" aria-label="Close photo">×</button>
    <div class="pdp-lightbox-stage"><img id="pdpLightboxImage" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="" /></div>
  </div>
  <footer role="contentinfo" class="footer">
    <div class="shell footer-bottom">
      <span>© <span id="y">2026</span> Rustjack · BuccaneerSalvage Store</span>
      <nav class="footer-links" aria-label="More">
        <a href="../terms.html">Terms</a>
        <a href="../privacy.html">Privacy</a>
        <a href="../videos.html">Music</a>
        <a href="../shame.html">Hall of shame</a>
        <a href="https://www.youtube.com/@BuccaneerSalvage" target="_blank" rel="noopener noreferrer">YouTube</a>
        <a href="https://x.com/jollyroger1480" target="_blank" rel="noopener noreferrer">X</a>
        <a href="https://www.ebay.com/str/buccaneersalvage" target="_blank" rel="noopener noreferrer">eBay</a>
        <a href="/ukiri/">Ukiri dossier</a>
      </nav>
    </div>
  </footer>
</body>
</html>
"""
        dest = (out_dir / f"{slug}.html").resolve()
        if dest.parent != out_dir.resolve():
            raise SystemExit(f"ERROR: PDP path escaped p/: {dest}")
        dest.write_text(page, encoding="utf-8")
        written.append(slug)
        if slug != iid:
            stub_path = (out_dir / f"{iid}.html").resolve()
            if stub_path.parent != out_dir.resolve():
                raise SystemExit(f"ERROR: stub path escaped p/: {stub_path}")
            stub_path.write_text(redirect_stub(slug), encoding="utf-8")
            stubs.append(iid)

    used_names = set(written) | set(stubs) | {"index"}
    for iid, old_slug in prev_slugs.items():
        if not isinstance(old_slug, str) or not old_slug:
            continue
        new_slug = slug_by_id.get(iid)
        if not new_slug or old_slug in (new_slug, iid):
            continue
        if old_slug in used_names:
            continue
        stub_path = (out_dir / f"{old_slug}.html").resolve()
        if stub_path.parent != out_dir.resolve():
            raise SystemExit(f"ERROR: stub path escaped p/: {stub_path}")
        stub_path.write_text(redirect_stub(new_slug), encoding="utf-8")
        stubs.append(old_slug)
        used_names.add(old_slug)

    keep = set(written) | set(stubs) | {"index"}
    stub_refresh_re = re.compile(r"url=([A-Za-z0-9-]+)\.html")
    for stale in out_dir.glob("*.html"):
        if stale.stem in keep:
            continue
        try:
            old_html = stale.read_text(encoding="utf-8")
        except OSError:
            old_html = ""
        # Keep a superseded-slug noindex stub if it still points at a
        # canonical this run wrote. pdp-slugs.json only stores the current
        # stem, so year-PN → name slugs would 404 on the next rebuild.
        m = stub_refresh_re.search(old_html)
        if m and m.group(1) in keep and "noindex" in old_html:
            keep.add(stale.stem)
            continue
        stale.unlink()
        print(f"removed stale PDP {stale.name}")

    if len(written) != len(items):
        raise SystemExit(f"ERROR: wrote {len(written)} PDPs != catalog {len(items)}")

    (out_dir / "index.html").write_text(
        f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'self'; form-action 'self'; object-src 'none'; frame-src 'none';" />
<meta name="referrer" content="strict-origin-when-cross-origin" />
<meta http-equiv="refresh" content="0;url=../store.html" />
<link rel="canonical" href="{BASE}/store.html" />
<meta name="robots" content="noindex" />
<title>Redirecting to store</title>
</head><body><p><a href="../store.html">BuccaneerSalvage Store</a></p></body></html>
""",
        encoding="utf-8",
    )

    # sitemaps — lastmod was a hardcoded 2026-08-04 literal on every one of
    # the 198 product entries regardless of whether that item's data actually
    # changed, on every regen since. Not per-item-accurate (that needs a
    # diff against the previous catalog, tracked elsewhere), but today's date
    # is honest now that buccaneer_sync only regenerates when the catalog
    # actually changed (see buccaneer_sync.py fix, 2026-08-14) — a frozen
    # fake date never helped crawlers prioritize anything.
    today = date.today().isoformat()

    def url_entry(loc, pri="0.7"):
        return f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>{pri}</priority>
  </url>"""

    store_urls = [url_entry(f"{BASE}/store.html", "0.95")]
    for slug in written:
        store_urls.append(url_entry(f"{BASE}/p/{slug}.html"))
    (HUB / "sitemap-store.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(store_urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    print(f"OK {len(written)} static PDPs → {out_dir}")
    assert_named_product_pages(HUB)


def is_pdp_redirect_stub(page: str) -> bool:
    """True when the file is a noindex meta-refresh, not a product page."""
    return (
        "http-equiv=\"refresh\"" in page
        and "noindex" in page
        and 'class="pdp-title"' not in page
    )


def assert_named_product_pages(hub: Path) -> None:
    """Canonical PDP files must be named product HTML, not Square-ID stubs.

    Catalog / sitemap / store.js all point at p/{slug}.html. A tree of only
    ID refresh stubs 404s every catalog click (Lost at Sea). Square-ID files
    may be stubs; the slug file must contain the product name in an H1.
    """
    hub = Path(hub)
    cat = json.loads((hub / "assets" / "square-catalog.json").read_text(encoding="utf-8"))
    items = [i for i in cat["items"] if has_sale_price(i)]
    slugs = json.loads((hub / "assets" / "pdp-slugs.json").read_text(encoding="utf-8"))
    out_dir = hub / "p"
    missing = []
    stub_canonicals = []
    nameless = []
    for item in items:
        iid = str(item.get("id") or "")
        slug = slugs.get(iid)
        name = str(item.get("name") or "").strip()
        if not slug:
            missing.append(iid)
            continue
        path = out_dir / f"{slug}.html"
        if not path.is_file():
            missing.append(slug)
            continue
        page = path.read_text(encoding="utf-8")
        if is_pdp_redirect_stub(page):
            stub_canonicals.append(slug)
            continue
        esc_name = html.escape(name)
        if 'class="pdp-title"' not in page or (
            name and esc_name not in page and name not in page
        ):
            nameless.append(slug)
    problems = []
    if missing:
        problems.append(f"missing named PDP ({len(missing)}): {missing[:8]}")
    if stub_canonicals:
        problems.append(
            f"canonical is redirect stub ({len(stub_canonicals)}): {stub_canonicals[:8]}"
        )
    if nameless:
        problems.append(f"canonical missing product name H1 ({len(nameless)}): {nameless[:8]}")
    if problems:
        raise SystemExit("ERROR: named PDP gate: " + " | ".join(problems))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        target = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else HUB
        assert_named_product_pages(target)
        print(f"OK named PDP gate → {target}")
    else:
        main()
