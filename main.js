(() => {
  "use strict";

  const year = document.getElementById("y");
  if (year) year.textContent = String(new Date().getFullYear());

  /* Sticky nav solid state */
  const nav = document.getElementById("nav");
  const onScroll = () => {
    if (!nav) return;
    nav.classList.toggle("is-solid", window.scrollY > 24);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* Mobile drawer */
  const toggle = document.getElementById("navToggle");
  const drawer = document.getElementById("drawer");
  if (toggle && drawer) {
    const main = document.getElementById("main");
    const setOpen = (open) => {
      drawer.classList.toggle("is-open", open);
      drawer.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      document.body.classList.toggle("nav-open", open);
      if (main) {
        if (open) main.setAttribute("inert", "");
        else main.removeAttribute("inert");
      }
      if (open) {
        const first = drawer.querySelector("a");
        if (first) first.focus();
      }
    };
    setOpen(false);
    toggle.addEventListener("click", () => {
      setOpen(!drawer.classList.contains("is-open"));
    });
    drawer.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => setOpen(false));
    });
    document.addEventListener("click", (e) => {
      if (!drawer.classList.contains("is-open")) return;
      if (drawer.contains(e.target) || toggle.contains(e.target)) return;
      setOpen(false);
    });
    document.addEventListener("keydown", (e) => {
      if (!drawer.classList.contains("is-open")) return;
      if (e.key === "Escape") {
        setOpen(false);
        toggle.focus();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = [...drawer.querySelectorAll("a, button")].filter(
        (el) => !el.hasAttribute("disabled")
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  /* Scroll reveals */
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
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
    );
    nodes.forEach((el) => io.observe(el));
  }
})();
