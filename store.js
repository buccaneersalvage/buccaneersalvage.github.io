(() => {
  "use strict";

  /**
   * BuccaneerSalvage Store — List.js PLP
   * Search + category + price filter + sort + pagination (not all 67 at once).
   * Commerce-style facets; brand-dark gold cards; cores warn on-card.
   */
  const CATALOG_URL = "assets/square-catalog.json?v=20260804w";
  const CORE_WARN = "FOR PARTS OR REBUILD · UNTESTED · NO RETURNS";
  const DEFAULT_PAGE = 12;

  let catalog = [];
  let list = null;
  let category = "all";
  let priceMin = null;
  let priceMax = null;
  let pageSize = DEFAULT_PAGE;

  const money = (n) =>
    n == null || Number.isNaN(Number(n))
      ? ""
      : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

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

  function safeUrl(u) {
    const s = String(u || "").trim();
    return /^https?:\/\//i.test(s) ? s : "#";
  }

  function rankCat(c) {
    return { turbo: 0, pump: 1, "air-spring": 2, brake: 3, other: 4 }[c] ?? 9;
  }

  /** Brand / manufacturer aliases so "chevy", "contitech", "benz" hit listings. */
  const BRAND_ALIASES = {
    chevrolet: "chevy chevrolet gm general motors",
    chevy: "chevy chevrolet",
    ford: "ford motor",
    dodge: "dodge ram",
    ram: "ram dodge",
    gmc: "gmc general motors",
    mercedes: "mercedes mercedes-benz benz",
    "mercedes-benz": "mercedes mercedes-benz benz",
    contitech: "contitech continental conti",
    continental: "continental contitech conti",
    goodyear: "goodyear",
    automann: "automann",
    carlson: "carlson",
    firestone: "firestone",
    holset: "holset cummins",
    mack: "mack truck",
    wagner: "wagner",
    econoride: "econoride",
    toyota: "toyota",
    lexus: "lexus",
    jeep: "jeep",
    chrysler: "chrysler",
    buick: "buick",
    cadillac: "cadillac",
    kia: "kia",
    nissan: "nissan",
    infiniti: "infiniti infinity",
    mazda: "mazda",
    subaru: "subaru",
    volkswagen: "volkswagen vw",
    fiat: "fiat",
    saturn: "saturn",
    oldsmobile: "oldsmobile olds",
    pontiac: "pontiac",
    isuzu: "isuzu",
    freightliner: "freightliner",
  };

  /** Expand "2000–2011" so year queries like 2005 match (List.js is substring). */
  function expandYearRange(from, to, cap = 45) {
    const a = Number(from);
    const b = Number(to);
    if (!Number.isFinite(a) || !Number.isFinite(b) || a > b) return [];
    if (b - a > cap) return [String(a), String(b)]; // huge ranges: endpoints only
    const out = [];
    for (let y = a; y <= b; y++) out.push(String(y));
    return out;
  }

  function yearsFromLabel(label) {
    const s = String(label || "");
    // 2000–2011 or 2000-2011
    let m = s.match(/\b((?:19|20)\d{2})\s*[–—-]\s*((?:19|20)\d{2})\b/);
    if (m) return expandYearRange(m[1], m[2]);
    m = s.match(/\b((?:19|20)\d{2})\b/);
    return m ? [m[1]] : [];
  }

  /**
   * Rich List.js search index: title, brand, MPN, interchange, vehicles,
   * year/make/model (with year-range expansion + brand aliases).
   */
  function buildSearchBlob(item) {
    const parts = [];
    const push = (v) => {
      if (v == null || v === "") return;
      if (Array.isArray(v)) {
        v.forEach(push);
        return;
      }
      if (typeof v === "object") return;
      parts.push(String(v));
    };

    push(item.name);
    push(item.category);
    push(catLabel(item.category));
    push(item.id);
    push(item.ebay_item_id);
    push(item.part_numbers);
    push(item.interchange);

    // Title brand / first tokens (OEM Goodyear …)
    const name = String(item.name || "");
    const brandTok = name.match(
      /^(?:OEM\s+)?(Carlson|Automann|Goodyear|Continental|ContiTech|Firestone|Holset|Mack|Wagner|Econoride|Mercedes(?:-Benz)?|Meritor)\b/i
    );
    if (brandTok) {
      push(brandTok[1]);
      push("brand manufacturer maker");
      const key = brandTok[1].toLowerCase();
      if (BRAND_ALIASES[key]) push(BRAND_ALIASES[key]);
    }

    // Vehicle labels: "2000–2011 Dodge Dakota"
    const vehLabels = Array.isArray(item.vehicles) ? item.vehicles : [];
    vehLabels.forEach((label) => {
      push(label);
      push(yearsFromLabel(label));
      // common make/model words already in label; add aliases
      const low = String(label).toLowerCase();
      Object.keys(BRAND_ALIASES).forEach((k) => {
        if (low.includes(k)) push(BRAND_ALIASES[k]);
      });
    });

    // Structured fitment.vehicles
    const fit = item.fitment && typeof item.fitment === "object" ? item.fitment : null;
    const fitVeh = fit && Array.isArray(fit.vehicles) ? fit.vehicles : [];
    fitVeh.forEach((v) => {
      if (!v || typeof v !== "object") return;
      push(v.make);
      push(v.model);
      push(v.trim);
      push(v.engine);
      push(v.notes);
      if (v.year_from != null || v.year_to != null) {
        const y0 = v.year_from != null ? v.year_from : v.year_to;
        const y1 = v.year_to != null ? v.year_to : v.year_from;
        push(expandYearRange(y0, y1));
        push(String(y0), String(y1));
      } else if (v.year != null) {
        push(String(v.year));
      }
      if (v.make) {
        const mk = String(v.make).toLowerCase();
        if (BRAND_ALIASES[mk]) push(BRAND_ALIASES[mk]);
        // multi-word makes: "Mercedes-Benz"
        Object.keys(BRAND_ALIASES).forEach((k) => {
          if (mk.includes(k)) push(BRAND_ALIASES[k]);
        });
      }
    });
    if (fit) {
      push(fit.part_numbers);
      push(fit.interchange);
      push(fit.vehicle_labels);
    }

    if (isCore(item)) {
      push("for parts rebuild untested no returns core turbo pump");
    }

    // Category synonyms for search
    if (item.category === "air-spring") {
      push("air spring airspring air bag airbag bag rolling lobe convoluted suspension");
    } else if (item.category === "brake") {
      push("brake brakes caliper pad drum hardware abutment pin kit");
    }

    // Dedupe tokens (preserve order), lowercase for List.js
    const seen = new Set();
    const out = [];
    parts
      .join(" ")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}.\-–—/&+]+/gu, " ")
      .split(/\s+/)
      .forEach((t) => {
        if (!t || seen.has(t)) return;
        seen.add(t);
        out.push(t);
      });
    return out.join(" ");
  }

  function cardHtml(item, { featured = false } = {}) {
    const core = isCore(item);
    const href = `item.html?id=${encodeURIComponent(item.id)}`;
    const imgUrl = safeUrl(item.image);
    const price = item.price != null ? Number(item.price) : "";
    const priceLabel = money(item.price);
    const img = imgUrl !== "#"
      ? `<img class="st-img" src="${escapeAttr(imgUrl)}" alt="" width="400" height="400" loading="${featured ? "eager" : "lazy"}" decoding="async" />`
      : `<div class="st-card-ph" aria-hidden="true">—</div>`;
    const ribbon = core ? `<span class="st-ribbon">FOR PARTS · NO RETURNS</span>` : "";
    const warn = core ? `<p class="st-warn">${escapeHtml(CORE_WARN)}</p>` : "";
    const cta = core ? "View details — for parts · no returns" : "View details";
    const tip = core
      ? "For parts or rebuild only. Untested. No returns. View product details."
      : "View product details";
    const searchblob = buildSearchBlob(item);

    // List.js valueNames: .name .category .searchblob + data-price
    return `
      <article class="st-card${core ? " st-card--core" : ""}${featured ? " st-card--featured" : ""}"
               data-price="${escapeAttr(price)}"
               data-category="${escapeAttr(item.category || "other")}"
               data-rank="${rankCat(item.category)}">
        <a class="st-card-link" href="${escapeAttr(href)}" title="${escapeAttr(tip)}">
          <div class="st-card-media">${ribbon}${img}</div>
          <div class="st-card-body">
            <span class="st-card-cat category">${escapeHtml(catLabel(item.category))}</span>
            <h3 class="st-card-title name">${escapeHtml(item.name)}</h3>
            <span class="searchblob visually-hidden">${escapeHtml(searchblob)}</span>
            ${warn}
            <div class="st-card-foot">
              <p class="st-card-price">${priceLabel ? escapeHtml(priceLabel) : "—"}</p>
              <span class="st-card-cta">${escapeHtml(cta)}</span>
            </div>
          </div>
        </a>
      </article>`;
  }

  function fillCounts() {
    const counts = { "air-spring": 0, brake: 0, cores: 0, other: 0, all: catalog.length };
    catalog.forEach((i) => {
      if (isCore(i)) counts.cores++;
      else if (counts[i.category] != null) counts[i.category]++;
      else counts.other++;
    });
    document.querySelectorAll("[data-count]").forEach((el) => {
      const k = el.getAttribute("data-count");
      el.textContent = String(counts[k] ?? 0);
    });
  }

  function updateShowing() {
    const meta = document.getElementById("stResultMeta");
    const showing = document.getElementById("stShowing");
    if (!list) return;
    const matching = list.matchingItems.length;
    // list.i / list.page can be strings (List.js reads data attrs) — coerce before math
    const i = Number(list.i) || 1; // 1-based start index of page
    const page = Number(list.page) || pageSize;
    const from = matching === 0 ? 0 : i;
    const to = Math.min(i + page - 1, matching);
    const text =
      matching === 0
        ? "No matches — try another search or clear filters"
        : `Showing ${from}–${to} of ${matching}`;
    if (meta) meta.textContent = text;
    if (showing) showing.textContent = text;
  }

  function applyFilters() {
    if (!list) return;
    list.filter((item) => {
      const el = item.elm;
      const cat = el.getAttribute("data-category") || "other";
      const core = cat === "turbo" || cat === "pump";
      // category
      if (category === "cores") {
        if (!core) return false;
      } else if (category !== "all" && cat !== category) {
        return false;
      }
      // price
      const p = parseFloat(el.getAttribute("data-price"));
      if (priceMin != null && !Number.isNaN(p) && p < priceMin) return false;
      if (priceMax != null && !Number.isNaN(p) && p > priceMax) return false;
      return true;
    });
    list.update();
    updateShowing();
    // scroll catalog into view gently on filter change (not on first paint)
  }

  // List.js multiplies sortFunction result by order (±1) — return ASC comparison only.
  function numSort(key, order) {
    list.sort(key, {
      order: order === "desc" ? "desc" : "asc",
      sortFunction(a, b) {
        const av = parseFloat(a.values()[key]);
        const bv = parseFloat(b.values()[key]);
        const an = Number.isFinite(av) ? av : 0;
        const bn = Number.isFinite(bv) ? bv : 0;
        if (an === bn) {
          const na = (a.values().name || "").toString();
          const nb = (b.values().name || "").toString();
          return na.localeCompare(nb);
        }
        return an < bn ? -1 : 1;
      },
    });
  }

  function applySort(mode) {
    if (!list) return;
    if (mode === "price-asc") {
      numSort("price", "asc");
    } else if (mode === "price-desc") {
      numSort("price", "desc");
    } else if (mode === "name-asc") {
      list.sort("name", { order: "asc" });
    } else if (mode === "name-desc") {
      list.sort("name", { order: "desc" });
    } else {
      // Featured: category rank (cores first) then name
      numSort("rank", "asc");
    }
    updateShowing();
  }

  function initList() {
    if (typeof List === "undefined") {
      console.error("[store] List.js not loaded");
      return;
    }
    const grid = document.getElementById("stGrid");
    if (!grid) return;

    // Sort catalog for initial DOM order (featured)
    const ordered = catalog.slice().sort(
      (a, b) =>
        rankCat(a.category) - rankCat(b.category) ||
        (a.name || "").localeCompare(b.name || "")
    );
    grid.innerHTML = ordered.map((i) => cardHtml(i)).join("");

    // List.js: { data: ['price'] } reads data-price on the item root.
    // ({ name, attr } reads attr from a *child* with class=name — easy footgun.)
    list = new List("storeList", {
      valueNames: [
        "name",
        "category",
        "searchblob",
        { data: ["price", "rank"] },
      ],
      page: pageSize,
      pagination: {
        innerWindow: 1,
        outerWindow: 1,
        left: 1,
        right: 1,
        paginationClass: "pagination",
        item: "<li><button type='button' class='page'></button></li>",
      },
    });

    list.on("updated", updateShowing);
    list.on("searchComplete", updateShowing);
    list.on("filterComplete", updateShowing);

    applySort("featured");
    updateShowing();
  }

  function reinitWithPageSize(n) {
    pageSize = n;
    const searchVal = document.getElementById("stSearch")?.value || "";
    const sortMode = document.getElementById("stSort")?.value || "featured";
    // Full rebuild keeps List.js page size + pagination in sync
    initList();
    if (searchVal && list) {
      list.search(searchVal);
      const searchEl = document.getElementById("stSearch");
      if (searchEl) searchEl.value = searchVal;
    }
    applyFilters();
    applySort(sortMode);
  }

  function wireControls() {
    document.querySelectorAll(".st-chip[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        category = btn.getAttribute("data-filter") || "all";
        document.querySelectorAll(".st-chip[data-filter]").forEach((b) => {
          const on = b === btn;
          b.classList.toggle("is-on", on);
          b.setAttribute("aria-pressed", on ? "true" : "false");
        });
        applyFilters();
        document.getElementById("catalog")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    document.getElementById("stPriceApply")?.addEventListener("click", () => {
      const minV = document.getElementById("stPriceMin")?.value;
      const maxV = document.getElementById("stPriceMax")?.value;
      priceMin = minV === "" || minV == null ? null : parseFloat(minV);
      priceMax = maxV === "" || maxV == null ? null : parseFloat(maxV);
      if (Number.isNaN(priceMin)) priceMin = null;
      if (Number.isNaN(priceMax)) priceMax = null;
      applyFilters();
    });

    document.getElementById("stClearFilters")?.addEventListener("click", () => {
      category = "all";
      priceMin = null;
      priceMax = null;
      document.querySelectorAll(".st-chip[data-filter]").forEach((b) => {
        const on = b.getAttribute("data-filter") === "all";
        b.classList.toggle("is-on", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      const minEl = document.getElementById("stPriceMin");
      const maxEl = document.getElementById("stPriceMax");
      if (minEl) minEl.value = "";
      if (maxEl) maxEl.value = "";
      const search = document.getElementById("stSearch");
      if (search) search.value = "";
      if (list) {
        list.search();
        list.filter();
      }
      applyFilters();
      applySort(document.getElementById("stSort")?.value || "featured");
    });

    document.getElementById("stSort")?.addEventListener("change", (e) => {
      applySort(e.target.value || "featured");
    });

    document.getElementById("stPageSize")?.addEventListener("change", (e) => {
      const n = parseInt(e.target.value, 10) || DEFAULT_PAGE;
      reinitWithPageSize(n);
    });

    // List.js binds .search on keyup; also drive search on input (paste / clear / IME)
    document.getElementById("stSearch")?.addEventListener("input", (e) => {
      if (!list) return;
      list.search(e.target.value || "");
      updateShowing();
    });
  }

  async function boot() {
    const countEl = document.getElementById("stCount");
    try {
      const res = await fetch(CATALOG_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`catalog ${res.status}`);
      const data = await res.json();
      catalog = Array.isArray(data.items) ? data.items : [];
      if (countEl) countEl.textContent = `${catalog.length} listings`;
      fillCounts();
      initList();
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
