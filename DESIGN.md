# BuccaneerSalvage — DESIGN.md (source of truth)

> **Do not redesign the store/hub from scratch.**  
> Live system is already cinematic maritime luxury.  
> Any new artifact must **extend** this contract, not invent Bebas/Inter/purple SaaS.

## Product identity

| Surface | URL | Role |
|---------|-----|------|
| **Hub** | https://buccaneersalvage.github.io/ | Flagship: music, lanes, ports, brand thesis |
| **Store (primary)** | https://buccaneersalvage.github.io/store.html | Parts catalog + checkout (own store) |
| **eBay (secondary)** | https://www.ebay.com/str/buccaneersalvage | Marketplace listings |
| **YouTube** | https://www.youtube.com/@BuccaneerSalvage | Dark AI music / Rustjack |

**Captain:** Cap'n Jules the Rustjack · Carbondale PA **18407**  
**Voice:** pirate salvage armada — receipts, riffs, rage; honest used-parts yard, not dropship fluff.

## Visual thesis

**Cinematic maritime luxury** — void black, brand gold foil, parchment type, glass edges, film grain.  
Not: generic AI landing, Bebas Neue posters, purple gradients, soft glassmorphism SaaS cards.

## Tokens (from `styles.css`)

### Color
- Gold: `#c5a028` · bright `#f0d078` · foil top `#fff1b8` · mid `#d4af37` · deep `#7a5a12`
- Blood: `#b91c1c` · deep `#7f1d1d` (accent / danger only)
- Surfaces: void `#050403` · ink `#0c0907` · elevated `#14100c` · smoke `#1c1612`
- Glass: `rgba(18,14,10,0.55)` · strong `rgba(12,9,7,0.78)`
- Glass edge: `rgba(240,208,120,0.18)` · hot `rgba(240,208,120,0.55)`
- Text: parchment `#f3ead8` · light `#eee4d4` · muted/faint alphas

### Type
- **Display:** `"Cormorant Garamond"` (serif luxury — never Bebas/Impact for brand UI)
- **Body:** `"Outfit"`
- **Mono:** `"IBM Plex Mono"`
- Fluid scale: `--text-xs` … `--text-hero` (see styles.css)

### Space / shape
- Max width `1180px` · gutter `clamp(1.1rem, 4vw, 2.25rem)`
- Radius: sm `10px` · `18px` · lg `28px`
- Easing: `cubic-bezier(0.22, 1, 0.36, 1)`

### Atmosphere
- Fixed grain overlay (~4.5% opacity, overlay blend)
- Gold/smoke orbs (gradient only — avoid heavy blur jank)
- Glass cards with gold edge, not flat gray boxes

## Assets (curated)

Use real hub assets under `assets/` — crest, hero atmosphere, port treasure, og-share, ship marks.  
Do not substitute stock pirate clipart.

## Hard rules for AI / Open Design

1. **Never** regenerate store.html / index.html as a “clean rewrite” without explicit order.
2. Prefer **additive** pieces: decks, ads, email, product PDFs, social cutdowns, Square banner variants, listing closer graphics — all using these tokens.
3. Match existing class language where possible (`nav-brand`, `btn-primary`, ports, glass).
4. No invented phone numbers, prices, or legal claims.
5. Mobile-first; respect CSP and local-font setup (`assets/fonts.css`).

## Good OD prompts (examples)

- “Fleet / wholesale one-pager PDF using BuccaneerSalvage DESIGN.md tokens + crest asset”
- “YouTube end-card 1920×1080 matching hub gold foil + Outfit/Cormorant”
- “eBay store banner 1600×400 consistent with `ebay-banner-wide` language”
- “3 Instagram story frames for air-spring drop — same system as store.html”

## Bad OD prompts

- “Build a landing page for BuccaneerSalvage” (competes with the live hub/store)
- “Modern SaaS redesign of the store”
- Any default brutalism / Inter / purple template

## Implementation roots

- This repo: `index.html` · `store.html` · `styles.css` · `main.js` · `videos.html`
- Live host: https://buccaneersalvage.github.io/
