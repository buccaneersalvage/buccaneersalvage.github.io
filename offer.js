// "Make an offer" on a product page. Posts {id, offer, email, note} to the
// checkout Worker, which only notifies the shop. Nothing is accepted here.
(() => {
  "use strict";

  const form = document.getElementById("pdpOfferForm");
  if (!form) return;
  const status = document.getElementById("pdpOfferStatus");
  const submit = document.getElementById("pdpOfferSubmit");
  const amount = document.getElementById("o-amount");
  const email = document.getElementById("o-email");
  const note = document.getElementById("o-note");
  const gotcha = document.getElementById("o-gotcha");
  const amountErr = document.getElementById("o-amount-err");
  const emailErr = document.getElementById("o-email-err");
  const endpoint = form.dataset.endpoint || "";
  const itemId = form.dataset.id || "";
  const max = Number(form.dataset.max);
  // Lowest offer the Worker takes (data-min from the builder, same 10% rule).
  const min = Number(form.dataset.min);
  const TIMEOUT_MS = 15000;
  const loadedAt = Date.now();
  const EMAIL_RE = /^[^\s@<>]{1,64}@[^\s@<>]{1,190}\.[A-Za-z]{2,24}$/;

  function setStatus(kind, text) {
    status.hidden = false;
    status.className = "contact-status contact-status--" + kind;
    status.textContent = text;
  }

  function fieldError(input, errEl, text) {
    if (text) {
      errEl.textContent = text;
      errEl.hidden = false;
      input.setAttribute("aria-invalid", "true");
    } else {
      errEl.textContent = "";
      errEl.hidden = true;
      input.removeAttribute("aria-invalid");
    }
  }

  function check() {
    let first = null;
    const val = Math.round(Number(amount.value) * 100) / 100;
    if (!amount.value.trim() || !Number.isFinite(val) || val <= 0) {
      fieldError(amount, amountErr, "Enter your offer in dollars, for example 25.00.");
      first = first || amount;
    } else if (Number.isFinite(max) && val > max) {
      fieldError(amount, amountErr, "An offer can be up to the list price of $" + max.toFixed(2) + ".");
      first = first || amount;
    } else if (Number.isFinite(min) && val < min) {
      fieldError(amount, amountErr, "That offer is too low for us to consider.");
      first = first || amount;
    } else {
      fieldError(amount, amountErr, "");
    }
    const em = email.value.trim();
    if (!EMAIL_RE.test(em) || em.length > 254) {
      fieldError(email, emailErr, "Enter an email address we can reply to, like name@example.com.");
      first = first || email;
    } else {
      fieldError(email, emailErr, "");
    }
    return { first, val, em };
  }

  const MESSAGES = {
    offers_closed: ["warn", "Offers are not open yet. Please use the Add to cart button or message us about this part."],
    rate_limited: ["warn", "Too many offers from this connection. Please try again in a few minutes."],
    sold_out: ["warn", "This part just sold out."],
    unknown_item: ["err", "This part is no longer listed."],
    bad_amount: ["err", "That offer is outside what we can accept for this part."],
    bad_email: ["err", "Please check your email address."],
  };

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const { first, val, em } = check();
    if (first) {
      first.focus();
      return;
    }
    // Filled honeypot or an instant submit: a bot. Show the normal thank-you.
    if ((gotcha && gotcha.value.trim()) || Date.now() - loadedAt < 1200) {
      setStatus("ok", "Thanks. Your offer was sent. We reply by email.");
      form.reset();
      return;
    }
    submit.disabled = true;
    setStatus("pending", "Sending your offer...");
    try {
      const ctl = typeof AbortController === "function" ? new AbortController() : null;
      const timer = ctl ? setTimeout(() => ctl.abort(), TIMEOUT_MS) : 0;
      const res = await fetch(endpoint, {
        method: "POST",
        signal: ctl ? ctl.signal : undefined,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: itemId, offer: val, email: em, note: note.value.trim().slice(0, 500) }),
      }).finally(() => clearTimeout(timer));
      let data = {};
      try {
        data = await res.json();
      } catch (_) {
        data = {};
      }
      if (res.ok && data.ok) {
        setStatus("ok", "Thanks. Your offer of $" + val.toFixed(2) + " was sent. We reply by email, usually within a day.");
        form.reset();
        return;
      }
      const hit = MESSAGES[data.error] || (res.status === 503 ? MESSAGES.offers_closed : null);
      if (hit) setStatus(hit[0], hit[1]);
      else setStatus("err", "Your offer did not go through. Please try again or message us about this part.");
    } catch (_) {
      setStatus("err", "Your offer did not go through. Please check your connection and try again.");
    } finally {
      submit.disabled = false;
    }
  });
})();
