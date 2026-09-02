(() => {
  "use strict";

  const cfg = window.BUC_FORMSPREE || {};
  const form = document.getElementById("bucContactForm");
  const status = document.getElementById("bucContactStatus");
  const submitBtn = document.getElementById("bucContactSubmit");
  if (!form || !status) return;

  const params = new URLSearchParams(location.search);
  const topic = params.get("topic") || params.get("subject") || "";
  const topicEl = document.getElementById("c-topic");
  if (topic && topicEl && !topicEl.value) topicEl.value = topic.slice(0, 80);

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
        : "BuccaneerSalvage hub contact",
      source: "hub-contact",
      page: location.href,
    };

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
