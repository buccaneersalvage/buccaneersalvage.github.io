#!/usr/bin/env python3
"""Regenerate static PDP pages under p/{id}.html for no-JS crawler SEO."""
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
from dept_tree import dept_label, item_ebay_tree

HUB = Path(__file__).resolve().parents[1]
BASE = "https://buccaneersalvage.github.io"


def money(n):
    try:
        return f"${float(n):,.2f}"
    except Exception:
        return ""


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


def item_part_numbers(item):
    fit = item.get("fitment") if isinstance(item.get("fitment"), dict) else {}
    return _uniq_keep(
        _split_pns(item.get("part_numbers"))
        + _split_pns(fit.get("part_numbers"))
        + pns_from_name(item.get("name"))
    )


def item_display_pns(item):
    """Primary part numbers only. Extra comma-blobs in later list entries are xrefs."""
    raw = item.get("part_numbers")
    if isinstance(raw, list) and raw:
        first = _uniq_keep(_split_pns(raw[0]))
        if first:
            return first
    named = pns_from_name(item.get("name"))
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
        '<section class="pdp-fitment" aria-label="Fitment">'
        '<h2 class="pdp-fitment-title">Fitment</h2>'
        + "".join(blocks)
        + note
        + "</section>"
    )


_VEH_YEAR_RE = re.compile(r"^(?:\d{4}\s*[-–—]\s*\d{4}|\d{4})\s+")
_TYPE_ALIAS = {
    "cv boot kit": "cv joint boot kit",
    "rolling lobe": "rolling lobe air spring",
}


def item_type_key(item):
    t = re.sub(r"\s+", " ", (item.get("ebay_type") or "").strip().lower())
    return _TYPE_ALIAS.get(t, t)


def vehicle_keys(item):
    """Make+model tokens only. Year ranges do not make two SKUs the same part."""
    keys = set()
    for v in item.get("vehicles") or []:
        s = _VEH_YEAR_RE.sub("", str(v).replace("\u2013", "-").replace("\u2014", "-"))
        s = re.sub(r"\s+", " ", s).strip().lower()
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


def related_items(item, items, limit=4):
    """Same part type that shares at least one vehicle. Category-only is not a match."""
    typ = item_type_key(item)
    vehs = vehicle_keys(item)
    if not typ or not vehs:
        return []
    scored = []
    for other in items:
        if other.get("id") == item.get("id"):
            continue
        if item_type_key(other) != typ:
            continue
        shared = vehs & vehicle_keys(other)
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


def related_card_note(item):
    typ = (item.get("ebay_type") or "").strip().lower()
    name = str(item.get("name") or "")
    bits = []
    temp = re.search(r"\b(1[5-9]\d|20[05])\b", name)
    if temp and "thermostat" in typ:
        bits.append(f"{temp.group(1)} F")
    vehs = item_vehicles(item)
    if vehs:
        bits.append(vehs[0])
    return " - ".join(bits[:2])


