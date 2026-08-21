# BuccaneerSalvage Hub — Full Architecture Review
**Date:** 2026-08-08  
**Live:** https://buccaneersalvage.github.io/  
**Source:** `~/sites/buccaneersalvage-hub`  
**Brains:** free MoA `bucc` (gemini-flash-lite + freellm + gemini-2.5-flash-lite → gemini-flash agg) · freellm solo · Claude synthesis · Grok local evidence  
**mega-free via hermes chat:** failed (tool loop / max-turns); **bucc via `aggregate_moa_context`:** succeeded  
**Scope:** SEO · mobile · perf · schema · security · commerce UX · dead assets · multi-identity  

---

## Executive scores (/10)

| Area | Score | Notes |
|------|------:|-------|
| SEO plumbing | **7** | Titles/canonicals/OG/JSON-LD/robots/multi-sitemap/NAP solid; undercut by store title lag + stale sitemap lastmod |
| Mobile | **6.5** | Viewport, 35 breakpoints, skip-link, focus-visible, reduced-motion; **no srcset**; videos.css gaps |
| Performance | **5.5** | Lean HTML; web-sized heroes exist; no WebP/srcset; unused repo assets ~3.5MB (not page weight); videos.html heavy JSON-LD |
| Security | **4.5** | Meta CSP + nosniff OK; **_headers dead on GH Pages**; only HSTS at HTTP layer |
| Commerce UX | **7** | Store primary → `p/{id}.html` static PDPs → square.link; eBay secondary; footer ports redesigned mid-review |

**Overall business hub:** ~**6.5/10** — beautiful flag + real NAP + own store path; discovery/perf polish still open.

---

## False positives (do **not** fix as stated)

| Claim | Reality |
|-------|---------|
| Store eBay banner `loading=lazy` is LCP bug | Banner is **third section** (after hero + trust). Lazy is correct. Claude + local verify. MoA/freellm over-flagged. |
| item.html missing `<title>` | False scanner miss — has `<title id="pageTitle">`. JS fills for dynamic shell. |
| item.html empty schema kills product SEO | Cards link to **`p/{id}.html`** (92 in sitemap-store). item.html is secondary shell. Soften defaults still P1. |
| 14MB assets = slow pages | Unreferenced files are **never fetched**. Repo/deploy bloat only (P2 hygiene). |
| Server CSP covers clickjacking via `_headers` | **_headers not applied by GitHub Pages** (file says so). Meta CSP cannot set `frame-ancestors`. |

---

## Ranked findings

### P0 — fix next (high ROI / correctness)

| # | Issue | Evidence | Fix |
|---|--------|----------|-----|
| 1 | **store title/OG still “Truck Parts”** while body/desc = auto parts + vintage collectibles | `store.html` title + og:title + twitter | Align to e.g. `BuccaneerSalvage Store — Auto Parts & Vintage Treasures \| Carbondale PA` |
| 2 | **Sitemap lastmod frozen 2026-08-04** while pages edited 2026-08-08 | `sitemap-hub.xml`, store/media | Hook lastmod into `deploy-buccaneer-pages` (ISO date) |
| 3 | **item.html bot defaults still “Truck parts”** (title/meta/OG stubs) | `item.html` static head | Neutral defaults: “Product \| BuccaneerSalvage Store”; keep `p/*` as SoT for SERP |

*(Security headers: real gap but **infra** — not a 5-minute HTML fix. Tracked as P1-infra below.)*

### P1 — high impact

| # | Issue | Fix |
|---|--------|-----|
| 4 | **No srcset / WebP sitewide** | Generate webp for heroes/crests/banners; `<img srcset>` or `<picture>` on LCP-ish assets |
| 5 | **videos.html** short meta (~74 chars) + huge inline ItemList JSON-LD (~58KB page) | Lengthen meta to ~150 chars; consider externalizing or trimming ItemList |
| 6 | **videos.css** missing `-webkit-text-size-adjust` | Add `text-size-adjust: 100%` |
| 7 | **HTTP security headers** only HSTS live | Cloudflare-in-front **or** document that meta CSP is the GH Pages ceiling; don’t pretend `_headers` works |
| 8 | **~3.5MB unreferenced assets** + `*.bak` under `assets/` | Move masters out of deploy tree; delete or exclude `square-catalog.json.bak*` from public host |

