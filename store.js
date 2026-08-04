(() => {
  "use strict";

  const CATALOG_URL = "assets/square-catalog.json";
  const CORE_WARN = "FOR PARTS OR REBUILD · UNTESTED · NO RETURNS";

  let allItems = [];
  let filter = "all";
  let sort = "featured";
  let query = "";

  const money = (n) =>
    n == null || Number.isNaN(Number(n))
      ? ""
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
        }).format(n);

  const isCore = (item) => item.category === "turbo" || item.category === "pump";

  const catLabel = (c) =>
    ({
      "air-spring": "Air spring",
      brake: "Brake hardware",
      turbo: "Turbo core",
      pump: "Pump core",
      other: "Parts",
    }[c] || "Parts");

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

  function rankCat(c) {
    return { turbo: 0, pump: 1, "air-spring": 2, brake: 3, other: 4 }[c] ?? 9;
  }

  function matchFilter(item) {
    if (filter === "all") return true;
    if (filter === "cores") return isCore(item);
    return item.category === filter;
  }

  function matchQuery(item) {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      (item.name || "").toLowerCase().includes(q) ||
      (item.id || "").toLowerCase().includes(q) ||
      (item.category || "").toLowerCase().includes(q)
    );
  }

  function sortItems(list) {
    const arr = list.slice();
    if (sort === "price-asc") {
      arr.sort((a, b) => (a.price ?? 1e12) - (b.price ?? 1e12));
    } else if (sort === "price-desc") {
      arr.sort((a, b) => (b.price ?? 0) - (a.price ?? 0));
    } else if (sort === "name") {
      arr.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    } else {
      arr.sort(
        (a, b) =>
          rankCat(a.category) - rankCat(b.category) ||
          (a.name || "").localeCompare(b.name || "")
      );
    }
    return arr;
  }

  function cardHtml(item, { featured = false } = {}) {
    const core = isCore(item);
    const href = item.url || "#";
    const price = money(item.price);
    const img = item.image
      ? `<img src="${escapeAttr(item.image)}" alt="" width="400" height="300" loading="${featured ? "eager" : "lazy"}" decoding="async" />`
      : `<div class="st-card-ph" aria-hidden="true">—</div>`;
    const ribbon = core
      ? `<span class="st-ribbon">FOR PARTS · NO RETURNS</span>`
      : "";
    const warn = core
      ? `<p class="st-warn">${escapeHtml(CORE_WARN)}</p>`
      : "";
    const cta = core
      ? "Checkout — for parts · no returns"
      : "Buy · secure checkout";
    const titleTip = core
      ? "For parts or rebuild only. Untested. No returns. Opens secure checkout."
      : "Opens secure checkout";

    return `
      <article class="st-card${core ? " st-card--core" : ""}${featured ? " st-card--featured" : ""}">
        <a class="st-card-link" href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer" title="${escapeAttr(titleTip)}">
          <div class="st-card-media">${ribbon}${img}</div>
          <div class="st-card-body">
            <span class="st-card-cat">${escapeHtml(catLabel(item.category))}</span>
            <h3 class="st-card-title">${escapeHtml(item.name)}</h3>
            ${warn}
            <div class="st-card-foot">
              ${price ? `<p class="st-card-price">${escapeHtml(price)}</p>` : "<p class=\"st-card-price\">—</p>"}
              <span class="st-card-cta">${escapeHtml(cta)}</span>
            </div>
          </div>
        </a>
      </article>`;
  }

  function renderFeatured() {
    const host = document.getElementById("stFeaturedCores");
    if (!host) return;
    const cores = sortItems(allItems.filter(isCore));
    if (!cores.length) {
      host.closest(".st-featured")?.setAttribute("hidden", "");
      return;
    }
    host.innerHTML = cores.map((i) => cardHtml(i, { featured: true })).join("");
  }

  function renderGrid() {
    const grid = document.getElementById("stGrid");
    const meta = document.getElementById("stResultMeta");
    if (!grid) return;

    const list = sortItems(allItems.filter((i) => matchFilter(i) && matchQuery(i)));
    if (meta) {
      meta.textContent =
        list.length === 1 ? "1 result" : `${list.length} results`;
    }
    if (!list.length) {
      grid.innerHTML = `<p class="st-empty">No parts match. Clear search or pick another category.</p>`;
      return;
    }
    grid.innerHTML = list.map((i) => cardHtml(i)).join("");
  }

  function wireControls() {
    document.querySelectorAll(".st-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        filter = btn.getAttribute("data-filter") || "all";
        document.querySelectorAll(".st-chip").forEach((b) => {
          const on = b === btn;
          b.classList.toggle("is-on", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        renderGrid();
      });
    });

    const search = document.getElementById("stSearch");
    if (search) {
      let t;
      search.addEventListener("input", () => {
        clearTimeout(t);
        t = setTimeout(() => {
          query = search.value.trim();
          renderGrid();
        }, 120);
      });
    }

    const sortEl = document.getElementById("stSort");
    if (sortEl) {
      sortEl.addEventListener("change", () => {
        sort = sortEl.value || "featured";
        renderGrid();
      });
    }
  }

  async function boot() {
    const countEl = document.getElementById("stCount");
    try {
      const res = await fetch(CATALOG_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`catalog ${res.status}`);
      const data = await res.json();
      allItems = Array.isArray(data.items) ? data.items : [];
      if (countEl) {
        countEl.textContent = `${allItems.length} listings`;
      }
      renderFeatured();
      renderGrid();
      wireControls();
    } catch (err) {
      if (countEl) countEl.textContent = "Catalog offline";
      const grid = document.getElementById("stGrid");
      if (grid) {
        grid.innerHTML = `<p class="st-empty">Could not load the catalog. Refresh the page.</p>`;
      }
      console.warn("[store]", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
