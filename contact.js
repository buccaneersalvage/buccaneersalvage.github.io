(() => {
  "use strict";

  const cfg = window.BUC_FORMSPREE || {};
  const form = document.getElementById("bucContactForm");
  const status = document.getElementById("bucContactStatus");
  const submitBtn = document.getElementById("bucContactSubmit");
  const banner = document.getElementById("bucPaidBanner");
  if (!form || !status) return;

  const loadedAt = Date.now();
  const params = new URLSearchParams(location.search);
  const topicEl = document.getElementById("c-topic");
  const msgEl = document.getElementById("c-message");
  const nameEl = document.getElementById("c-name");
  const emailEl = document.getElementById("c-email");
  const emailErr = document.getElementById("c-email-err");
  const msgErr = document.getElementById("c-message-err");

  const topicQ = (params.get("topic") || params.get("subject") || "").trim();
  const sourceQ = (params.get("source") || "").trim().toLowerCase();
  const planQ = (params.get("plan") || "").trim();
  const msgQ = (params.get("message") || params.get("msg") || "").trim();
  // Square sometimes appends order/transaction ids on redirect
  const orderHint = (
    params.get("orderId") ||
    params.get("order_id") ||
    params.get("transactionId") ||
    params.get("transaction_id") ||
    params.get("checkoutId") ||
    ""
  ).trim();

  const SQUARE_SOURCES = new Set([
    "square",
    "square-store",
    "square-services",
    "square-pay",
    "paid",
  ]);
  const fromSquare = SQUARE_SOURCES.has(sourceQ) || params.get("paid") === "1";

  let formSource = "hub-contact";
  if (sourceQ === "square-store") formSource = "hub-contact-square-store";
  else if (sourceQ === "square-services") formSource = "hub-contact-square-services";
  else if (fromSquare) formSource = "hub-contact-square";
  else if (sourceQ === "hub-services" || sourceQ === "services") formSource = "hub-contact-services";

  const titleEl = document.getElementById("bucContactTitle");
  const asideEl = document.getElementById("bucContactAside");
  const ledeEl = document.getElementById("bucContactLede");
  const footEl = document.getElementById("bucContactFoot");
  const secondaryEl = document.getElementById("bucContactSecondary");
  const isServicesPay = sourceQ === "square-services";

  function makeGoldLink(href, label) {
    const a = document.createElement("a");
    a.className = "link-gold";
    a.href = href;
    a.textContent = label;
    return a;
  }

  // Paid listing-services handoff: job intake page, not generic yard contact
  if (isServicesPay) {
    document.title = "Send listing details — BuccaneerSalvage";
    if (titleEl) titleEl.textContent = "You're paid — send the details";
    if (asideEl) {
      asideEl.textContent =
        "Square already took payment. Fill this once so we can start the listing work.";
    }
    if (ledeEl) ledeEl.hidden = true;
    if (submitBtn) submitBtn.textContent = "Send job details";
    if (secondaryEl) {
      secondaryEl.href = "services.html";
      secondaryEl.textContent = "Back to services";
    }
    if (footEl) {
      footEl.replaceChildren(
        document.createTextNode(
          "One message is enough — photos, part numbers, or your store link. "
        ),
        makeGoldLink("privacy.html", "Privacy"),
        document.createTextNode(" · "),
        makeGoldLink("services.html", "Services")
      );
    }
    if (msgEl) {
      msgEl.placeholder =
        "Paste photo links, part numbers, how many listings, and any notes…";
    }
  }

  if (topicQ && topicEl && !topicEl.value) {
    topicEl.value = topicQ.slice(0, 80);
  } else if (fromSquare && topicEl && !topicEl.value) {
    topicEl.value = isServicesPay
      ? "Listing services"
      : "Store order — note";
  }

  if (planQ && topicEl && topicEl.value && !/plan/i.test(topicEl.value)) {
    const next = (topicEl.value + " · " + planQ).slice(0, 80);
    topicEl.value = next;
  }

  if (msgEl && !msgEl.value) {
    const bits = [];
    if (isServicesPay) {
      bits.push("Paid on Square for listing services.");
      bits.push("");
      bits.push("Photos / Drive link:");
      bits.push("");
      bits.push("Part numbers (or store URL to review):");
      bits.push("");
      bits.push("How many listings / which plan:");
    } else if (fromSquare) {
      bits.push("Paid on Square (store checkout).");
      bits.push("Optional notes:");
    }
    if (planQ) bits.push("Plan: " + planQ);
    if (orderHint) bits.push("Square ref: " + orderHint);
    if (msgQ) bits.push(msgQ);
    if (bits.length) msgEl.value = bits.join("\n").slice(0, 2000);
  }

  if (fromSquare && banner) {
    banner.hidden = false;
    const strong = document.createElement("strong");
    strong.className = "gold-em";
    if (isServicesPay) {
      strong.textContent = "Next step (required)";
      banner.replaceChildren(
        strong,
        document.createTextNode(
          " Payment is done. Work starts when this form is sent — not before. Typical handling: 1–2 business days after we have your details."
        )
      );
    } else {
      strong.textContent = "Optional note";
      banner.replaceChildren(
        strong,
        document.createTextNode(
          " Store orders already have a confirmation page. Use this only if you need delivery or pickup notes."
        )
      );
    }
  }

  function setStatus(kind, text) {
    status.hidden = !text;
    status.className = "contact-status" + (kind ? " contact-status--" + kind : "");
    status.textContent = text || "";
  }

  function setFieldError(inputEl, errEl, message) {
    if (!inputEl) return;
    if (message) {
      inputEl.setAttribute("aria-invalid", "true");
      if (errEl) {
        errEl.textContent = message;
        errEl.hidden = false;
      }
    } else {
      inputEl.removeAttribute("aria-invalid");
      if (errEl) {
        errEl.textContent = "";
        errEl.hidden = true;
      }
    }
  }

  if (emailEl) {
    emailEl.addEventListener("input", () => setFieldError(emailEl, emailErr, ""));
  }
  if (msgEl) {
    msgEl.addEventListener("input", () => setFieldError(msgEl, msgErr, ""));
  }

  function validateFields() {
    let firstInvalid = null;
    const emailVal = String((emailEl && emailEl.value) || "").trim();
    const msgVal = String((msgEl && msgEl.value) || "").trim();

    if (!emailVal || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(emailVal)) {
      setFieldError(emailEl, emailErr, "Enter a valid email address so we can reply.");
      firstInvalid = firstInvalid || emailEl;
    } else {
      setFieldError(emailEl, emailErr, "");
    }

    if (!msgVal) {
      setFieldError(msgEl, msgErr, "Tell us the part number, vehicle, or question.");
      firstInvalid = firstInvalid || msgEl;
    } else {
      setFieldError(msgEl, msgErr, "");
    }

    if (firstInvalid) {
      setStatus("err", "Check the highlighted fields below and try again.");
      firstInvalid.focus();
      return false;
    }
    return true;
  }

  if (!cfg.endpoint) {
    setStatus(
      "warn",
      "Contact is not configured yet. Set the Formspree endpoint in formspree-config.js."
    );
    if (submitBtn) submitBtn.disabled = true;
    return;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validateFields()) return;

    const data = new FormData(form);
    /* Honeypot + instant-POST bot trap: never burn real Formspree quota on bots */
    if (String(data.get("_gotcha") || "").trim() || Date.now() - loadedAt < 800) {
      setStatus("ok", "Thanks — message sent.");
      form.reset();
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    setStatus("pending", "Sending…");

    const topicVal = String(data.get("topic") || "").trim();
    const payload = {
      name: String(data.get("name") || "").trim(),
      email: String(data.get("email") || "").trim(),
      phone: String(data.get("phone") || "").trim(),
      topic: topicVal,
      message: String(data.get("message") || "").trim(),
      _subject: topicVal
        ? "BuccaneerSalvage hub: " + topicVal
        : fromSquare
          ? "BuccaneerSalvage hub: after Square pay"
          : "BuccaneerSalvage hub contact",
      source: formSource,
      page: location.href,
    };
    if (orderHint) payload.square_ref = orderHint;
    if (planQ) payload.plan = planQ;

    try {
      const res = await fetch(cfg.endpoint, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        setStatus("ok", "Sent. We will reply at " + payload.email + ".");
        form.reset();
        if (banner) banner.hidden = true;
      } else {
        const err =
          (body && body.errors && body.errors.map((x) => x.message).join(" ")) ||
          (body && body.error) ||
          "Could not send. Try again in a minute.";
        setStatus("err", err);
      }
    } catch (_) {
      setStatus("err", "Network error — check your connection and try again.");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
})();
