(() => {
  "use strict";

  /**
   * BuccaneerSalvage Store — List.js PLP
   * Search + category + price filter + sort + pagination (not all 67 at once).
   * Commerce-style facets; brand-dark gold cards; cores warn on-card.
   */
  const CATALOG_URL = "assets/square-catalog.json?v=202608180030";
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
        hint.textContent = `Price filter: ${lo} - ${hi}`;
      } else {
        hint.textContent =
          "Min, max, or search under 40.";
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
      mobility: "Mobility",
      cycling: "Cycling",
      "material-handling": "Material Handling",
      "electric-motors": "Electric Motors",
      interior: "Interior",
      exhaust: "Exhaust",
      engines: "Engines",
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
      engines: 6,
      interior: 7,
      exhaust: 7,
      mobility: 8,
      cycling: 8,
      "material-handling": 8,
      "electric-motors": 8,
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

  /** Map Type / title → eBay department. Wins over a wrong PrimaryCategory. */
  const TYPE_PARENT = [
    [/oil filter|crankcase|breather|timing|sprocket|air injection/i, "Engines & Engine Parts"],
    [/fuel filter|air filter/i, "Air & Fuel Delivery"],
    [/distributor|ignition|spark plug|vacuum advance|pickup coil|\bhei\b/i, "Ignition Systems & Components"],
    [/\bcv\b|boot kit|drivetrain/i, "Transmission & Drivetrain"],
    [/brake|caliper/i, "Brakes & Brake Parts"],
    [/air spring|rolling lobe|air ride|convoluted/i, "Suspension & Steering"],
    [/turbo|injection pump|^pump$/i, "Cores"],
    [/exhaust|flange gasket/i, "Exhaust & Emission Systems"],
    [/headlight switch|dimmer/i, "Interior Parts & Accessories"],
    [/wheelchair/i, "Mobility"],
    [/\bbicycle\b|\bbike\b|\bmasi\b/i, "Cycling"],
    [/forklift/i, "Material Handling"],
    [/capacitor motor|\bcraftsman\b.*\bmotor\b/i, "Electric Motors"],
  ];

  /** Non-vehicle store departments. Stay out of make/model/year parts search. */
  const YARD_PARENTS = new Set([
    "mobility",
    "cycling",
    "material-handling",
    "electric-motors",
  ]);

  const PARENT_SHORT = {
    "suspension-steering": "Suspension",
    "brakes-brake-parts": "Brakes",
    "ignition-systems-components": "Ignition",
    "air-fuel-delivery": "Air & Fuel",
    "engines-engine-parts": "Engines",
    "transmission-drivetrain": "Drivetrain",
    "other-car-truck-parts-accessories": "Other parts",
    "interior-parts-accessories": "Interior",
    "air-conditioning-heating": "HVAC",
    "exhaust-emission-systems": "Exhaust",
    cores: "Cores",
    mobility: "Mobility",
    cycling: "Cycling",
    "material-handling": "Material Handling",
    "electric-motors": "Electric Motors",
  };

  const SUB_CANON = {
    "oil-filters": "oil-filter",
    "fuel-filters": "fuel-filter",
    "air-filters": "air-filter",
    "distributor-caps": "distributor-cap",
    "ignition-coils": "ignition-coil",
    "brake-pads": "brake-pad",
    "transmission-filters": "transmission-filter",
    "exhaust-gaskets": "exhaust-gasket",
    "wheelchairs": "wheelchair",
    "bicycles": "bicycle",
  };

  const SUB_LABEL = {
    "oil-filter": "Oil Filter",
    "fuel-filter": "Fuel Filter",
    "air-filter": "Air Filter",
    "distributor-cap": "Distributor Cap",
    "ignition-coil": "Ignition Coil",
    "brake-pad": "Brake Pad",
    "transmission-filter": "Transmission Filter",
    "exhaust-gasket": "Exhaust Gasket",
    wheelchair: "Wheelchair",
    bicycle: "Bicycle",
  };

  function canonSubSlug(s) {
    const k = slugKey(s);
    return SUB_CANON[k] || k;
  }

  function parentChipLabel(slug, fallback) {
    return PARENT_SHORT[slug] || fallback || slug;
  }

  function displayHyphen(s) {
    return String(s || "").replace(/[–—]/g, "-");
  }

  let byId = new Map();
  let activeSub = "";
  let activeMake = "";
  let activeModel = "";
  let activeYear = "";

  function slugKey(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  }

  function compactToken(s) {
    return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  }

  function ownValue(map, key) {
    if (!key || !Object.prototype.hasOwnProperty.call(map, key)) return undefined;
    return map[key];
  }

  function tokenAlts(tok) {
    const t = String(tok || "").toLowerCase();
    const alts = new Set([t, compactToken(t)]);
    const extra = ownValue(TOKEN_ALIASES, t) || ownValue(TOKEN_ALIASES, compactToken(t)) || [];
    if (Array.isArray(extra)) {
      extra.forEach((a) => {
        alts.add(a);
        alts.add(compactToken(a));
      });
    }
    const brand = ownValue(BRAND_ALIASES, t);
    if (typeof brand === "string") brand.split(/\s+/).forEach((a) => alts.add(a));
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

  function isNonVehicleDept(item) {
    return YARD_PARENTS.has(itemEbayTree(item).parentSlug);
  }

  function itemHitsQuery(item, raw) {
    const q = String(raw || "").trim().toLowerCase();
    if (!q) return true;
    const blob = item._blob || (item._blob = buildSearchBlob(item));
    const compactBlob = compactToken(blob);
    const tokens = q.split(/[^\p{L}\p{N}.]+/u).filter(Boolean);
    if (
      isNonVehicleDept(item) &&
      tokens.length &&
      tokens.every((tok) => /^(?:19|20)\d{2}$/.test(tok))
    ) {
      return false;
    }
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

  function itemHitsModel(item, makeSlug, modelSlug) {
    if (!modelSlug) return true;
    const vs = (item.fitment && item.fitment.vehicles) || [];
    if (
      vs.some(
        (v) => v && slugKey(v.make) === makeSlug && slugKey(v.model) === modelSlug
      )
    ) {
      return true;
    }
    const want = compactToken(modelSlug);
    return (item.vehicles || []).some((lb) => {
      const low = slugKey(lb);
      if (makeSlug && !low.includes(makeSlug) && !compactToken(lb).includes(makeSlug.replace(/-/g, ""))) {
        return false;
      }
      return low.includes(modelSlug) || compactToken(lb).includes(want);
    });
  }

  function itemHitsType(item, typeSlug) {
    if (!typeSlug) return true;
    const want = canonSubSlug(typeSlug);
    const have = canonSubSlug(item.ebay_type || (item.fitment && item.fitment.type) || "");
    return have === want;
  }

  function typeParentName(typ, name) {
    const tryOn = [typ || "", name || ""];
    for (let t = 0; t < tryOn.length; t++) {
      const s = tryOn[t];
      if (!s) continue;
      for (let i = 0; i < TYPE_PARENT.length; i++) {
        if (TYPE_PARENT[i][0].test(s)) return TYPE_PARENT[i][1];
      }
    }
    return "";
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
    const typ = (item.ebay_type || (item.fitment && item.fitment.type) || "").trim();
    let parent = "";
    let sub = "";
    if (kept.length >= 2) {
      parent = kept[0];
      sub = kept[kept.length - 1];
    } else if (kept.length === 1) {
      parent = kept[0];
      sub = typ || kept[0];
    }
    const typed = typeParentName(typ, item.name || "");
    if (typed && slugKey(parent) !== slugKey(typed)) {
      parent = typed;
      if (typ && !/^vintage$/i.test(typ)) sub = typ;
    }
    if (!parent) {
      if (item.category === "turbo" || item.category === "pump") parent = "Cores";
      else parent = typeParentName(typ, item.name || "");
    }
    const rawSlug = slugKey(parent);
    if (rawSlug === "health-beauty") parent = typeParentName(typ, item.name || "") || "Mobility";
    else if (rawSlug === "sporting-goods") parent = typeParentName(typ, item.name || "") || "Cycling";
    else if (rawSlug === "business-industrial") parent = typeParentName(typ, item.name || "") || "Material Handling";
    if (!sub || /^vintage$/i.test(sub)) {
      sub = typ && !/^vintage$/i.test(typ) ? typ : kept[kept.length - 1] || parent;
    }
    const subSlug = canonSubSlug(sub) || "other";
    item._eb = {
      parent,
      parentSlug: slugKey(parent) || "other",
      sub: SUB_LABEL[subSlug] || sub,
      subSlug,
    };
    return item._eb;
  }

  function itemHitsParent(item, parentSlug) {
    if (!parentSlug || parentSlug === "all") return true;
    const eb = itemEbayTree(item);
    if (eb.parentSlug === parentSlug) return true;
    return false;
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
      const alias = ownValue(BRAND_ALIASES, key);
      if (typeof alias === "string") push(alias);
    }

    // Vehicle labels: "2000–2011 Dodge Dakota"
    const vehLabels = Array.isArray(item.vehicles) ? item.vehicles : [];
    vehLabels.forEach((label) => {
      push(label);
      push(yearsFromLabel(label));
      // common make/model words already in label; add aliases
      const low = String(label).toLowerCase();
      Object.keys(BRAND_ALIASES).forEach((k) => {
        const a = ownValue(BRAND_ALIASES, k);
        if (typeof a === "string" && low.includes(k)) push(a);
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
        const mkAlias = ownValue(BRAND_ALIASES, mk);
        if (typeof mkAlias === "string") push(mkAlias);
        // multi-word makes: "Mercedes-Benz"
        Object.keys(BRAND_ALIASES).forEach((k) => {
          const a = ownValue(BRAND_ALIASES, k);
          if (typeof a === "string" && mk.includes(k)) push(a);
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

  function pnsFromName(name) {
    const s = String(name || "");
    const rxs = [
      /\bWIX\s+\d{4,6}\b/gi,
      /\bMOOG\s+CV\d+\b/gi,
      /\bCloyes\s+[A-Z]-?\d{2,4}\b/gi,
      /\bStandard\s+JH\d+\b/gi,
      /\bPace\s*Setter\s+DR-?\d+\b/gi,
      /\b8VBB-1100\b/gi,
      /\b780068P\b/gi,
      /\bKW14\b/gi,
    ];
    const out = [];
    rxs.forEach((rx) => {
      const hits = s.match(rx);
      if (hits) hits.forEach((h) => out.push(h));
    });
    return out;
  }

  function cardXrefHint(item) {
    if (Array.isArray(item.interchange)) {
      const first = item.interchange.map((x) => String(x || "").trim()).find(Boolean);
      if (first) return first;
    }
    const pns = Array.isArray(item.part_numbers) ? item.part_numbers : [];
    for (let i = 1; i < pns.length; i++) {
      const bits = String(pns[i] || "")
        .split(/[,;/|]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (bits[0]) return bits[0];
    }
    const named = pnsFromName(item && item.name);
    return named[0] || "";
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
    const vehHint = Array.isArray(item.vehicles)
      ? item.vehicles.filter(Boolean).slice(0, 2).map(displayHyphen)
      : [];
    const xrefHint = cardXrefHint(item);
    const rawN = Number(item.vehicle_count_raw);
    let fitHint = vehHint.length
      ? "Fits " + vehHint.join(" · ")
      : xrefHint
        ? "Interchange " + String(xrefHint)
        : "";
    if (fitHint && Number.isFinite(rawN) && rawN > vehHint.length) {
      fitHint += ` (${rawN} listed)`;
    }

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
            <span class="st-card-cat category">${escapeHtml(itemEbayTree(item).sub || item.ebay_type || catLabel(item.category))}</span>
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

  function itemHitsYear(item, year) {
    if (!year) return true;
    const y = Number(year);
    if (!Number.isFinite(y)) return false;
    const vs = (item.fitment && item.fitment.vehicles) || [];
    if (
      vs.some((v) => {
        if (!v) return false;
        if (activeMake && slugKey(v.make) !== activeMake) return false;
        if (activeModel && slugKey(v.model) !== activeModel) return false;
        if (v.year != null && Number(v.year) === y) return true;
        const a = v.year_from != null ? Number(v.year_from) : null;
        const b = v.year_to != null ? Number(v.year_to) : a;
        return a != null && Number.isFinite(a) && Number.isFinite(b) && y >= a && y <= b;
      })
    ) {
      return true;
    }
    return yearHitsFitment(item, y);
  }

  function itemHitsVehicle(item) {
    if (isNonVehicleDept(item) && (activeMake || activeModel || activeYear)) return false;
    if (activeMake && !itemHitsMake(item, activeMake)) return false;
    if (activeModel && !itemHitsModel(item, activeMake, activeModel)) return false;
    if (activeYear && !itemHitsYear(item, activeYear)) return false;
    return true;
  }

  function catalogCounts() {
    const counts = { all: 0 };
    catalog.forEach((i) => {
      if (!itemHitsVehicle(i)) return;
      const eb = itemEbayTree(i);
      if (!isNonVehicleDept(i)) counts.all++;
      const k = eb.parentSlug;
      if (!counts[k]) counts[k] = { label: eb.parent, n: 0 };
      counts[k].n++;
    });
    return counts;
  }

  function subCounts(parentSlug) {
    const counts = {};
    catalog.forEach((i) => {
      if (!itemHitsVehicle(i)) return;
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

  function yearCounts(makeSlug, modelSlug) {
    const counts = {};
    if (!makeSlug) return counts;
    catalog.forEach((i) => {
      if (!itemHitsMake(i, makeSlug)) return;
      if (modelSlug && !itemHitsModel(i, makeSlug, modelSlug)) return;
      const years = new Set();
      ((i.fitment && i.fitment.vehicles) || []).forEach((v) => {
        if (!v || slugKey(v.make) !== makeSlug) return;
        if (modelSlug && slugKey(v.model) !== modelSlug) return;
        const a = v.year_from != null ? Number(v.year_from) : v.year != null ? Number(v.year) : NaN;
        const b = v.year_to != null ? Number(v.year_to) : a;
        if (!Number.isFinite(a)) return;
        const y0 = Number.isFinite(b) ? Math.min(a, b) : a;
        const y1 = Number.isFinite(b) ? Math.max(a, b) : a;
        if (y1 - y0 > 45) {
          years.add(y0);
          years.add(y1);
          return;
        }
        for (let y = y0; y <= y1; y++) years.add(y);
      });
      years.forEach((y) => {
        const k = String(y);
        if (!counts[k]) counts[k] = { label: k, n: 0 };
        counts[k].n++;
      });
    });
    return counts;
  }

  function modelCounts(makeSlug) {
    const counts = {};
    if (!makeSlug) return counts;
    catalog.forEach((i) => {
      if (!itemHitsMake(i, makeSlug)) return;
      const seen = new Set();
      ((i.fitment && i.fitment.vehicles) || []).forEach((v) => {
        if (!v || slugKey(v.make) !== makeSlug) return;
        const model = (v.model || "").trim();
        const k = slugKey(model);
        if (!k || seen.has(k)) return;
        seen.add(k);
        if (!counts[k]) counts[k] = { label: model, n: 0 };
        counts[k].n++;
      });
    });
    return counts;
  }

  function optionHtml(value, label, n) {
    const text = n != null ? `${label} (${n})` : label;
    return `<option value="${escapeAttr(value)}">${escapeHtml(text)}</option>`;
  }

  function renderFacetChips() {
    const cats = catalogCounts();
    const catSel = document.getElementById("stCatSelect");
    if (catSel) {
      const ranked = Object.entries(cats)
        .filter(([k, v]) => k !== "all" && v && v.n)
        .sort((a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label));
      const main = ranked.filter(([k]) => k !== "other");
      const otherN = (cats.other && cats.other.n) || 0;
      const bits = [optionHtml("all", "All parts", cats.all)];
      main.forEach(([k, v]) => {
        bits.push(optionHtml(k, parentChipLabel(k, v.label), v.n));
      });
      if (otherN) bits.push(optionHtml("other", "Other", otherN));
      catSel.innerHTML = bits.join("");
      const want = category || "all";
      catSel.value = [...catSel.options].some((o) => o.value === want) ? want : "all";
      if (catSel.value !== category) {
        category = catSel.value || "all";
        activeSub = "";
      }
    }

    const makeGroup = document.getElementById("stMakeGroup");
    const makeSel = document.getElementById("stMakeSelect");
    if (makeGroup && makeSel) {
      const makes = makeCounts();
      const makeList = Object.entries(makes).sort(
        (a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label)
      );
      makeGroup.hidden = false;
      makeSel.innerHTML = [optionHtml("", "Any vehicle")].concat(
        makeList.map(([k, v]) => optionHtml(k, v.label, v.n))
      ).join("");
      makeSel.value = activeMake && [...makeSel.options].some((o) => o.value === activeMake)
        ? activeMake
        : "";
      if (makeSel.value !== activeMake) {
        activeMake = makeSel.value;
        activeModel = "";
      }
    }

    const modelGroup = document.getElementById("stModelGroup");
    const modelSel = document.getElementById("stModelSelect");
    if (modelGroup && modelSel) {
      const models = activeMake ? modelCounts(activeMake) : {};
      const modelList = Object.entries(models).sort(
        (a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label)
      );
      if (!activeMake || modelList.length < 1) {
        modelGroup.hidden = true;
        modelSel.innerHTML = "";
        activeModel = "";
      } else {
        modelGroup.hidden = false;
        modelSel.innerHTML = [optionHtml("", "Any model")].concat(
          modelList.map(([k, v]) => optionHtml(k, v.label, v.n))
        ).join("");
        modelSel.value = activeModel && [...modelSel.options].some((o) => o.value === activeModel)
          ? activeModel
          : "";
        if (modelSel.value !== activeModel) activeModel = modelSel.value;
      }
    }

    const yearGroup = document.getElementById("stYearGroup");
    const yearSel = document.getElementById("stYearSelect");
    if (yearGroup && yearSel) {
      const years = activeMake ? yearCounts(activeMake, activeModel) : {};
      const yearList = Object.entries(years).sort((a, b) => Number(b[0]) - Number(a[0]));
      if (!activeMake || yearList.length < 1) {
        yearGroup.hidden = true;
        yearSel.innerHTML = "";
        activeYear = "";
      } else {
        yearGroup.hidden = false;
        yearSel.innerHTML = [optionHtml("", "Any year")].concat(
          yearList.map(([k, v]) => optionHtml(k, v.label, v.n))
        ).join("");
        yearSel.value = activeYear && [...yearSel.options].some((o) => o.value === activeYear)
          ? activeYear
          : "";
        if (yearSel.value !== activeYear) activeYear = yearSel.value;
      }
    }

    const typeGroup = document.getElementById("stTypeGroup");
    const typeSel = document.getElementById("stTypeSelect");
    if (typeGroup && typeSel) {
      const parentOn = category && category !== "all";
      const types = parentOn ? subCounts(category) : {};
      const typeList = Object.entries(types).sort(
        (a, b) => b[1].n - a[1].n || a[1].label.localeCompare(b[1].label)
      );
      if (!parentOn || typeList.length < 2) {
        typeGroup.hidden = true;
        typeSel.innerHTML = "";
        if (typeList.length < 2) activeSub = "";
      } else {
        typeGroup.hidden = false;
        typeSel.innerHTML = [optionHtml("", "Any type")].concat(
          typeList.map(([k, v]) => optionHtml(k, SUB_LABEL[k] || v.label, v.n))
        ).join("");
        typeSel.value = activeSub && [...typeSel.options].some((o) => o.value === activeSub)
          ? activeSub
          : "";
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
        : `Showing ${from}-${to} of ${matching}`;
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
        hint.textContent = `Search amount: ${lo} - ${hi}`;
      }
    } else {
      readFacetPrices();
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
      if (rec && isNonVehicleDept(rec)) {
        if (activeMake || activeModel || activeYear) return false;
        if (category === "all" && !textQ) return false;
      }
      if (activeSub) {
        if (!rec || !itemHitsSub(rec, activeSub)) return false;
      }
      if (activeMake) {
        if (!rec || !itemHitsMake(rec, activeMake)) return false;
      }
      if (activeModel) {
        if (!rec || !itemHitsModel(rec, activeMake, activeModel)) return false;
      }
      if (activeYear) {
        if (!rec || !itemHitsYear(rec, activeYear)) return false;
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
    applyFilters();
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
    document.getElementById("stMakeSelect")?.addEventListener("change", (e) => {
      activeMake = e.target.value || "";
      activeModel = "";
      activeYear = "";
      renderFacetChips();
      applyFilters();
      const next = document.getElementById("stModelGroup");
      if (next && !next.hidden) {
        next.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
    document.getElementById("stModelSelect")?.addEventListener("change", (e) => {
      activeModel = e.target.value || "";
      activeYear = "";
      renderFacetChips();
      applyFilters();
    });
    document.getElementById("stYearSelect")?.addEventListener("change", (e) => {
      activeYear = e.target.value || "";
      renderFacetChips();
      applyFilters();
    });
    document.getElementById("stCatSelect")?.addEventListener("change", (e) => {
      category = e.target.value || "all";
      activeSub = "";
      renderFacetChips();
      applyFilters();
      const next = document.getElementById("stTypeGroup");
      if (next && !next.hidden) {
        next.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
    document.getElementById("stTypeSelect")?.addEventListener("change", (e) => {
      activeSub = e.target.value || "";
      renderFacetChips();
      applyFilters();
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
      activeModel = "";
      activeYear = "";
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
          "Min, max, or search under 40.";
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
      if (countEl) {
        const autoN = catalog.filter((i) => !isNonVehicleDept(i)).length;
        countEl.textContent = `${autoN} listings`;
      }
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