### P2 — polish / hygiene

| # | Issue | Fix |
|---|--------|-----|
| 9 | Meta CSP `unsafe-inline` on index | Optional: externalize any remaining inline if tightening later |
| 10 | root `logo.png` 518KB possibly unused | Confirm refs; drop from deploy if dead |
| 11 | GBP: no public street address | Business choice; verification needs **real** private mailing — don’t invent |
| 12 | square.html redirect retained | Keep for old links unless analytics = zero |

### P3 — low / intentional

| # | Note |
|---|------|
| Multi-identity `og:site_name` / WebSite `@id` (hub vs store) | **By design** on github.io — not a bug |
| square.link checkout (not square.site) | **Intentional** after Online CMS scrub |
| Ukiri multi-sitemap | Public warning site — keep indexed |

---

## Architecture (8-check lens)

| Check | Status |
|-------|--------|
| 1 Separation | Hub / store / music / ukiri identities OK |
| 2 Sequence | catalog → store cards → **p/*.html** → square.link OK |
| 3 Instantiation | item.js fills title/schema; bots should hit static `p/` |
| 4 Data model | Dark Fleet kinds music\|comedy\|short (recent fix) |
| 5 Syntax | Static HTML — N/A |
| 6 Dead code/assets | Large unused masters + bak JSON public |
| 7 Logging | N/A |
| 8 Cross-component | **Sitemap lastmod not wired to deploy**; store title lagged body rewrite |

**Confidence (synthesis): 8/10** — local + live curl + source verified; no full Lighthouse mobile run this pass.

---

## Top 5 fix order (next session)

1. **store.html title + OG + twitter** (2-minute SERP fix)  
2. **deploy hook: sitemap lastmod = today**  
3. **item.html neutral static defaults** (not Truck parts)  
4. **Prune unused assets + .bak from public tree**  
5. **srcset/webp for crest + hero + store key images** (real mobile perf)

Optional infra: Cloudflare free in front of GH Pages for real security headers.

---

## Done mid-review (2026-08-08)

- Footer **Linktree dump → “Ports of call”** chip grid (Store / eBay / Music / YT / X / Ukiri one-chip) + contact icons — live `13eeee2` / styles `godmode5`.

---

## Artifact paths

| File | Role |
|------|------|
| `/tmp/hub-arch-review-20260808/EVIDENCE.md` | Local evidence pack |
| `/tmp/hub-arch-review-20260808/claude-review.out` | Claude full synthesis |
| `/tmp/hub-arch-review-20260808/moa-bucc.out` | Free MoA bucc aggregate |
| `/tmp/hub-arch-review-20260808/freellm.out` | Free freellm solo |
| `/tmp/hub-arch-review-20260808/unused-assets.txt` | Unused asset list |
| `/tmp/hub-arch-review-20260808/REPORT.md` | This report |

**No code fixes applied for P0–P2 SEO/perf except the footer redesign** (user pivot). Say the word to implement the Top 5.

---

## Fixes applied 2026-08-08 (session)

| Item | Status |
|------|--------|
| store title/OG/twitter generalized | done |
| item.html static defaults no Truck parts | done |
| sitemap lastmod → 2026-08-08 | done |
| deploy-buccaneer-pages lastmod stamp + bak/_archive excludes | done |
| videos meta lengthened | done |
| videos.css text-size-adjust | done |
| unused assets → `_archive/unused-assets-20260808/` (~3.5MB+ masters) | done |
| WebP + `<picture>` for crest/port/hero/store banner/og-scene | done |
| `_headers` note clarified (GH Pages no-op) | done |
| Footer ports redesign | done earlier |
| Real HTTP CSP/frame-ancestors | **blocked** on github.io without Cloudflare |
| Public street address / GBP | **business** — not inventable |
