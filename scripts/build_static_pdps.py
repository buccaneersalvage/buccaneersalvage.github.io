#!/usr/bin/env python3
"""Regenerate static PDP pages under p/{id}.html for no-JS crawler SEO."""
from __future__ import annotations

import html
import json
import re
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


def offer_return_policy(category):
    """Cores: no returns. Other stock: 7-day unused mail return, buyer pays (hub store terms)."""
    if is_core(category):
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
        checkout = safe_checkout(item.get("url"))
        title = f"{name} | BuccaneerSalvage Store"
        desc = f"{name} — {catl}. {price}. Browse and secure checkout at BuccaneerSalvage Store."
        canonical = f"{BASE}/p/{iid}.html"
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "@id": f"{canonical}#product",
            "name": name,
            "description": desc,
            "image": img,
            "sku": iid,
            "brand": {"@type": "Brand", "name": "BuccaneerSalvage Store"},
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
                "hasMerchantReturnPolicy": offer_return_policy(item.get("category")),
            },
        }
        if price_n is not None:
            schema["offers"]["price"] = str(price_n)

        def esc(s):
            return html.escape(str(s or ""), quote=True)

        def esc_t(s):
            return html.escape(str(s or ""))

        if checkout:
            nav_cta = f'<a class="nav-cta" href="{esc(checkout)}" target="_blank" rel="noopener noreferrer">Buy now</a>'
            lab = "Checkout — for parts · no returns" if is_core(item.get("category")) else "Buy · secure checkout"
            cta = f'<a class="btn btn-primary" href="{esc(checkout)}" target="_blank" rel="noopener noreferrer">{esc_t(lab)}</a>'
        else:
            nav_cta = '<a class="nav-cta is-disabled" href="../store.html">Buy now</a>'
            cta = '<span class="btn btn-primary is-disabled" aria-disabled="true">Not available for purchase</span>'
        warn = (
            '<p class="pdp-warn">FOR PARTS OR REBUILD · UNTESTED · NO RETURNS</p>'
            if is_core(item.get("category"))
            else ""
        )
        img_tag = f'<img class="pdp-image" src="{esc(img)}" alt="{esc(name)}" width="600" height="600" />'
        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{esc_t(title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
  <meta name="theme-color" content="#0c0a08" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; base-uri 'self'; object-src 'none';" />
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
  <script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
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
        <div class="pdp-media"><div class="pdp-image-wrapper">{img_tag}</div></div>
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
            <p><strong>Returns:</strong> 7 days on most unused parts. Buyer remorse: 15% restocking. Cores, opened, and used items: no returns. <a href="../terms.html#returns">Store terms</a> (not eBay rules).</p>
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

    # sitemaps
    def url_entry(loc, pri="0.7"):
        return f"""  <url>
    <loc>{loc}</loc>
    <lastmod>2026-08-04</lastmod>
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
