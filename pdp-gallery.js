(() => {
  "use strict";

  /**
   * PDP media: thumb swap, click-to-zoom lightbox + pinch.
   * Cart lives in main.js.
   * Progressive enhancement — without JS the hero photo still renders.
   */

  function isSafeImageSrc(u) {
    const s = String(u || "").trim();
    if (/^\.\.\/assets\/pdp-gallery\/[A-Z0-9]{16,32}\/\d{2}\.webp$/.test(s)) {
      return true;
    }
    if (!/^https:\/\//i.test(s)) return false;
    try {
      const host = new URL(s).hostname.toLowerCase();
      return (
        host === "buccaneersalvage.github.io" ||
        host.endsWith(".squareup.com") ||
        host.endsWith(".squarecdn.com") ||
        host === "items-images-production.s3.us-west-2.amazonaws.com"
      );
    } catch (_) {
      return false;
    }
  }

  function initThumbs() {
    const stage = document.querySelector(".pdp-stage");
    if (!stage) return;
    const imgEl = document.getElementById("pdpMainImage");
    const videoEl = document.getElementById("pdpMainVideo");
    const buttons = document.querySelectorAll(".pdp-thumb-btn");
    if (!imgEl || !buttons.length) return;

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        buttons.forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");

        if (btn.dataset.type === "video" && videoEl) {
          imgEl.hidden = true;
          videoEl.hidden = false;
        } else {
          if (videoEl && !videoEl.paused) videoEl.pause();
          if (videoEl) videoEl.hidden = true;
          imgEl.hidden = false;
          const src = btn.dataset.src || "";
          if (isSafeImageSrc(src)) imgEl.src = src;
        }
      });
    });
  }

  function initLightbox() {
    const box = document.getElementById("pdpLightbox");
    const img = document.getElementById("pdpLightboxImage");
    const main = document.getElementById("pdpMainImage");
    if (!box || !img || !main) return;
    const stage = box.querySelector(".pdp-lightbox-stage") || box;
    const closeBtn = box.querySelector(".pdp-lightbox-close");
    const videoEl = document.getElementById("pdpMainVideo");

    let scale = 1;
    let lastTap = 0;
    let pinch0 = 0;
    let scale0 = 1;

    function setScale(n) {
      scale = Math.min(4, Math.max(1, n));
      img.style.transform = "scale(" + scale + ")";
    }

    function resetZoom() {
      setScale(1);
    }

    function open() {
      if (videoEl && !videoEl.hidden) return;
      const src = main.getAttribute("src") || "";
      if (!isSafeImageSrc(src)) return;
      img.src = src;
      img.alt = main.alt || "";
      box.hidden = false;
      document.body.classList.add("pdp-lightbox-open");
      resetZoom();
      if (closeBtn) closeBtn.focus();
    }

    function close() {
      if (box.hidden) return;
      box.hidden = true;
      document.body.classList.remove("pdp-lightbox-open");
      resetZoom();
    }

    main.setAttribute("tabindex", "0");
    main.setAttribute("role", "button");
    main.setAttribute("aria-label", "Zoom photo");
    main.addEventListener("click", open);
    main.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
    if (closeBtn) closeBtn.addEventListener("click", close);
    box.addEventListener("click", (e) => {
      if (e.target === box) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !box.hidden) close();
    });

    stage.addEventListener(
      "wheel",
      (e) => {
        if (box.hidden) return;
        e.preventDefault();
        setScale(scale + (e.deltaY < 0 ? 0.2 : -0.2));
      },
      { passive: false }
    );

    img.addEventListener("pointerup", () => {
      if (box.hidden) return;
      const now = Date.now();
      if (now - lastTap < 280) {
        setScale(scale > 1 ? 1 : 2);
        lastTap = 0;
      } else {
        lastTap = now;
      }
    });

    stage.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length === 2) {
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          pinch0 = Math.hypot(dx, dy) || 1;
          scale0 = scale;
        }
      },
      { passive: true }
    );
    stage.addEventListener(
      "touchmove",
      (e) => {
        if (e.touches.length === 2 && pinch0) {
          e.preventDefault();
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          setScale(scale0 * (Math.hypot(dx, dy) / pinch0));
        }
      },
      { passive: false }
    );
  }

  function init() {
    initThumbs();
    initLightbox();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
