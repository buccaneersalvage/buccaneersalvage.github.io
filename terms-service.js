(() => {
  "use strict";

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

  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll(".toc a").forEach((link) => {
    link.addEventListener("click", (e) => {
      const href = link.getAttribute("href") || "";
      if (!href.startsWith("#")) return;
      e.preventDefault();
      const id = href.slice(1);
      const target = document.getElementById(id);
      if (target) {
        target.scrollIntoView({
          behavior: prefersReduced ? "auto" : "smooth",
          block: "start",
        });
        history.pushState(null, "", "#" + id);
      }
    });
  });
})();
