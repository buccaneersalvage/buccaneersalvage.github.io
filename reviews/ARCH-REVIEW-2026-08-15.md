# BuccaneerSalvage Hub — Architecture Review (2026-08-15)

Free-cloud 8-check after leftover fixes. **Local tree only — not deployed.**

Full merge + rejected leaf claims: `~/grok-work/reports/hub-arch-review-20260815/00-EXECUTIVE-SUMMARY.md`

**Brains:** Mistral direct `mistral-large-latest` + `ministral-14b-latest` + `codestral-latest` (user Mistral key, not NVIDIA NIM); Gemini Flash (truncated, discarded).

**Overall: 7.5/10** (confidence 8/10).

| # | Check | Status |
|---|--------|--------|
| 1 SoC | OK / gap — videos fork OK; **PDP lacks hub drawer** |
| 2 Sequence | OK — catalog 198 == p/ 198 == sitemap-store 199 (store+PDPs) |
| 3 Instantiation | OK — item.js gone; store cards → `p/{id}.html` |
| 4 Data model | OK / small — hardcoded PDP clip `uploadDate`; pdp_desc lowercase leftover |
| 5 Syntax | OK |
| 6 Dead code | OK / docs — SITE_GRAPH still mentions `/item.html` |
| 7 Logging | thin, not blocking |
| 8 Cross-component | **PDP mobile nav missing** vs index/store/terms |

**P0 leftover from this review (if asked):** add `#navToggle` / `#drawer` + `../main.js` to PDP builder and regen.

Do not treat Dark Fleet’s 55 videos as Square catalog videos. Do not invent product essays. Do not deploy unless asked.
