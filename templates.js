(() => {
  "use strict";

  const filterBtns = document.querySelectorAll(".filter-btn");
  const cards = document.querySelectorAll(".template-card");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      filterBtns.forEach((b) => {
        const on = b === btn;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      cards.forEach((card) => {
        const cats = (card.dataset.categories || "").split(/\s+/);
        const show = filter === "all" || cats.includes(filter);
        card.classList.toggle("hidden", !show);
      });
    });
  });

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
      { threshold: 0.05 }
    );
    reveals.forEach((el) => io.observe(el));
  }

  const nav = document.getElementById("nav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("is-solid", window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
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
    toggleBtn.addEventListener("click", () => setOpen(drawer.hidden));
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
})();
