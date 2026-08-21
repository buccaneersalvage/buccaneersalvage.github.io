# SCRAP PAGE — Kimi build report (2026-08-18)

Built `scrap.html`: god-mode local SEO page for Carbondale / NEPA scrap metal, junk removal, and e-waste. Same cinematic maritime luxury system as the hub (void black, gold foil, Cormorant + Outfit, glass cards, grain). Additive only — no redesign of index/store. Not deployed.

## Files changed

| File | Change |
|------|--------|
| `scrap.html` | **New.** Full head (title/desc/keywords/canonical/robots/theme-color/CSP with `img-src 'self'`), OG + Twitter cards for `https://buccaneersalvage.github.io/scrap.html` (og:image = `assets/scrap/og-scrap.jpg` 1200×630), JSON-LD `@graph`: WebPage + BreadcrumbList (Home → Scrap, Junk & E-Waste) + Service with OfferCatalog (free scrap / paid junk / paid e-waste / cheaper drop-off). Reuses hub nav, hero, bento ports, about, footer, `main.js`. |
| `styles.css` | Appended scrap-only block: `.scrap-hero .hero-bg`, `.about-visual--scrap`, `.about-visual--scrap2`, `.scrap-gallery` / `.scrap-shot` (glass cards, 1→2→3 col). No second design system. |
| `index.html` | Drawer "Scrap & e-waste" → `scrap.html`; hero ghost CTA → `scrap.html`; Local port card → `scrap.html` (copy now says junk+e-waste paid); `#local` teaser kept, now points to full page with ghost CTA; footer contact link → `scrap.html`; ItemList schema position 3 URL → `scrap.html`. |
| `store.html` | Footer "Scrap & e-waste (local)" link `index.html#local` → `scrap.html`. |
| `sitemap-hub.xml` | Added `scrap.html` (lastmod 2026-08-18, weekly, 0.85). |
| `sitemap.txt` | Added `scrap.html` URL. |
| `assets/scrap/` | **New dir.** 10 photos × (webp + jpg, ≤1600px, stripped) + `og-scrap.jpg` (1200×630). ~11MB total. |
| `previews/scrap-*.png` | Verification screenshots (desktop, mobile, drawer, sections, hub teaser). |
| `scripts/stamp_sri.py` run | Re-stamped `styles.css?v=11ec6c73db` + SRI across 270 HTML files (styles.css changed). |

`videos.html` / `terms.html`: no `#local` / "Scrap & e-waste" links existed — untouched (minimal-change rule).

## Service facts (as given — nothing invented)

- Scrap metal haul: **free**, local, by appointment.
- Junk removal: **paid** (quoted per job).
- E-waste / electronics recycling: **paid**; **drop-off at the house is cheaper than pickup** (stated plainly, no dollar amounts).
- Local only · by appointment · not a walk-in junkyard.
- NAP: (570) 468-2901 · jollyroger1480@gmail.com · Carbondale PA 18407 · Mon–Sat 9a–5p by appointment.
- Captain: Cap'n Jules the Rustjack. Store/eBay stay the online-parts lane.

## Photo sources (Plex originals — COPIED, never moved/deleted)

All visually inspected; skipped family/kids, legal/PUC docs, screenshots, memes, MV/AI stills, plate closeups, house interiors.

| Asset | Original Plex path |
|-------|--------------------|
| `yard-truck-flatbed` (.jpg/.webp) + hero bg | `/mnt/external_hdd/Pictures/2025/2025-04/2025-04-03 - Madison Township Pennsylvania/IMG_20250403_165747464.jpg` |
| `yard-truck-trailer` + about visual | `/mnt/external_hdd/Pictures/2025/2025-04/2025-04-03 - Madison Township Pennsylvania/IMG_20250403_165754930.jpg` |
| `yard-truck-loaded` + hero card + `og-scrap.jpg` | `/mnt/external_hdd/Pictures/2025/2025-04/2025-04-20 - Madison Township Pennsylvania/IMG_20250420_155050287.jpg` |
| `scrap-pile-chains` | `/mnt/external_hdd/Pictures/2025/2025-04/2025-04-20 - Madison Township Pennsylvania/IMG_20250420_154811270.jpg` |
| `yard-trailer-frame` | `/mnt/external_hdd/Pictures/2025/2025-04/2025-04-20 - Madison Township Pennsylvania/IMG_20250420_155045350.jpg` |
| `scrap-trailer-flatbed` + about visual 2 | `/mnt/external_hdd/Pictures/2025/2025-07/2025-07-01 - Carbondale Pennsylvania/IMG_20250701_135504647.jpg` |
| `engine-pull-garage` | `/mnt/external_hdd/Pictures/2025/2025-05/2025-05-22 - Ransom Township Pennsylvania/IMG_20250522_132711416.jpg` |
| `scrap-engine-pile` | `/mnt/external_hdd/Pictures/2026/2026-04/2026-04-08 - Dallas Pennsylvania/IMG_20260408_131349738.jpg` |
| `rusty-hardware-chain` | `/mnt/external_hdd/Pictures/2026/2026-04/2026-04-08 - Dallas Pennsylvania/IMG_20260408_131407881.jpg` |
| `vintage-car-rust` | `/mnt/external_hdd/Pictures/2026/2026-04/2026-04-08 - Dallas Pennsylvania/IMG_20260408_131514047.jpg` |

Skipped on review: purple tow-truck shot (visible camper plate), July trailer closeups w/ house siding, all monitoring/legal docs, selfies, kitten/family shots.

## Verification done

- `python3` HTML parse of `scrap.html`: OK · JSON-LD parses, `@graph` = WebPage/BreadcrumbList/Service.
- All `<img>`/`<source>` refs + 6 CSS `url("assets/scrap/...")` refs exist on disk.
- `grep`: zero `#local` hrefs remain in index/store/videos/terms; 7 `scrap.html` links in index, 1 in store.
- `sitemap-hub.xml` / `sitemap-index.xml`: valid XML.
- `python3 scripts/stamp_sri.py`: styles.css `?v=11ec6c73db` + sha384 consistent across pages.
- Playwright (headless chromium, local HTTP): desktop 1440 + mobile 390 renders, drawer opens, zero console/page errors. Screenshots in `previews/scrap-*.png`.

## Not done (by design)

- No deploy (per instructions).
- No reviews, prices, certifications, "licensed/bonded", or extra phone numbers invented.
