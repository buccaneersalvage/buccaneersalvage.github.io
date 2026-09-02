# Formspree — BuccaneerSalvage hub

Uses the **existing** account form already on Ukiri support:

- Endpoint: `https://formspree.io/f/mlggwlyo`
- Config: `formspree-config.js`
- Notify: jollyroger1480@gmail.com (dashboard only — not on the public site; pages use contact.html)

## Free tier (50 submissions / month)

Formspree **free is 50 submissions/month for the whole account**, not per form. Ukiri support + hub contact + services intake **share that pool**.

That is usually fine for real yard traffic. It is **not** fine if bots hammer the form.

### If you get hammered

1. Turn on **Formshield** + **reCAPTCHA** in the Formspree dashboard for `mlggwlyo`.
2. Confirm **allowed domains** include `buccaneersalvage.github.io` (and drop random origins).
3. Honeypot is already on `/contact.html` (`_gotcha`).
4. If volume or spam still burns the 50: stop using Formspree for the public hub and switch to a Worker → email API (Resend/Mailgun/CF Email) — unlimited-ish, you control rate limits. Mailto stays a bad phone UX; don’t go back to that as primary.

### When Formspree is still the right call

- Low real contact volume (parts questions, scrap bookings, service intake).
- You want zero backend.
- You’re OK upgrading later if the yard gets noisy.

## Site touchpoints

| Surface | Behavior |
|---------|----------|
| `/contact.html` | Main contact form (AJAX → mlggwlyo) |
| Footer / nav former mailto | → `contact.html` |
| Ask widget email links | → `contact.html` |
| `/services.html` intake | POST same endpoint |
| `/ukiri/support.html` | Same endpoint (already live) |

## Deploy

After `formspree-config.js` change: `python3 scripts/stamp_sri.py`, commit, push Pages. Smoke-test `/contact.html` once (counts against the 50).

## Square → Formspree (eBay listing services only)

Square and Formspree do **not** share a backend. Formspree is only for **messages**, not payment.

| Path | After-pay landing |
|------|-------------------|
| Hub **store cart** (Worker) | `thanks.html` — pirate thank-you. **No** Formspree redirect. Optional Contact link on that page. |
| **eBay listing services** (`services.html` / `square.link`) | **Done via Square API 2026-09-02** (all 10 `services.html` square.link URLs). Re-run if links are recreated. Manual path was: Square Dashboard → Payment Link → After payment redirect → `https://buccaneersalvage.github.io/contact.html?source=square-services&topic=Listing%20services` so buyers can send photos / PNs / store URL via Formspree `mlggwlyo`. |

Contact tags Formspree `source=hub-contact-square-services`. Counts against the **50/mo** pool only when they submit the form.

Do **not** POST Square webhooks into Formspree (burns quota). Do **not** send store checkout to Contact by default.

