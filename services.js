(() => {
  "use strict";

  const loadedAt = Date.now();
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const reveals = document.querySelectorAll(".reveal");
  if (prefersReduced || !("IntersectionObserver" in window)) {
    reveals.forEach((el) => el.classList.add("visible"));
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    reveals.forEach((el) => io.observe(el));
  }

  const toggleBtn = document.getElementById("navToggle");
  const drawer = document.getElementById("drawer");
  if (toggleBtn && drawer) {
    const setOpen = (open) => {
      drawer.hidden = !open;
      drawer.classList.toggle("open", open);
      drawer.classList.toggle("is-open", open);
      toggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
      toggleBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    };
    setOpen(false);
    toggleBtn.addEventListener("click", () => {
      setOpen(drawer.hidden);
    });
    drawer.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => setOpen(false));
    });
    document.addEventListener("click", (e) => {
      if (drawer.hidden) return;
      if (drawer.contains(e.target) || toggleBtn.contains(e.target)) return;
      setOpen(false);
    });
    document.addEventListener("keydown", (e) => {
      if (!drawer.hidden && e.key === "Escape") {
        setOpen(false);
        toggleBtn.focus();
      }
    });
  }

  const nav = document.getElementById("nav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("is-solid", window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  const sendBtn = document.getElementById("f-send");
  const intakeForm = sendBtn ? sendBtn.closest("form") : null;
  const emailInput = document.getElementById("f-email");
  const emailErr = document.getElementById("f-email-err");

  function setEmailError(msg) {
    if (!emailInput) return;
    if (msg) {
      emailInput.setAttribute("aria-invalid", "true");
      if (emailErr) {
        emailErr.textContent = msg;
        emailErr.hidden = false;
      }
    } else {
      emailInput.removeAttribute("aria-invalid");
      if (emailErr) {
        emailErr.textContent = "";
        emailErr.hidden = true;
      }
    }
  }

  if (emailInput) {
    emailInput.addEventListener("input", () => setEmailError(""));
  }

  async function handleIntakeSubmit(e) {
    if (e) e.preventDefault();
    if (!sendBtn) return;

    const email = String((emailInput && emailInput.value) || "").trim();
    const status = document.getElementById("f-status");
    const gotcha = document.getElementById("f-gotcha");
    const endpoint = (window.BUC_FORMSPREE && window.BUC_FORMSPREE.endpoint) || "";

    function setStatus(kindStatus, text) {
      if (!status) return;
      status.hidden = !text;
      status.className =
        "contact-status" + (kindStatus ? " contact-status--" + kindStatus : "");
      status.textContent = text || "";
    }

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
      setEmailError("Enter a valid email address so we can reply.");
      setStatus("err", "Enter a valid email address.");
      if (emailInput) emailInput.focus();
      return;
    }
    setEmailError("");

    if ((gotcha && String(gotcha.value || "").trim()) || Date.now() - loadedAt < 800) {
      setStatus("ok", "Thanks — details received.");
      if (intakeForm) intakeForm.reset();
      return;
    }

    const store = ((document.getElementById("f-store") || {}).value || "").trim();
    const count = (document.getElementById("f-count") || {}).value || "";
    const plan = (document.getElementById("f-plan") || {}).value || "";
    const photos = ((document.getElementById("f-photos") || {}).value || "").trim();
    const fallbackTopic = "Listing services - " + plan;
    const payload = {
      email,
      store_url: store,
      sku_count: count,
      plan,
      photos,
      topic: "Listing services",
      message: `Listing services intake\nPlan: ${plan}\nSKU count: ${count}\nStore: ${store}\nPhotos: ${photos}`,
      _subject: `BuccaneerSalvage services - ${plan} (${count})`,
      source: "hub-services",
      page: location.href,
    };

    if (!endpoint) {
      setStatus(
        "warn",
        "Form backend not configured yet. Opening the main contact page."
      );
      window.location.href = "contact.html?topic=" + encodeURIComponent(fallbackTopic);
      return;
    }

    sendBtn.disabled = true;
    setStatus("pending", "Sending…");
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setStatus("ok", "Sent. We will reply at " + email + ".");
        if (intakeForm) intakeForm.reset();
      } else {
        const body = await res.json().catch(() => ({}));
        setStatus("err", (body && body.error) || "Send failed — try the contact page.");
      }
    } catch (_) {
      setStatus("err", "Network error. Try the contact page.");
    } finally {
      sendBtn.disabled = false;
    }
  }

  if (intakeForm) {
    intakeForm.addEventListener("submit", handleIntakeSubmit);
  } else if (sendBtn) {
    sendBtn.addEventListener("click", handleIntakeSubmit);
  }
})();