def related_card_html(other, esc, esc_t):
    iid = other.get("id") or ""
    src = related_thumb(other)
    title = related_card_title(other)
    note = related_card_note(other)
    price = money(other.get("price"))
    note_html = f'<p class="pdp-rel-note">{esc_t(note)}</p>' if note else ""
    price_html = f'<p class="pdp-rel-price">{esc_t(price)}</p>' if price else ""
    return (
        f'<a class="pdp-rel-card" href="{esc(iid)}.html">'
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


def related_html(item, items, esc, esc_t):
    also = also_stocked_items(item, items)
    also_ids = {o.get("id") for o in also}
    related = [o for o in related_items(item, items) if o.get("id") not in also_ids]
    typ = (item.get("ebay_type") or "").strip()
    if not also and not related and not typ:
        return ""
    blocks = []
    if also:
        cards = "".join(related_card_html(o, esc, esc_t) for o in also)
        blocks.append(
            '<div class="pdp-related-block">'
            '<p class="pdp-related-h">Same part number</p>'
            f'<div class="pdp-related-grid">{cards}</div></div>'
        )
    if related:
        cards = "".join(related_card_html(o, esc, esc_t) for o in related)
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
    r"Mack|Wagner|Econoride|WIX|Standard(?:\s+Motor\s+Products)?|Moog|Beck/Arnley|"
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


def offer_shipping_details(pickup=False):
    """GSC Merchant listings require shippingDetails on every Offer.

    Ship-to-US: free UPS Ground. Pickup-only: $0 local PA, not a missing field.
    """
    if pickup:
        return {
            "@type": "OfferShippingDetails",
            "shippingRate": {
                "@type": "MonetaryAmount",
                "value": "0",
                "currency": "USD",
            },
            "shippingDestination": {
                "@type": "DefinedRegion",
                "addressCountry": "US",
                "addressRegion": "PA",
            },
            "deliveryTime": {
                "@type": "ShippingDeliveryTime",
                "handlingTime": {
                    "@type": "QuantitativeValue",
                    "minValue": 0,
                    "maxValue": 1,
                    "unitCode": "DAY",
                },
                "transitTime": {
                    "@type": "QuantitativeValue",
                    "minValue": 0,
                    "maxValue": 1,
                    "unitCode": "DAY",
                },
            },
        }
    return {
        "@type": "OfferShippingDetails",
        "shippingRate": {
            "@type": "MonetaryAmount",
            "value": "0",
            "currency": "USD",
        },
        "shippingDestination": {
            "@type": "DefinedRegion",
            "addressCountry": "US",
        },
        "deliveryTime": {
            "@type": "ShippingDeliveryTime",
            "handlingTime": {
                "@type": "QuantitativeValue",
                "minValue": 1,
                "maxValue": 3,
                "unitCode": "DAY",
            },
            "transitTime": {
                "@type": "QuantitativeValue",
                "minValue": 2,
                "maxValue": 7,
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


def safe_image(u):
    s = str(u or "").strip()
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
    items = cat["items"]
    out_dir = HUB / "p"
    out_dir.mkdir(exist_ok=True)

    written = []
    for item in items:
        iid = safe_item_id(item.get("id"))
        name = item.get("name") or "Product"
        price_n = item.get("price")
        price = money(price_n)
        catl = dept_label(item)
        desc_kind = item_ebay_tree(item).get("sub") or cat_label(item.get("category"))
        img = safe_image(item.get("image")) or f"{BASE}/assets/og-share.jpg"
        gallery_raw = [safe_image(u) for u in (item.get("images") or [])]
        gallery = [u for u in gallery_raw if u and u != img]
        video = safe_video(item.get("video"))
        checkout = safe_checkout(item.get("url"))
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
        canonical = f"{BASE}/p/{iid}.html"
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "@id": f"{canonical}#product",
            "name": name,
            "description": desc,
            "image": [img, *gallery] if gallery else img,
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
                "shippingDetails": offer_shipping_details(pickup=pickup),
            },
        }
        if pickup:
            schema["offers"]["availableDeliveryMethod"] = "https://schema.org/OnSitePickup"
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

        def esc(s):
            return html.escape(str(s or ""), quote=True)

        def esc_t(s):
            return html.escape(str(s or ""))

        if checkout:
            nav_cta = f'<a class="nav-cta" href="{esc(checkout)}" target="_blank" rel="noopener noreferrer">Buy now</a>'
            lab = "Checkout - for parts · no returns" if no_returns else "Buy · secure checkout"
            cta = f'<a class="btn btn-primary" href="{esc(checkout)}" target="_blank" rel="noopener noreferrer">{esc_t(lab)}</a>'
        else:
            nav_cta = '<a class="nav-cta is-disabled" href="../store.html">Buy now</a>'
            cta = '<span class="btn btn-primary is-disabled" aria-disabled="true">Not available for purchase</span>'
        if custom_warn:
            warn = f'<p class="pdp-warn">{esc_t(custom_warn)}</p>'
        elif is_core(item.get("category")):
            warn = '<p class="pdp-warn">FOR PARTS OR REBUILD · UNTESTED · NO RETURNS</p>'
        else:
            warn = ""
        fitment = pdp_fitment_html(item, esc_t)
        related = related_html(item, items, esc, esc_t)
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
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://items-images-production.s3.us-west-2.amazonaws.com https://*.squareup.com https://*.squarecdn.com; media-src 'self'; font-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; object-src 'none'; frame-src 'none';" />
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
  <link rel="stylesheet" href="../styles.css?v=50686aadc5" integrity="sha384-oTiTp/J0UVbInQsSQaMgHTapsTs8Sbgg/4sip7WfoK7UZZsXGQnLNlDBUYW3oHWX" />
  <script type="application/ld+json">{schema_json}</script>
  <script src="../pdp-gallery.js?v=366cbe22c5" integrity="sha384-g6VHBI6bjnClm1Q9Y5yN2XzKSt1dwoJXKdlaE9hoCUQHtJmNjTd1MYdwW6h8BqUj" defer></script>
  <script src="../main.js?v=e49d70008a" integrity="sha384-QjfesZFAOsxwfD3NfGGRcyMWdv+cJj23cZveTesOK/kGx1yvV7Zw1Om5jWDya5ce" defer></script>
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
        <a href="../terms.html">Terms</a>
        <a href="../videos.html">Music</a>
        <a class="nav-port" href="https://www.youtube.com/@BuccaneerSalvage" target="_blank" rel="noopener noreferrer"><img class="nav-port-icon" loading="lazy" decoding="async" src="../assets/nav/youtube-pirate-48.webp" width="22" height="22" alt="" />YouTube</a>
        <a class="nav-port" href="https://x.com/jollyroger1480" target="_blank" rel="noopener noreferrer"><img class="nav-port-icon" loading="lazy" decoding="async" src="../assets/nav/x-pirate-48.webp" width="22" height="22" alt="" />X</a>
        <a class="nav-port" href="https://www.ebay.com/str/buccaneersalvage" target="_blank" rel="noopener noreferrer"><img class="nav-port-icon" loading="lazy" decoding="async" src="../assets/nav/ebay-pirate-48.webp" width="22" height="22" alt="" />eBay</a>
        <a href="/ukiri/" class="nav-warn">Ukiri</a>
      </nav>
      {nav_cta}
      <button class="nav-toggle" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="drawer" id="navToggle">
        <span></span>
      </button>
    </div>
    <div class="nav-drawer" id="drawer" hidden>
      <a href="../index.html">Home</a>
      <a href="../store.html">Store catalog</a>
      <a href="../terms.html">Terms &amp; returns</a>
      <a href="../videos.html">Music</a>
      <a class="nav-port" href="https://www.youtube.com/@BuccaneerSalvage" target="_blank" rel="noopener noreferrer"><img class="nav-port-icon" loading="lazy" decoding="async" src="../assets/nav/youtube-pirate-48.webp" width="22" height="22" alt="" />YouTube</a>
      <a class="nav-port" href="https://x.com/jollyroger1480" target="_blank" rel="noopener noreferrer"><img class="nav-port-icon" loading="lazy" decoding="async" src="../assets/nav/x-pirate-48.webp" width="22" height="22" alt="" />X</a>
      <a class="nav-port" href="https://www.ebay.com/str/buccaneersalvage" target="_blank" rel="noopener noreferrer"><img class="nav-port-icon" loading="lazy" decoding="async" src="../assets/nav/ebay-pirate-48.webp" width="22" height="22" alt="" />eBay store</a>
      <a href="/ukiri/">Ukiri</a>
    </div>
  </header>
  <main id="main">
    <section class="pdp-hero">
      <div class="shell pdp-hero-inner">
        <nav class="pdp-breadcrumb" aria-label="Breadcrumb">
          <a href="../store.html">Store</a>
          <span aria-hidden="true">/</span>
          <span>{esc_t(name)}</span>
        </nav>
      </div>
    </section>
    <section class="pdp-content">
      <div class="shell pdp-layout">
        <div class="pdp-media"><div class="pdp-stage">{img_tag}{video_el}</div>{gallery_tag}</div>
        <div class="pdp-info">
          <h1 class="pdp-title">{esc_t(name)}</h1>
          <p class="pdp-category">{esc_t(catl)}</p>
          <p class="pdp-price">{esc_t(price or "Contact for price")}</p>
          {warn}
          {fitment}
          {related}
          <div class="pdp-cta-group">
            {cta}
            <a href="../store.html" class="btn btn-secondary">Back to store</a>
          </div>
          <div class="pdp-meta">
            <p><strong>Secure checkout:</strong> Card processing off-site</p>
            <p><strong>Ships from:</strong> {esc_t(ship_from)}</p>
            <p><strong>Local pickup:</strong> By appointment</p>
            <p><strong>Returns:</strong> {esc_t("Sold as-is, no returns." if no_returns else "7 days on most unused parts. Buyer remorse: 15% restocking. Cores, opened, and used items: no returns.")} <a href="../terms.html#{'no-return' if no_returns else 'returns'}">Store terms</a>.</p>
          </div>
        </div>
      </div>
    </section>
  </main>
  <footer role="contentinfo" class="footer">
    <div class="shell footer-bottom">
      <span>© <span id="y">2026</span> Rustjack · BuccaneerSalvage Store</span>
      <span><a href="../terms.html">Terms &amp; returns</a> · ships from Carbondale, PA</span>
    </div>
  </footer>
</body>
</html>
"""
        dest = (out_dir / f"{iid}.html").resolve()
        if dest.parent != out_dir.resolve():
            raise SystemExit(f"ERROR: PDP path escaped p/: {dest}")
        dest.write_text(page, encoding="utf-8")
        written.append(iid)

    keep = set(written) | {"index"}
    for stale in out_dir.glob("*.html"):
        if stale.stem not in keep:
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
    for iid in written:
        store_urls.append(url_entry(f"{BASE}/p/{iid}.html"))
    (HUB / "sitemap-store.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(store_urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    # Legacy sitemap.xml used to be a second urlset (and still gets submitted
    # in old GSC properties). Keep it as a sitemapindex pointing at the live
    # split sitemaps so it is not dead weight and cannot drift from robots.txt.
    (HUB / "sitemap.xml").write_text(
        (HUB / "sitemap-index.xml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    print(f"OK {len(written)} static PDPs → {out_dir}")


if __name__ == "__main__":
    main()
