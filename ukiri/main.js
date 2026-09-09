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

  const toggle = document.getElementById("navToggle");
  const drawer = document.getElementById("drawer");
  if (toggle && drawer) {
    toggle.addEventListener("click", () => {
      const open = !drawer.classList.contains("is-open");
      drawer.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });
    drawer.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        drawer.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

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
      { rootMargin: "0px 0px -6% 0px", threshold: 0.1 }
    );
    nodes.forEach((el) => io.observe(el));
  }

  const copyBtn = document.getElementById("copyStickyBtn");
  const stickyEl = document.getElementById("stickyCopy");
  if (copyBtn && stickyEl) {
    copyBtn.addEventListener("click", async () => {
      const text = stickyEl.textContent || "";
      try {
        await navigator.clipboard.writeText(text);
        const prev = copyBtn.textContent;
        copyBtn.textContent = "Copied ✓";
        setTimeout(() => {
          copyBtn.textContent = prev;
        }, 1800);
      } catch {
        const range = document.createRange();
        range.selectNodeContents(stickyEl);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        copyBtn.textContent = "Select + Ctrl/Cmd+C";
      }
    });
  }
})();
