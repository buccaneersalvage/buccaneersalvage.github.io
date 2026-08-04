(() => {
  "use strict";

  const CATALOG_URL = "assets/square-catalog.json";
  const STORE = "https://buccaneersalvage.square.site/";

  const money = (n) =>
    n == null || Number.isNaN(Number(n))
      ? ""
      : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  const catLabel = (c) =>
    ({
      "air-spring": "Air spring",
      brake: "Brake",
      turbo: "Turbo core",
      pump: "Pump core",
      other: "Parts",
    }[c] || "Parts");

  const matchFilter = (item, filter) => {
    if (filter === "all") return true;
    if (filter === "cores") return item.category === "turbo" || item.category === "pump";
    return item.category === filter;
  };

  const cardHtml = (item, { marquee = false } = {}) => {
    const cls = marquee ? "sq-card sq-card--marquee" : "sq-card";
    const img = item.image
      ? `<img src="${escapeAttr(item.image)}" alt="" loading="lazy" width="320" height="240" />`
      : `<div class="sq-card-ph" aria-hidden="true">☠</div>`;
    const price = money(item.price);
    const badge = catLabel(item.category);
    // Product URL = Square checkout only (payment/shipping). Catalog lives on this hub page.
    const href = item.url || STORE;
    return `
      <a class="${cls}" href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer"
         title="Opens Square for secure checkout">
        <div class="sq-card-media">${img}</div>
        <div class="sq-card-body">
          <span class="sq-card-badge">${escapeHtml(badge)}</span>
          <h3 class="sq-card-title">${escapeHtml(item.name)}</h3>
          ${price ? `<p class="sq-card-price">${escapeHtml(price)}</p>` : ""}
          <span class="sq-card-go">Buy / Checkout on Square →</span>
        </div>
      </a>`;
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function renderMarquee(items) {
    const track = document.getElementById("sqMarqueeTrack");
    const wrap = document.getElementById("sqMarquee");
    if (!track || !wrap) return;

    const featured = items
      .filter((i) => i.image)
      .slice()
      .sort((a, b) => {
        const rank = (c) => ({ turbo: 0, pump: 1, "air-spring": 2, brake: 3, other: 4 }[c] ?? 9);
        return rank(a.category) - rank(b.category);
      })
      .slice(0, 14);

    if (!featured.length) {
      wrap.hidden = true;
      return;
    }

    // Duplicate sequence for seamless CSS loop
    const seq = featured.map((i) => cardHtml(i, { marquee: true })).join("");
    track.innerHTML = seq + seq;

    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      wrap.classList.add("is-static");
      return;
    }

    // Pause on hover / focus
    const pause = () => wrap.setAttribute("data-paused", "true");
    const play = () => wrap.setAttribute("data-paused", "false");
    wrap.addEventListener("mouseenter", pause);
    wrap.addEventListener("mouseleave", play);
    wrap.addEventListener("focusin", pause);
    wrap.addEventListener("focusout", play);
  }

  function renderGrid(items, filter) {
    const grid = document.getElementById("sqGrid");
    if (!grid) return;
    const list = items.filter((i) => matchFilter(i, filter));
    if (!list.length) {
      grid.innerHTML = `<p class="sq-empty">No parts in this bay right now. <a href="${STORE}" target="_blank" rel="noopener noreferrer">Open the full store</a>.</p>`;
      return;
    }
    grid.innerHTML = list.map((i) => cardHtml(i)).join("");
  }

  function wireFilters(items) {
    const buttons = document.querySelectorAll(".sq-filter");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const filter = btn.getAttribute("data-filter") || "all";
        buttons.forEach((b) => {
          const on = b === btn;
          b.classList.toggle("is-on", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        renderGrid(items, filter);
      });
    });
  }

  async function boot() {
    const meta = document.getElementById("sqMeta");
    try {
      const res = await fetch(CATALOG_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`catalog ${res.status}`);
      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];
      if (meta) {
        const when = data.updated ? ` · snapshot ${data.updated.slice(0, 10)}` : "";
        meta.textContent = `${items.length} parts on this page${when} · checkout via Square`;
      }
      renderMarquee(items);
      renderGrid(items, "all");
      wireFilters(items);
    } catch (err) {
      if (meta) meta.textContent = "Catalog offline — try refresh.";
      const grid = document.getElementById("sqGrid");
      if (grid) {
        grid.innerHTML = `<p class="sq-empty">Could not load the catalog snapshot. Refresh this page.
          Checkout still runs on Square when links work.</p>`;
      }
      console.warn("[square-shop]", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
