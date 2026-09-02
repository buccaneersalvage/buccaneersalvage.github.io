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

## Square checkout → Formspree (after pay)

Square and Formspree do **not** share a backend. Tie-in is **redirect after pay** onto Contact (Formspree `mlggwlyo`):

| Path | After-pay landing |
|------|-------------------|
| Hub **cart** (Worker payment links) | `REDIRECT_URL` → `contact.html?source=square-store&topic=Store%20order` |
| **Services** `square.link` buttons | In Square Dashboard → each Payment Link → **After payment** / redirect URL → `https://buccaneersalvage.github.io/contact.html?source=square-services&topic=Listing%20services` |

Contact prefills topic/message and tags Formspree `source` (`hub-contact-square-store` / `hub-contact-square-services`). Still counts against the **50/mo** free pool — only when the buyer actually sends the form.

Do **not** POST every Square webhook into Formspree (burns quota; no buyer message).
