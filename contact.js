(() => {
  "use strict";

  const cfg = window.BUC_FORMSPREE || {};
  const form = document.getElementById("bucContactForm");
  const status = document.getElementById("bucContactStatus");
  const submitBtn = document.getElementById("bucContactSubmit");
  const banner = document.getElementById("bucPaidBanner");
  if (!form || !status) return;

  const params = new URLSearchParams(location.search);
  const topicEl = document.getElementById("c-topic");
  const msgEl = document.getElementById("c-message");
  const nameEl = document.getElementById("c-name");
  const emailEl = document.getElementById("c-email");

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

  if (topicQ && topicEl && !topicEl.value) {
    topicEl.value = topicQ.slice(0, 80);
  } else if (fromSquare && topicEl && !topicEl.value) {
    topicEl.value =
      sourceQ === "square-services"
        ? "Listing services — after pay"
        : "Store order — after pay";
  }

  if (planQ && topicEl && topicEl.value && !/plan/i.test(topicEl.value)) {
    const next = (topicEl.value + " · " + planQ).slice(0, 80);
    topicEl.value = next;
  }

  if (msgEl && !msgEl.value) {
    const bits = [];
    if (fromSquare) {
      bits.push(
        sourceQ === "square-services"
          ? "I paid on Square for listing services."
          : "I paid on Square (store checkout)."
      );
      bits.push("What I need next:");
      if (sourceQ === "square-services") {
        bits.push("- Photos / part numbers / store URL:");
        bits.push("- How many listings / plan:");
      } else {
        bits.push("- Order or item notes:");
        bits.push("- Questions:");
      }
    }
    if (planQ) bits.push("Plan: " + planQ);
    if (orderHint) bits.push("Square ref: " + orderHint);
    if (msgQ) bits.push(msgQ);
    if (bits.length) msgEl.value = bits.join("\n").slice(0, 2000);
  }

  if (fromSquare && banner) {
    banner.hidden = false;
    const title =
      sourceQ === "square-services"
        ? "Payment received — send the job details"
        : "Payment received — send a note if you need anything";
    const body =
      sourceQ === "square-services"
        ? "Square checkout is done. Use this form so Cap'n Jules gets your photos, part numbers, or store link. Work starts when the message lands."
        : "Thanks for your store order. Optional: use this form for delivery notes, fitment questions, or pickup timing. No public email on the site — this form is the channel.";
    banner.innerHTML =
      "<strong class=\"gold-em\">" +
      title +
      "</strong> " +
      body;
  }

  function setStatus(kind, text) {
    status.hidden = !text;
    status.className = "contact-status" + (kind ? " contact-status--" + kind : "");
    status.textContent = text || "";
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
    if (submitBtn) submitBtn.disabled = true;
    setStatus("pending", "Sending…");

    const data = new FormData(form);
    /* Honeypot: bots fill _gotcha; humans leave it empty */
    if (String(data.get("_gotcha") || "").trim()) {
      setStatus("ok", "Thanks — message sent.");
      form.reset();
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

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
        setStatus("ok", "Sent. I’ll get back to you at " + payload.email + ".");
        form.reset();
        if (banner) banner.hidden = true;
      } else {
        const err =
          (body && body.errors && body.errors.map((x) => x.message).join(" ")) ||
          (body && body.error) ||
          "Could not send. Try again in a minute.";
        setStatus("err", err);
      }
    } catch (err) {
      setStatus("err", "Network error — check connection and try again.");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
})();
