(() => {
  "use strict";

  const y = document.getElementById("y");
  if (y) y.textContent = String(new Date().getFullYear());

  const nav = document.getElementById("nav");
  const onScroll = () => {
    if (nav) nav.classList.toggle("is-solid", window.scrollY > 20);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  // Accessible mobile drawer: hidden toggle, Escape close, outside click, focus return
  const toggle = document.getElementById("navToggle");
  const drawer = document.getElementById("drawer");
  const setDrawer = (open, restoreFocus) => {
    if (!toggle || !drawer) return;
    drawer.classList.toggle("is-open", open);
    if (open) {
      drawer.removeAttribute("hidden");
    } else {
      drawer.setAttribute("hidden", "");
    }
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    document.body.classList.toggle("nav-open", open);
    if (!open && restoreFocus) {
      toggle.focus();
    }
  };
  if (toggle && drawer) {
    toggle.addEventListener("click", () => {
      const open = drawer.hasAttribute("hidden") || !drawer.classList.contains("is-open");
      setDrawer(open, false);
      if (open) {
        const firstLink = drawer.querySelector("a");
        if (firstLink) firstLink.focus();
      }
    });
    drawer.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => setDrawer(false, false));
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && drawer.classList.contains("is-open")) {
        setDrawer(false, true);
      }
    });
    document.addEventListener("click", (ev) => {
      if (!drawer.classList.contains("is-open")) return;
      const target = ev.target;
      if (target instanceof Node && !drawer.contains(target) && !toggle.contains(target)) {
        setDrawer(false, false);
      }
    });
  }

  // Reveal observer
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nodes = document.querySelectorAll(".reveal");
  if (prefersReduced || !("IntersectionObserver" in window)) {
    nodes.forEach((el) => el.classList.add("is-in"));
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.08 }
    );
    nodes.forEach((el) => io.observe(el));
  }

  // Copy-to-clipboard helpers (accountability sticky & roast X caption)
  const bindCopy = (btnId, sourceId) => {
    const btn = document.getElementById(btnId);
    const src = document.getElementById(sourceId);
    if (!btn || !src) return;
    btn.addEventListener("click", async () => {
      const text = src.textContent || "";
      const prev = btn.textContent;
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.textContent = prev;
        }, 1800);
      } catch {
        const range = document.createRange();
        range.selectNodeContents(src);
        const sel = window.getSelection();
        if (sel) {
          sel.removeAllRanges();
          sel.addRange(range);
        }
        btn.textContent = "Select + Ctrl/Cmd+C";
      }
    });
  };
  bindCopy("copyStickyBtn", "stickyCopy");
  bindCopy("copyGodmodeBtn", "godmodeXCopy");

  // Accessible tips form validation + anti-bot mount timing gate (support.html)
  const tipForm = document.getElementById("tipForm");
  if (tipForm instanceof HTMLFormElement) {
    const mountedAt = Date.now();
    const statusEl = document.getElementById("tipFormStatus");
    const fields = [
      { id: "name", errId: "nameError", msg: "Please enter your name or press outlet." },
      { id: "email", errId: "emailError", msg: "Please enter a valid email address so I can reply." },
      { id: "message", errId: "messageError", msg: "Please enter your tip, question, or document details." },
    ];

    const setFieldError = (input, errEl, message) => {
      if (!input || !errEl) return;
      if (message) {
        input.setAttribute("aria-invalid", "true");
        errEl.textContent = message;
        errEl.removeAttribute("hidden");
      } else {
        input.removeAttribute("aria-invalid");
        errEl.textContent = "";
        errEl.setAttribute("hidden", "");
      }
    };

    fields.forEach(({ id, errId }) => {
      const input = document.getElementById(id);
      const errEl = document.getElementById(errId);
      if (input && errEl) {
        input.addEventListener("input", () => setFieldError(input, errEl, ""));
      }
    });

    tipForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (statusEl) {
        statusEl.setAttribute("hidden", "");
        statusEl.classList.remove("is-error");
        statusEl.textContent = "";
      }

      const gotcha = tipForm.querySelector('input[name="_gotcha"]');
      if (gotcha instanceof HTMLInputElement && gotcha.value.trim() !== "") {
        return;
      }

      let firstInvalid = null;
      fields.forEach(({ id, errId, msg }) => {
        const input = document.getElementById(id);
        const errEl = document.getElementById(errId);
        if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) return;
        const val = input.value.trim();
        const emailBad = input.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
        if (!val || emailBad) {
          setFieldError(input, errEl, msg);
          if (!firstInvalid) firstInvalid = input;
        } else {
          setFieldError(input, errEl, "");
        }
      });

      if (firstInvalid) {
        firstInvalid.focus();
        return;
      }

      if (Date.now() - mountedAt < 1200) {
        if (statusEl) {
          statusEl.textContent = "Please wait a moment and press Send again.";
          statusEl.classList.add("is-error");
          statusEl.removeAttribute("hidden");
        }
        return;
      }

      const submitBtn = tipForm.querySelector('button[type="submit"]');
      const prevLabel = submitBtn ? submitBtn.textContent : "Send tip";
      if (submitBtn instanceof HTMLButtonElement) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Sending...";
      }
      try {
        const resp = await fetch(tipForm.action, {
          method: "POST",
          body: new FormData(tipForm),
          headers: { Accept: "application/json" },
        });
        if (resp.ok) {
          tipForm.reset();
          if (statusEl) {
            statusEl.textContent = "Thank you. Your message has been sent.";
            statusEl.classList.remove("is-error");
            statusEl.removeAttribute("hidden");
          }
        } else {
          if (statusEl) {
            statusEl.textContent = "Submission could not be completed right now. Please check your entries and try again.";
            statusEl.classList.add("is-error");
            statusEl.removeAttribute("hidden");
          }
        }
      } catch {
        if (statusEl) {
          statusEl.textContent = "Network error while sending. Please check your connection and try again.";
          statusEl.classList.add("is-error");
          statusEl.removeAttribute("hidden");
        }
      } finally {
        if (submitBtn instanceof HTMLButtonElement) {
          submitBtn.disabled = false;
          submitBtn.textContent = prevLabel;
        }
      }
    });
  }
})();
