(() => {
  "use strict";

  /**
   * BuccaneerSalvage Store — List.js PLP
   * Search + category + price filter + sort + pagination (not all 67 at once).
   * Commerce-style facets; brand-dark gold cards; cores warn on-card.
   */
  const CATALOG_URL = "assets/square-catalog.json?v=20260815";
  const CORE_WARN = "FOR PARTS OR REBUILD · UNTESTED · NO RETURNS";
  const DEFAULT_PAGE = 12;

  let catalog = [];
  let list = null;
  let category = "all";
  let priceMin = null;
  let priceMax = null;
  let pageSize = DEFAULT_PAGE;
  let priceTimer = null;

  const money = (n) =>
    n == null || Number.isNaN(Number(n))
      ? ""
      : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  /** Parse "$50", "50", "1,299.99", "-10" → non-negative number or null. */
  function parseMoneyInput(raw) {
    if (raw == null) return null;
    let s = String(raw).trim();
    if (!s) return null;
    s = s.replace(/[$,\s]/g, "");
    // trailing + / junk: keep first numeric token
    const m = s.match(/^-?\d+(?:\.\d+)?/);
    if (!m) return null;
    const n = parseFloat(m[0]);
    if (!Number.isFinite(n)) return null;
    // Amounts are never negative for this catalog — clamp
    return Math.max(0, Math.abs(n));
  }

  /**
   * Detect amount-intent search queries so "$50" / "under 40" / "50-100"
   * filter by price instead of (broken) text substring match.
   * Bare digits alone stay text search (years, part #s).
   */
  function parseAmountQuery(q) {
    const s = String(q || "").trim().toLowerCase();
    if (!s) return null;
    let m;
    m = s.match(/^(?:under|below|max|upto|up\s*to|<=?)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$/i);
    if (m) return { min: null, max: parseMoneyInput(m[1]) };
    m = s.match(/^(?:over|above|min|from|>=?)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$/i);
    if (m) return { min: parseMoneyInput(m[1]), max: null };
    m = s.match(/^\$?\s*([\d,]+(?:\.\d+)?)\s*[-–—to]+\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$/i);
    if (m) {
      let a = parseMoneyInput(m[1]);
      let b = parseMoneyInput(m[2]);
      if (a != null && b != null && a > b) [a, b] = [b, a];
      return { min: a, max: b };
    }
    // Explicit currency: $50 or 50$
    m = s.match(/^\$\s*([\d,]+(?:\.\d+)?)\s*$/);
    if (m) {
      const n = parseMoneyInput(m[1]);
      if (n == null) return null;
      // tight band around exact price (± $1)
      return { min: Math.max(0, n - 1), max: n + 1, exactish: true };
    }
    m = s.match(/^([\d,]+(?:\.\d+)?)\s*\$\s*$/);
    if (m) {
      const n = parseMoneyInput(m[1]);
      if (n == null) return null;
      return { min: Math.max(0, n - 1), max: n + 1, exactish: true };
    }
    return null;
  }

  function readFacetPrices() {
    let min = parseMoneyInput(document.getElementById("stPriceMin")?.value);
    let max = parseMoneyInput(document.getElementById("stPriceMax")?.value);
    if (min != null && max != null && min > max) {
      [min, max] = [max, min];
    }
    priceMin = min;
    priceMax = max;
    const hint = document.getElementById("stPriceHint");
    if (hint) {
      if (min != null || max != null) {
        const lo = min != null ? money(min) : "any";
        const hi = max != null ? money(max) : "any";
        hint.textContent = `Price filter: ${lo} – ${hi}`;
      } else {
        hint.textContent =
          "Enter min and/or max (e.g. 20, $50, 100). Or search $50 / under 40.";
      }
    }
  }

  const isCore = (item) => item.category === "turbo" || item.category === "pump";

  const catLabel = (c) =>
    ({
      "air-spring": "Air spring",
      brake: "Brake hardware",
      filters: "Filter",
      ignition: "Ignition",
      driveline: "Driveline",
      turbo: "Turbo core",
      pump: "Pump core",
      vintage: "Vintage",
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

  /** Product images: self host + Square CDN / Square S3 only. */
  function safeImageUrl(u) {
    const s = String(u || "").trim();
    if (!/^https:\/\//i.test(s)) return "";
    try {
      const host = new URL(s).hostname.toLowerCase();
      if (
        host === "buccaneersalvage.github.io" ||
        host.endsWith(".squareup.com") ||
        host.endsWith(".squarecdn.com") ||
        host === "items-images-production.s3.us-west-2.amazonaws.com"
      ) {
        return s;
      }
    } catch (_) {}
    return "";
  }

  /** Prefer self-hosted 400² WebP thumbs; missing files fall back via data-fallback. */
  function cardImageUrl(item) {
    const id = String(item && item.id || "").trim();
    if (!/^[A-Z0-9]{16,32}$/.test(id)) return "";
    return `assets/product-thumbs/${id}.webp`;
  }

  function bindThumbFallbacks(root) {
    if (!root) return;
    root.querySelectorAll("img.st-img[data-fallback]").forEach((img) => {
      const fallback = () => {
        const next = img.getAttribute("data-fallback") || "";
        img.removeAttribute("data-fallback");
        if (next && next !== img.getAttribute("src")) img.src = next;
      };
      img.addEventListener("error", fallback);
      if (img.complete && img.naturalWidth === 0) fallback();
    });
  }

  function rankCat(c) {
    return {
      turbo: 0,
      pump: 1,
      "air-spring": 2,
      brake: 3,
      filters: 4,
      ignition: 5,
      driveline: 6,
      vintage: 7,
      other: 8,
    }[c] ?? 9;
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

  /** Model / PN aliases. Each token matches ANY alt (not AND). */
  const TOKEN_ALIASES = {
    f150: ["f-150", "f150", "f 150"],
    "f-150": ["f-150", "f150"],
    f250: ["f-250", "f250"],
    "f-250": ["f-250", "f250"],
    f350: ["f-350", "f350"],
    "f-350": ["f-350", "f350"],
    chevy: ["chevy", "chevrolet"],
    chevrolet: ["chevrolet", "chevy"],
    vw: ["vw", "volkswagen"],
    volkswagen: ["volkswagen", "vw"],
    benz: ["benz", "mercedes", "mercedes-benz"],
    mercedes: ["mercedes", "mercedes-benz", "benz"],
    "mercedes-benz": ["mercedes-benz", "mercedes", "benz"],
    gm: ["gm", "gmc", "chevrolet", "chevy"],
  };

  /** Skip eBay root crumbs so chips start at the department. */
  const EBAY_SKIP = new Set([
    "ebay motors",
    "parts & accessories",
    "car & truck parts & accessories",
    "commercial truck parts",
  ]);

  /** Map Type → same eBay department when GetItem left PrimaryCategory empty. */
  const TYPE_PARENT = [
    [/oil filter|crankcase|breather|timing (component|sprocket|belt)/i, "Engines & Engine Parts"],
    [/fuel filter|air filter/i, "Air & Fuel Delivery"],
    [/distributor|ignition|spark plug/i, "Ignition Systems & Components"],
    [/\bcv\b|boot kit|drivetrain/i, "Transmission & Drivetrain"],
    [/brake|caliper/i, "Brakes & Brake Parts"],
    [/air spring|rolling lobe|air ride/i, "Suspension & Steering"],
    [/turbo|injection pump|^pump$/i, "Cores"],
  ];

  let byId = new Map();
  let activeSub = "";
  let activeMake = "";

  function slugKey(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  }

  function compactToken(s) {
    return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  }

  function tokenAlts(tok) {
    const t = String(tok || "").toLowerCase();
    const alts = new Set([t, compactToken(t)]);
    const extra = TOKEN_ALIASES[t] || TOKEN_ALIASES[compactToken(t)] || [];
    extra.forEach((a) => {
      alts.add(a);
      alts.add(compactToken(a));
    });
    const brand = BRAND_ALIASES[t];
    if (brand) brand.split(/\s+/).forEach((a) => alts.add(a));
    return [...alts].filter(Boolean);
  }

  function yearHitsFitment(item, year) {
    const y = Number(year);
    if (!Number.isFinite(y)) return false;
    const vs = (item.fitment && Array.isArray(item.fitment.vehicles) && item.fitment.vehicles) || [];
    return vs.some((v) => {
      if (!v || typeof v !== "object") return false;
      if (v.year != null && Number(v.year) === y) return true;
      const a = v.year_from != null ? Number(v.year_from) : null;
      const b = v.year_to != null ? Number(v.year_to) : a;
      return a != null && Number.isFinite(a) && Number.isFinite(b) && y >= a && y <= b;
    });
  }

  function itemHitsQuery(item, raw) {
    const q = String(raw || "").trim().toLowerCase();
    if (!q) return true;
    const blob = item._blob || (item._blob = buildSearchBlob(item));
    const compactBlob = compactToken(blob);
    const tokens = q.split(/[^\p{L}\p{N}.]+/u).filter(Boolean);
    return tokens.every((tok) => {
      if (/^(?:19|20)\d{2}$/.test(tok) && yearHitsFitment(item, tok)) return true;
      return tokenAlts(tok).some((a) => blob.includes(a) || compactBlob.includes(compactToken(a)));
    });
  }

  function itemHitsMake(item, makeSlug) {
    if (!makeSlug) return true;
    const vs = (item.fitment && item.fitment.vehicles) || [];
    if (vs.some((v) => v && slugKey(v.make) === makeSlug)) return true;
    const labels = item.vehicles || [];
    return labels.some((lb) => slugKey(lb).includes(makeSlug) || compactToken(lb).includes(makeSlug.replace(/-/g, "")));
  }

  function itemHitsType(item, typeSlug) {
    if (!typeSlug) return true;
    return slugKey(item.ebay_type || (item.fitment && item.fitment.type) || "") === typeSlug;
  }

  function itemEbayTree(item) {
    if (!item) return { parent: "Other", parentSlug: "other", sub: "Other", subSlug: "other" };
    if (item._eb) return item._eb;
    const raw = (
      item.ebay_category ||
      (item.fitment && item.fitment.ebay_category) ||
      ""
    ).trim();
    const parts = raw
      ? raw.split(":").map((s) => s.trim()).filter(Boolean)
      : [];
    const kept = parts.filter((p) => !EBAY_SKIP.has(p.toLowerCase()));
    let parent = "";
    let sub = "";
    if (kept.length >= 2) {
      parent = kept[0];
      sub = kept[kept.length - 1];
    } else if (kept.length === 1) {
      parent = kept[0];
      sub = (item.ebay_type || (item.fitment && item.fitment.type) || "").trim() || kept[0];
    } else {
      const typ = (item.ebay_type || (item.fitment && item.fitment.type) || "").trim();
      parent = "Other";
      for (let i = 0; i < TYPE_PARENT.length; i++) {
        if (TYPE_PARENT[i][0].test(typ)) {
          parent = TYPE_PARENT[i][1];
          break;
        }
      }
      if (parent === "Other") {
        if (item.category === "turbo" || item.category === "pump") parent = "Cores";
        else if (item.category === "vintage") parent = "Vintage";
        else if (item.category && item.category !== "other") parent = catLabel(item.category);
      }
      sub = typ || parent;
    }
    item._eb = {
      parent,
      parentSlug: slugKey(parent) || "other",
      sub,
      subSlug: slugKey(sub) || "other",
    };
    return item._eb;
  }

  function itemHitsParent(item, parentSlug) {
    if (!parentSlug || parentSlug === "all") return true;
    return itemEbayTree(item).parentSlug === parentSlug;
  }

  function itemHitsSub(item, subSlug) {
    if (!subSlug) return true;
    const eb = itemEbayTree(item);
    if (eb.subSlug === subSlug) return true;
    return itemHitsType(item, subSlug);
  }

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
    push(item.ebay_type);
    push(item.ebay_brand);
    push(item.ebay_category);
    const eb = itemEbayTree(item);
    push(eb.parent);
    push(eb.sub);
    const pns = []
      .concat(item.part_numbers || [])
      .concat(item.interchange || []);
    pns.forEach((p) => {
      const c = compactToken(p);
      if (c.length >= 4) push(c);
    });

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

    // Price tokens so amount-ish text search can still hit (prefer $N query → price filter)
    if (item.price != null && Number.isFinite(Number(item.price))) {
      const p = Number(item.price);
      const whole = Math.floor(p);
      push(String(p));
      push(p.toFixed(2));
      push("$" + p.toFixed(2));
      push("$" + whole);
      push(String(whole));
      push("dollars usd price");
    }

    // Category synonyms for search
    if (item.category === "air-spring") {
      push("air spring airspring air bag airbag bag rolling lobe convoluted suspension");
    } else if (item.category === "brake") {
      push("brake brakes caliper pad drum hardware abutment pin kit");
    } else if (item.category === "filters") {
      push("filter filters air oil fuel transmission breather wix");
    } else if (item.category === "ignition") {
      push("ignition distributor cap coil spark plug wire vacuum advance");
    } else if (item.category === "driveline") {
      push("cv boot axle timing belt sprocket driveline");
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
    const href = `p/${encodeURIComponent(item.id)}.html`;
    // Prefer local thumb; else Square original. No inline onerror (CSP script-src 'self').
    const imgUrl = cardImageUrl(item);
    const fallback = safeImageUrl(item && item.image);
    const price = item.price != null ? Number(item.price) : "";
    const priceLabel = money(item.price);
    const imgAlt = (item.name || catLabel(item.category) || "Part").slice(0, 120);
    const img = imgUrl
      ? `<img class="st-img" src="${escapeAttr(imgUrl)}"${fallback ? ` data-fallback="${escapeAttr(fallback)}"` : ""} alt="${escapeAttr(imgAlt)}" width="400" height="400" loading="${featured ? "eager" : "lazy"}" decoding="async"${featured ? ' fetchpriority="high"' : ""} />`
      : fallback
      ? `<img class="st-img" src="${escapeAttr(fallback)}" alt="${escapeAttr(imgAlt)}" width="400" height="400" loading="${featured ? "eager" : "lazy"}" decoding="async"${featured ? ' fetchpriority="high"' : ""} />`
      : `<div class="st-card-ph" aria-hidden="true"></div>`;
    const ribbon = core ? `<span class="st-ribbon">FOR PARTS · NO RETURNS</span>` : "";
    const warn = core ? `<p class="st-warn">${escapeHtml(CORE_WARN)}</p>` : "";
    const cta = core ? "View details - for parts · no returns" : "View details";
    const tip = core
      ? "For parts or rebuild only. Untested. No returns. View product details."
      : "View product details";
    const searchblob = buildSearchBlob(item);
    const vehHint = Array.isArray(item.vehicles) ? item.vehicles.filter(Boolean).slice(0, 2) : [];
    const xrefHint = Array.isArray(item.interchange) ? item.interchange.filter(Boolean)[0] : "";
    const fitHint = vehHint.length
      ? "Fits " + vehHint.join(" · ")
      : xrefHint
        ? "Interchange " + String(xrefHint)
        : "";

    // List.js valueNames: .name .category .searchblob + data-price
    return `
      <article class="st-card${core ? " st-card--core" : ""}${featured ? " st-card--featured" : ""}"
               data-price="${escapeAttr(price)}"
               data-id="${escapeAttr(item.id || "")}"
               data-category="${escapeAttr(item.category || "other")}"
               data-rank="${rankCat(item.category)}">
        <a class="st-card-link" href="${escapeAttr(href)}" title="${escapeAttr(tip)}">
          <div class="st-card-media">${ribbon}${img}</div>
          <div class="st-card-body">
            <span class="st-card-cat category">${escapeHtml(item.ebay_type || catLabel(item.category))}</span>
            <h3 class="st-card-title name">${escapeHtml(item.name)}</h3>
            ${fitHint ? `<p class="st-card-fit">${escapeHtml(fitHint)}</p>` : ""}
            <span class="searchblob visually-hidden">${escapeHtml(searchblob)}</span>
            ${warn}
            <div class="st-card-foot">
              <p class="st-card-price">${priceLabel ? escapeHtml(priceLabel) : ""}</p>
              <span class="st-card-cta">${escapeHtml(cta)}</span>
            </div>
          </div>
        </a>
      </article>`;
  }

  function catalogCounts() {
    const counts = { all: catalog.length };
    catalog.forEach((i) => {
      const eb = itemEbayTree(i);
      const k = eb.parentSlug;
      if (!counts[k]) counts[k] = { label: eb.parent, n: 0 };
      counts[k].n++;
    });
    return counts;
  }

  function subCounts(parentSlug) {
    const counts = {};
    catalog.forEach((i) => {
      const eb = itemEbayTree(i);
      if (parentSlug && eb.parentSlug !== parentSlug) return;
      const k = eb.subSlug;
      if (!k) return;
      if (!counts[k]) counts[k] = { label: eb.sub, n: 0 };
      counts[k].n++;
    });
    return counts;
  }

  function makeCounts() {
    const counts = {};
    catalog.forEach((i) => {
      const seen = new Set();
      ((i.fitment && i.fitment.vehicles) || []).forEach((v) => {
        const make = (v && v.make) || "";
        const k = slugKey(make);
        if (!k || seen.has(k)) return;
        seen.add(k);
        if (!counts[k]) counts[k] = { label: make, n: 0 };
        counts[k].n++;
      });
    });
    return counts;
  }

  function chipHtml(filter, label, n, on) {
    const count = n != null ? ` <span class="st-chip-n" data-count="${escapeAttr(filter)}">${n}</span>` : "";
    return `<button type="button" class="st-chip${on ? " is-on" : ""}" data-filter="${escapeAttr(filter)}" aria-pressed="${on ? "true" : "false"}">${escapeHtml(label)}${count}</button>`;
  }

  function renderFacetChips() {
    const cats = catalogCounts();
    const catBox = document.getElementById("stCatChips");
    if (catBox) {
      const bits = [chipHtml("all", "All", cats.all, category === "all" && !activeSub && !activeMake)];
      Object.entries(cats)
        .filter(([k, v]) => k !== "all" && v && v.n)
        .sort((a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label))
        .forEach(([k, v]) => {
          bits.push(chipHtml("cat:" + k, v.label, v.n, category === k));
        });
      catBox.innerHTML = bits.join("");
    }

    const typeGroup = document.getElementById("stTypeGroup");
    const typeBox = document.getElementById("stTypeChips");
    if (typeGroup && typeBox) {
      const parentOn = category && category !== "all";
      const types = parentOn ? subCounts(category) : {};
      const typeList = Object.entries(types).sort(
        (a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label)
      );
      if (!parentOn || typeList.length < 2) {
        typeGroup.hidden = true;
        typeBox.innerHTML = "";
        if (typeList.length < 2) activeSub = "";
      } else {
        typeGroup.hidden = false;
        typeBox.innerHTML = typeList
          .map(([k, v]) => chipHtml("sub:" + k, v.label, v.n, activeSub === k))
          .join("");
      }
    }

    const makes = makeCounts();
    const makeList = Object.entries(makes)
      .filter(([, v]) => v.n >= 2)
      .sort((a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label))
      .slice(0, 14);
    const makeGroup = document.getElementById("stMakeGroup");
    const makeBox = document.getElementById("stMakeChips");
    if (makeGroup && makeBox) {
      if (!makeList.length) {
        makeGroup.hidden = true;
        makeBox.innerHTML = "";
      } else {
        makeGroup.hidden = false;
        makeBox.innerHTML = makeList
          .map(([k, v]) => chipHtml("make:" + k, v.label, v.n, activeMake === k))
          .join("");
      }
    }
  }

  function fillCounts() {
    renderFacetChips();
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
        ? "No matches. Try another search or clear filters"
        : `Showing ${from}–${to} of ${matching}`;
    if (meta) meta.textContent = text;
    if (showing) showing.textContent = text;
    updateEmptyState(matching);
  }

  /** In-grid empty state with clear-filters affordance when zero matches. */
  function updateEmptyState(matching) {
    const grid = document.getElementById("stGrid");
    if (!grid) return;
    let empty = document.getElementById("stEmptyState");
    if (matching > 0) {
      if (empty) empty.remove();
      return;
    }
    if (!empty) {
      empty = document.createElement("div");
      empty.id = "stEmptyState";
      empty.className = "st-empty st-empty--panel";
      empty.setAttribute("role", "status");
      empty.innerHTML =
        '<p class="st-empty-msg">No parts match that search or filter.</p>' +
        '<button type="button" class="btn btn-secondary" id="stEmptyClear">Clear filters</button>';
      grid.appendChild(empty);
      empty.querySelector("#stEmptyClear")?.addEventListener("click", () => {
        document.getElementById("stClearFilters")?.click();
      });
    }
  }

  /**
   * Unified search + category + price (facets and/or amount-query).
   * Fixes List.js fight: search alone wiped mental model of min/max;
   * "$50" used to fail because $ is regex-escaped and price wasn't indexed.
   */
  function applyFilters() {
    if (!list) return;
    const rawQ = document.getElementById("stSearch")?.value || "";
    const amountQ = parseAmountQuery(rawQ);

    let min = priceMin;
    let max = priceMax;
    let textQ = rawQ.trim();

    if (amountQ) {
      // Amount-intent query → price bounds (stack tighter with facets)
      if (amountQ.min != null) {
        min = min == null ? amountQ.min : Math.max(min, amountQ.min);
      }
      if (amountQ.max != null) {
        max = max == null ? amountQ.max : Math.min(max, amountQ.max);
      }
      if (min != null && max != null && min > max) [min, max] = [max, min];
      textQ = ""; // don't also substring-search "$50"
      const hint = document.getElementById("stPriceHint");
      if (hint) {
        const lo = min != null ? money(min) : "any";
        const hi = max != null ? money(max) : "any";
        hint.textContent = `Search amount → ${lo} – ${hi}`;
      }
    }

    // Do not use List.js search() — hyphenated PNs are treated as regex (W01-358-8091).
    list.search("");

    list.filter((item) => {
      const el = item.elm;
      if (!el) return false;
      const rec = byId.get(el.getAttribute("data-id") || "") || null;
      if (category !== "all") {
        if (!rec || !itemHitsParent(rec, category)) return false;
      }
      if (activeSub) {
        if (!rec || !itemHitsSub(rec, activeSub)) return false;
      }
      if (activeMake) {
        if (!rec || !itemHitsMake(rec, activeMake)) return false;
      }
      if (textQ && rec && !itemHitsQuery(rec, textQ)) return false;
      if (textQ && !rec) return false;
      const p = parseFloat(el.getAttribute("data-price"));
      const hasPrice = Number.isFinite(p);
      if (min != null) {
        if (!hasPrice || p < min) return false;
      }
      if (max != null) {
        if (!hasPrice || p > max) return false;
      }
      return true;
    });
    updateShowing();
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
    const eagerN = window.matchMedia("(min-width: 900px)").matches
      ? 8
      : window.matchMedia("(min-width: 560px)").matches
        ? 4
        : 2;
    grid.innerHTML = ordered.map((i, idx) => cardHtml(i, { featured: idx < eagerN })).join("");
    bindThumbFallbacks(grid);

    // List.js: { data: ['price'] } reads data-price on the item root.
    // ({ name, attr } reads attr from a *child* with class=name — easy footgun.)
    list = new List("storeList", {
      valueNames: [
        "name",
        "category",
        "searchblob",
        { data: ["price", "rank"] },
      ],
      searchColumns: ["name", "category", "searchblob"],
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
    const searchEl = document.getElementById("stSearch");
    if (searchEl) searchEl.value = searchVal;
    readFacetPrices();
    applyFilters();
    applySort(sortMode);
  }

  function wireControls() {
    document.getElementById("stFacets")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".st-chip[data-filter]");
      if (!btn || !document.getElementById("stFacets").contains(btn)) return;
      const raw = btn.getAttribute("data-filter") || "all";
      if (raw.startsWith("cat:")) {
        category = raw.slice(4);
        activeSub = "";
      } else if (raw.startsWith("sub:")) {
        const next = raw.slice(4);
        activeSub = activeSub === next ? "" : next;
      } else if (raw.startsWith("make:")) {
        const next = raw.slice(5);
        activeMake = activeMake === next ? "" : next;
      } else if (raw.startsWith("type:")) {
        const next = raw.slice(5);
        activeSub = activeSub === next ? "" : next;
      } else {
        category = raw === "all" ? "all" : raw;
        activeSub = "";
        if (raw === "all") activeMake = "";
      }
      renderFacetChips();
      applyFilters();
      document.getElementById("catalog")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    const applyPriceFacets = () => {
      readFacetPrices();
      applyFilters();
    };

    document.getElementById("stPriceApply")?.addEventListener("click", applyPriceFacets);

    // Live min/max (debounced) + Enter — type "$50" or "20" in either box
    ["stPriceMin", "stPriceMax"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener("input", () => {
        clearTimeout(priceTimer);
        priceTimer = setTimeout(applyPriceFacets, 220);
      });
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          clearTimeout(priceTimer);
          applyPriceFacets();
        }
      });
      el.addEventListener("blur", applyPriceFacets);
    });

    document.getElementById("stClearFilters")?.addEventListener("click", () => {
      category = "all";
      activeSub = "";
      activeMake = "";
      priceMin = null;
      priceMax = null;
      renderFacetChips();
      const minEl = document.getElementById("stPriceMin");
      const maxEl = document.getElementById("stPriceMax");
      if (minEl) minEl.value = "";
      if (maxEl) maxEl.value = "";
      const search = document.getElementById("stSearch");
      if (search) search.value = "";
      const hint = document.getElementById("stPriceHint");
      if (hint) {
        hint.textContent =
          "Enter min and/or max (e.g. 20, $50, 100). Or search $50 / under 40.";
      }
      if (list) {
        list.search("");
        list.filter(); // clear filter flags
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

    // Drive search through applyFilters so price facets + amount queries stack
    // (List.js also binds .search keyup — our path re-applies category/price after)
    document.getElementById("stSearch")?.addEventListener("input", () => {
      if (!list) return;
      applyFilters();
    });
    document.getElementById("stSearch")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applyFilters();
      }
    });
  }

  async function boot() {
    const countEl = document.getElementById("stCount");
    try {
      const res = await fetch(CATALOG_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`catalog ${res.status}`);
      const data = await res.json();
      catalog = Array.isArray(data.items) ? data.items : [];
      byId = new Map(catalog.map((i) => [String(i.id || ""), i]));
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
