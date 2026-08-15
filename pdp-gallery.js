(() => {
  "use strict";

  /**
   * Product page media switcher — swaps the main stage (photo or video) when
   * a thumbnail is clicked, instead of the thumbnail opening a new tab.
   * Progressive enhancement: without JS the hero photo + native video
   * (if present) still both render from build_static_pdps.py, just without
   * the click-to-swap behavior.
   */
  function isSafeImageSrc(u) {
    const s = String(u || "").trim();
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

  function init() {
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
