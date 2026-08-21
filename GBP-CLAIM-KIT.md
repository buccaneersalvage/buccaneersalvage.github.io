# Google Business Profile — BuccaneerSalvage (claim kit)

Google **cannot** create a live GBP from this PC without your Google login + phone verification.  
Fill the Business Profile form with the fields below. Hub already matches this NAP after deploy.

**Create / manage:** https://business.google.com/  
**Alternate:** https://www.google.com/business/

---

## Copy-paste fields

| Field | Value |
|--------|--------|
| **Business name** | BuccaneerSalvage |
| **Category (primary)** | Used Auto Parts Store |
| **Category (additional)** | Auto Parts Store |
| **Category (additional)** | Scrap Metal Dealer |
| **Category (additional)** | Junk Dealer *or* Antique Store (for industrial / collectible relics) |
| **Category (additional)** | Electronics Recycler *(only if you really take e-waste for a fee)* |

**Category strategy (2026-08-08):** Lead with **auto parts / cores** so truck buyers find you. Scrap + relics are secondary categories + description services — not primary “antique shop” (that attracts the wrong Maps queries). Cores stay under used auto parts.
| **Phone** | (570) 468-2901 |
| **Website** | https://buccaneersalvage.github.io/ |
| **Email** (if asked) | jollyroger1480@gmail.com |

### Address mode (important)

You do **not** have a public street on the hub yet (city + ZIP only). Prefer:

**Service-area business (SAB)**  
- Deliver / serve customers at their location  
- **Hide** street address from Google Maps if it’s a home yard  
- **Service areas:** Carbondale, PA · Scranton area / Lackawanna County · NEPA (radius you actually haul)

If you have a public commercial address you’re willing to show, use that street + Carbondale PA 18407 instead and skip SAB.

### Hours

| Day | Hours |
|-----|--------|
| Mon–Sat | 9:00 AM – 5:00 PM |
| Sun | Closed |
| Note | **By appointment only** — call or text (570) 468-2901 |

(Matches hub schema; don’t claim walk-in retail if you don’t do walk-ins.)

### Business description (750 char max — paste)

```
BuccaneerSalvage is Cap'n Jules the Rustjack in Carbondale, PA 18407. Opportunistic truck parts and salvage cores (as-is) sold online via eBay and our site store. Free local scrap metal removal by appointment. Electronic recycling / e-waste for a fee (not free). Ships US-wide; local pickup by appointment. Call or text (570) 468-2901 · jollyroger1480@gmail.com · buccaneersalvage.github.io
```

### Services to add

1. Free scrap metal pickup / haul (local)  
2. Electronic recycling / e-waste (paid)  
3. Used auto / truck parts (online + local pickup)  
4. Salvage cores (as-is / rebuild)

### Attributes (check what applies)

- Appointment required  
- On-site services (if you pick up at customer)  
- Free estimates (optional)  
- Women-led / veteran / etc. only if true  

### Photos (upload from phone)

1. Logo / crest (`assets/crest-rustjack-web.jpg` on hub)  
2. Cover / yard or packing table  
3. 3–10 product or haul photos (real stock)  
4. Optional: packing / free USPS boxes  

### Links / social

- Website: https://buccaneersalvage.github.io/  
- YouTube: https://www.youtube.com/@BuccaneerSalvage  
- eBay: https://www.ebay.com/str/buccaneersalvage  
- X: https://x.com/jollyroger1480  

### Verification

Google will usually verify by **postcard**, **phone**, or **email/video**.  
Use the same phone **(570) 468-2901** and Gmail **jollyroger1480@gmail.com**.

---

## After live

1. First post: “Free scrap metal haul + paid e-waste · Carbondale PA · call (570) 468-2901”  
2. Weekly: “In the hold this week” photo linking eBay  
3. Keep NAP identical: phone · city/ZIP · website (same as hub footer)

## Hub files updated for NAP/CTA (deploy when ready)

- `index.html` — CTAs, `#local`, schema LocalBusiness, footer  
- `store.html` / `p/{id}.html` — contact / product pages 

Deploy only when you say: `deploy-buccaneer-pages` (org Pages).
