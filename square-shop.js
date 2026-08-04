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

  /** Turbo / injection pump: as-is cores — warn on the card + checkout CTA */
  const isCoreParts = (item) =>
    item.category === "turbo" || item.category === "pump";

  const CORE_WARN = "FOR PARTS OR REBUILD · UNTESTED · NO RETURNS";

  const matchFilter = (item, filter) => {
    if (filter === "all") return true;
    if (filter === "cores") return isCoreParts(item);
    return item.category === filter;
  };

  const cardHtml = (item, { marquee = false, featured = false } = {}) => {
    const core = isCoreParts(item);
    const cls = [
      "sq-card",
      marquee ? "sq-card--marquee" : "",
      featured ? "sq-card--featured" : "",
      core ? "sq-card--core" : "",
    ]
      .filter(Boolean)
      .join(" ");
    const img = item.image
      ? `<img src="${escapeAttr(item.image)}" alt="" loading="${featured || marquee ? "eager" : "lazy"}" width="320" height="240" />`
      : `<div class="sq-card-ph" aria-hidden="true">☠</div>`;
    const price = money(item.price);
    const badge = catLabel(item.category);
    const href = item.url || STORE;
    const warn = core
      ? `<p class="sq-card-warn" role="status">${escapeHtml(CORE_WARN)}</p>`
      : "";
    const mediaWarn = core
      ? `<span class="sq-card-ribbon">${escapeHtml("FOR PARTS · NO RETURNS")}</span>`
      : "";
    const cta = core
      ? "Checkout — for parts / rebuild · no returns →"
      : "Buy / Checkout on Square →";
    const titleAttr = core
      ? "For parts or rebuild only. Untested. No returns. Opens Square checkout."
      : "Opens Square for secure checkout";
    return `
      <a class="${cls}" href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer"
         title="${escapeAttr(titleAttr)}">
        <div class="sq-card-media">${mediaWarn}${img}</div>
        <div class="sq-card-body">
          <span class="sq-card-badge">${escapeHtml(badge)}</span>
          <h3 class="sq-card-title">${escapeHtml(item.name)}</h3>
          ${warn}
          ${price ? `<p class="sq-card-price">${escapeHtml(price)}</p>` : ""}
          <span class="sq-card-go">${escapeHtml(cta)}</span>
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

  function sortShop(list) {
    const rank = (c) => ({ turbo: 0, pump: 1, "air-spring": 2, brake: 3, other: 4 }[c] ?? 9);
    return list.slice().sort((a, b) => rank(a.category) - rank(b.category) || a.name.localeCompare(b.name));
  }

  function renderFeaturedCores(items) {
    const host = document.getElementById("sqFeaturedCores");
    if (!host) return;
    const cores = sortShop(items.filter(isCoreParts));
    if (!cores.length) {
      host.hidden = true;
      return;
    }
    host.hidden = false;
    host.innerHTML = cores.map((i) => cardHtml(i, { featured: true })).join("");
  }

  function renderGrid(items, filter) {
    const grid = document.getElementById("sqGrid");
    if (!grid) return;
    // When showing "all", cores already featured above — still list them first with warn badges
    const list = sortShop(items.filter((i) => matchFilter(i, filter)));
    if (!list.length) {
      grid.innerHTML = `<p class="sq-empty">No parts in this bay right now.</p>`;
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
      renderFeaturedCores(items);
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
