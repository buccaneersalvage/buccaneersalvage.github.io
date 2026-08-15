#!/usr/bin/env python3
"""Regenerate static PDP pages under p/{id}.html for no-JS crawler SEO."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

HUB = Path(__file__).resolve().parents[1]
BASE = "https://buccaneersalvage.github.io"


def money(n):
    try:
        return f"${float(n):,.2f}"
    except Exception:
        return ""


def cat_label(c):
    return {
        "air-spring": "Air spring",
        "brake": "Brake hardware",
        "filters": "Filter",
        "ignition": "Ignition",
        "driveline": "Driveline",
        "turbo": "Turbo core",
        "pump": "Pump core",
        "other": "Parts",
    }.get(c, "Parts")


def is_core(c):
    return c in ("turbo", "pump")


_BRAND_RE = re.compile(
    r"^(?:OEM\s+)?(Carlson|Automann|Goodyear|Continental|ContiTech|Firestone|Holset|"
    r"Mack|Wagner|Econoride|WIX|Standard(?:\s+Motor\s+Products)?|Moog|Beck/Arnley|"
    r"Cloyes|Pace\s?Setter|AP\s+Exhaust)\b",
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


def offer_shipping_details():
    """US Ground from Carbondale PA — free UPS Ground where available (Square store SEO)."""
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


def safe_checkout(u):
    s = str(u or "").strip()
    if not s.startswith("http"):
        return ""
    try:
        host = (urlparse(s).hostname or "").lower()
        if host == "square.link" or host.endswith(".square.link") or host == "checkout.square.site":
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
    if not s.startswith("http"):
        return ""
    try:
        host = (urlparse(s).hostname or "").lower()
        if (
            host == "buccaneersalvage.github.io"
            or host.endswith(".squareup.com")
            or host.endswith(".squarecdn.com")
            or host.endswith(".amazonaws.com")
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

    TEMPLATE = (HUB / "scripts/pdp_static_template.html").read_text() if False else None
    # inline template kept in generator for single-file regen
    from textwrap import dedent

    # reuse generation via import of prior logic — call subprocess self
    # simpler: exec the same block as session generator
    written = []
    for item in items:
        iid = item["id"]
        name = item.get("name") or "Product"
        price_n = item.get("price")
        price = money(price_n)
        catl = cat_label(item.get("category"))
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
        no_returns = is_core(item.get("category")) or bool(custom_warn)
        # Google truncates SERP titles around ~60 chars. Catalog product names
        # (sourced from eBay listing titles) commonly run 60-100+ chars on
        # their own — appending " | BuccaneerSalvage Store" (24 chars) to an
        # already-long name only pushed the truncation point further into the
        # name itself while burying the brand suffix nobody sees anyway.
        # Drop the suffix once it would put the title over budget; the store
        # name still appears via og:site_name / structured data either way.
        _BRAND_SUFFIX = " | BuccaneerSalvage Store"
        title = name if len(name) + len(_BRAND_SUFFIX) > 60 else f"{name}{_BRAND_SUFFIX}"
        desc = f"{name} — {catl}. {price}. Browse and secure checkout at BuccaneerSalvage Store."
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
                "shippingDetails": offer_shipping_details(),
                "hasMerchantReturnPolicy": offer_return_policy(item.get("category"), force_no_returns=no_returns),
            },
        }
        if price_n is not None:
            schema["offers"]["price"] = str(price_n)
        if video:
            schema["video"] = {
                "@type": "VideoObject",
                "name": f"{name} — test run",
                "description": f"Test-run clip of {name}.",
                "thumbnailUrl": [img],
                "uploadDate": "2026-08-14",
                "contentUrl": f"{BASE}/{video}",
            }

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
            lab = "Checkout — for parts · no returns" if no_returns else "Buy · secure checkout"
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
            f'data-src="{esc(img)}" aria-label="{esc_t(name)} — main photo">'
            f'<img class="pdp-thumb" src="{esc(img)}" alt="" width="100" height="100" loading="lazy" /></button>'
        )
        thumbs += "".join(
            f'<button type="button" class="pdp-thumb-btn" data-type="image" data-src="{esc(u)}" '
            f'aria-label="{esc_t(name)} — additional photo">'
            f'<img class="pdp-thumb" src="{esc(u)}" alt="" width="100" height="100" loading="lazy" /></button>'
            for u in gallery
        )
        if video:
            thumbs += (
                f'<button type="button" class="pdp-thumb-btn pdp-thumb-video" data-type="video" '
                f'aria-label="{esc_t(name)} — test-run video">'
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
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; object-src 'none';" />
  <meta http-equiv="X-Content-Type-Options" content="nosniff" />
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
  <link rel="stylesheet" href="../assets/fonts.css" />
  <link rel="stylesheet" href="../styles.css?v=godmode7" />
  <script type="application/ld+json">{schema_json}</script>
  <script src="../pdp-gallery.js" defer></script>
</head>
<body class="page-item">
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav is-solid" role="banner">
    <div class="nav-inner">
      <a class="nav-brand" href="../store.html" aria-label="BuccaneerSalvage Store home">
        <img class="nav-mark" src="../assets/crest-rustjack-web.jpg" width="38" height="38" alt="BuccaneerSalvage Jolly Roger logo" />
        <span class="nav-word">BuccaneerSalvage Store</span>
      </a>
      <nav class="nav-links" aria-label="Primary">
        <a href="../index.html">Home</a>
        <a href="../store.html">Store</a>
        <a href="../terms.html">Terms</a>
        <a href="../videos.html">Music library</a>
        <a href="/ukiri/" class="nav-warn">Ukiri Fraud Report</a>
      </nav>
      {nav_cta}
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
          <div class="pdp-cta-group">
            {cta}
            <a href="../store.html" class="btn btn-secondary">Back to store</a>
          </div>
          <div class="pdp-meta">
            <p><strong>Secure checkout:</strong> Card processing off-site</p>
            <p><strong>Ships from:</strong> Carbondale, PA 18407</p>
            <p><strong>Local pickup:</strong> By appointment</p>
            <p><strong>Returns:</strong> {esc_t("Sold as-is, no returns." if no_returns else "7 days on most unused parts. Buyer remorse: 15% restocking. Cores, opened, and used items: no returns.")} <a href="../terms.html#{'no-return' if no_returns else 'returns'}">Store terms</a>.</p>
          </div>
        </div>
      </div>
    </section>
  </main>
  <footer role="contentinfo" class="footer">
    <div class="shell footer-bottom">
      <span>© 2026 Rustjack · BuccaneerSalvage Store</span>
      <span><a href="../terms.html">Terms &amp; returns</a> · ships from Carbondale, PA</span>
    </div>
  </footer>
</body>
</html>
"""
        (out_dir / f"{iid}.html").write_text(page, encoding="utf-8")
        written.append(iid)

    (out_dir / "index.html").write_text(
        f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8" />
<meta http-equiv="refresh" content="0;url=../store.html" />
<link rel="canonical" href="{BASE}/store.html" />
<meta name="robots" content="noindex" />
<title>Redirecting to store…</title>
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

    # patch sitemap.xml + sitemap.txt
    for fname in ("sitemap.xml", "sitemap.txt"):
        path = HUB / fname
        text = path.read_text(encoding="utf-8")
        text2 = re.sub(
            r"https://buccaneersalvage\.github\.io/item\.html\?id=([A-Z0-9]+)",
            r"https://buccaneersalvage.github.io/p/\1.html",
            text,
        )
        # also ensure p/ urls exist if only old format was used
        path.write_text(text2, encoding="utf-8")

    print(f"OK {len(written)} static PDPs → {out_dir}")


if __name__ == "__main__":
    main()
