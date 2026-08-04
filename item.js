(() => {
  "use strict";

  /**
   * BuccaneerSalvage PDP — Product Detail Page
   * Load item by URL param; display from static catalog JSON.
   * Primary CTA opens Square checkout (catalog item.url).
   */
  const CATALOG_URL = "assets/square-catalog.json?v=20260804s";
  const CORE_WARN = "FOR PARTS OR REBUILD · UNTESTED · NO RETURNS";

  const money = (n) =>
    n == null || Number.isNaN(Number(n))
      ? ""
      : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  const isCore = (item) => item.category === "turbo" || item.category === "pump";

  const catLabel = (c) =>
    (
      {
        "air-spring": "Air spring",
        brake: "Brake hardware",
        turbo: "Turbo core",
        pump: "Pump core",
        other: "Parts",
      }[c] || "Parts"
    );

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function safeUrl(u) {
    const s = String(u || "").trim();
    return /^https?:\/\//i.test(s) ? s : "";
  }

  /**
   * Catalog JSON has no fitment fields. Pull useful signals from the title:
   * - "Replaces W01-358-8091 1R14-171" → interchange
   * - Brand OEM tokens (Automann/Goodyear/Carlson/etc. part codes)
   * - "for Ford F-Series", "Dodge Ram Dakota", Mercedes class, Mack truck
   */
  function parseTitleSpecs(name) {
    const title = String(name || "").trim();
    const parts = [];
    const xref = [];
    const vehicles = [];

    // Cross-ref after "Replaces" / "Replace" / "Repl."
    const rep = title.match(
      /\bReplaces?\b\.?\s+(.+?)(?:\s+[—–-]\s+|\s+New\b|\s+NOS\b|$)/i
    );
    if (rep) {
      const chunk = rep[1]
        .replace(/\b(New|NOS|Brand New|in Original Box)\b/gi, "")
        .trim();
      chunk.split(/[,\s]+(?:and\s+)?/).forEach((tok) => {
        const t = tok.replace(/[()]/g, "").trim();
        if (t.length >= 4 && /[A-Za-z0-9]/.test(t) && !/^(or|for|the)$/i.test(t)) {
          if (!xref.includes(t)) xref.push(t);
        }
      });
      // Prefer whitespace-split tokens that look like part numbers
      const better = chunk.match(
        /\b(?:W\d{2}-\d{3}-\d{4}|1R\d{2}-\d{2,4}|[A-Z]{0,4}\d[\w./-]{3,})\b/gi
      );
      if (better) {
        better.forEach((t) => {
          if (!xref.includes(t)) xref.push(t);
        });
      }
    }

    // Leading brand + primary PN patterns
    const brandPn = title.match(
      /^(?:OEM\s+)?(Automann|Goodyear|Continental|Carlson|Mack|Holset|Wagner|Firestone|Meritor)\s+([A-Z0-9][\w./-]{2,})/i
    );
    if (brandPn) {
      parts.push(`${brandPn[1]} ${brandPn[2]}`);
    } else {
      const carlson = title.match(/\b(Carlson)\s+(H?\d{4,5}[A-Z]?Q?)\b/i);
      if (carlson) parts.push(`${carlson[1]} ${carlson[2]}`);
      const bare = title.match(/^(H?\d{4,5}[A-Z]?Q?)\b/);
      if (bare) parts.push(bare[1]);
    }

    // Firestone-style W01-… and 1R… anywhere in title (primary, not only Replaces)
    (title.match(/\bW\d{2}-\d{3}-\d{4}\b/g) || []).forEach((t) => {
      if (!parts.includes(t) && !xref.includes(t)) parts.push(t);
    });
    (title.match(/\b1R\d{2}-\d{2,4}\b/g) || []).forEach((t) => {
      if (!parts.includes(t) && !xref.includes(t)) parts.push(t);
    });

    // Vehicle / application phrases
    const vehiclePatterns = [
      /\bfor\s+((?:Ford|Chevy|Chevrolet|GMC|Dodge|Ram|Mercedes(?:-Benz)?|Mack|Kia|Toyota|Honda|Jeep|Nissan)[^—–,]{0,60})/gi,
      /\b((?:Ford|Chevy|Chevrolet|GMC)\s+F-?Series(?:\s*\/\s*E-Series)?)/gi,
      /\b(Dodge\s+Ram(?:\s+Dakota)?(?:\s+Durango)?)/gi,
      /\b(Mercedes(?:-Benz)?\s+S-Class(?:\s*\/\s*SL-Class)?)/gi,
      /\b(Mack\s+Truck(?:\s+V8)?)/gi,
      /\b(Parking Brake\s+Kia)\b/gi,
    ];
    vehiclePatterns.forEach((re) => {
      let m;
      const r = new RegExp(re.source, re.flags);
      while ((m = r.exec(title)) !== null) {
        let v = (m[1] || m[0] || "")
          .replace(/\s+[—–-].*$/, "")
          .replace(/\s*[-–—]\s*New.*$/i, "")
          .replace(/\s+Brand New.*$/i, "")
          .replace(/\s*!\s*$/, "")
          .trim();
        v = v.replace(/\s{2,}/g, " ");
        if (v.length >= 3 && !vehicles.some((x) => x.toLowerCase() === v.toLowerCase())) {
          vehicles.push(v);
        }
      }
    });

    // Mack truck cores often name the platform without "for"
    if (/\bMack\b/i.test(title) && !vehicles.some((v) => /mack/i.test(v))) {
      vehicles.push("Mack truck (verify model / OEM casting)");
    }

    // Deduplicate xref vs parts
    const xrefClean = xref.filter((x) => !parts.some((p) => p.includes(x) && p !== x));

    return { parts, xref: xrefClean, vehicles };
  }

  function fillList(ulId, items) {
    const ul = document.getElementById(ulId);
    if (!ul) return;
    ul.replaceChildren();
    items.forEach((text) => {
      const li = document.createElement("li");
      li.textContent = text; // textContent — never innerHTML for catalog strings
      ul.appendChild(li);
    });
  }

  /**
   * Prefer structured catalog fitment (built by scripts/build_fitment.py).
   * Fall back to title regex only when DB fields are empty.
   */
  function resolveFitment(item) {
    const dbParts = Array.isArray(item.part_numbers) ? item.part_numbers : [];
    const dbXref = Array.isArray(item.interchange) ? item.interchange : [];
    const dbVehicles = Array.isArray(item.vehicles) ? item.vehicles : [];
    // Structured vehicle objects → display labels
    if ((!dbVehicles.length) && item.fitment && Array.isArray(item.fitment.vehicles)) {
      item.fitment.vehicles.forEach((v) => {
        if (!v || typeof v !== "object") return;
        const label =
          v.notes ||
          [v.year_from && v.year_to ? `${v.year_from}–${v.year_to}` : "", v.make, v.model]
            .filter(Boolean)
            .join(" ")
            .trim();
        if (label) dbVehicles.push(label);
      });
    }
    const hasDb = dbParts.length || dbXref.length || dbVehicles.length;
    if (hasDb) {
      return {
        parts: dbParts,
        xref: dbXref,
        vehicles: dbVehicles,
        source: item.fitment_source || (item.fitment && item.fitment.source) || "catalog",
        confidence:
          item.fitment_confidence ||
          (item.fitment && item.fitment.confidence) ||
          "medium",
      };
    }
    const parsed = parseTitleSpecs(item.name);
    return {
      parts: parsed.parts,
      xref: parsed.xref,
      vehicles: parsed.vehicles,
      source: "title",
      confidence: "low",
    };
  }

  /** Human copy only — never expose internal pipeline keys. */
  function setFitmentNotes(source, confidence, vehicleCount, rawCount) {
    const xrefNote = document.querySelector("#pdpXrefBlock .pdp-fitment-note");
    const vehNote = document.querySelector("#pdpVehicleBlock .pdp-fitment-note");
    const fromEbay =
      source &&
      (String(source).includes("ebay_listing") || String(source).includes("ebay_compat"));
    const fromDisk =
      source &&
      (String(source).includes("carlson") || String(source).includes("airspring_inventory"));
    if (xrefNote) {
      if (fromEbay || fromDisk) {
        xrefNote.textContent =
          "Cross-reference numbers from the live listing / inventory data. Match these to your old part before ordering.";
      } else {
        xrefNote.textContent =
          "Interchange numbers taken from the product title. Confirm against your application before ordering.";
      }
    }
    if (vehNote) {
      if (fromEbay && (vehicleCount > 0 || rawCount > 0)) {
        const extra =
          rawCount > vehicleCount
            ? ` ${rawCount} eBay fitment rows collapsed into ${vehicleCount} year/make/model ranges.`
            : "";
        vehNote.textContent =
          "Vehicle applications from the eBay listing compatibility list." +
          extra +
          " Confirm year, make, model, and trim before ordering.";
      } else if (fromDisk && vehicleCount > 0) {
        vehNote.textContent =
          "Application notes from inventory records. Confirm year/make/model and OEM numbers before ordering.";
      } else {
        vehNote.textContent =
          "Limited application notes from the title only — not a full fitment list. Confirm year/make/model and OEM numbers.";
      }
    }
  }

  function renderFitment(item) {
    const root = document.getElementById("pdpFitment");
    const partBlock = document.getElementById("pdpPartBlock");
    const xrefBlock = document.getElementById("pdpXrefBlock");
    const vehBlock = document.getElementById("pdpVehicleBlock");
    const coreNote = document.getElementById("pdpCoreNote");
    if (!root) return;

    const { parts, xref, vehicles, source, confidence } = resolveFitment(item);
    const rawCount = Number(item.vehicle_count_raw || (item.fitment && item.fitment.raw_compat_rows) || 0) || 0;
    setFitmentNotes(source, confidence, vehicles.length, rawCount);
    let any = false;

    if (parts.length) {
      fillList("pdpPartList", parts);
      partBlock?.removeAttribute("hidden");
      any = true;
    } else {
      partBlock?.setAttribute("hidden", "");
    }

    if (xref.length) {
      fillList("pdpXrefList", xref);
      xrefBlock?.removeAttribute("hidden");
      any = true;
    } else {
      xrefBlock?.setAttribute("hidden", "");
    }

    if (vehicles.length) {
      fillList("pdpVehicleList", vehicles);
      vehBlock?.removeAttribute("hidden");
      any = true;
    } else {
      vehBlock?.setAttribute("hidden", "");
    }

    if (isCore(item)) {
      coreNote?.removeAttribute("hidden");
      any = true;
    } else {
      coreNote?.setAttribute("hidden", "");
    }

    if (any) root.removeAttribute("hidden");
    else root.setAttribute("hidden", "");
  }

  function updateSEO(item) {
    if (!item) return;

    const title = `${item.name} | BuccaneerSalvage Store`;
    const desc = `${item.name} — ${catLabel(item.category)}. ${money(item.price)}. Browse and secure checkout at BuccaneerSalvage Store.`;
    const imgUrl = safeUrl(item.image) || "https://buccaneersalvage.github.io/assets/og-share.jpg";
    const itemUrl = `https://buccaneersalvage.github.io/item.html?id=${encodeURIComponent(item.id)}`;

    // Basic meta
    document.getElementById("pageTitle").textContent = title;
    document.title = title;
    document.getElementById("pageMeta").setAttribute("content", desc);
    document.getElementById("canonical").setAttribute("href", itemUrl);

    // OG
    document.getElementById("ogTitle").setAttribute("content", item.name);
    document.getElementById("ogDesc").setAttribute("content", desc);
    document.getElementById("ogImage").setAttribute("content", imgUrl);

    // Twitter
    document.getElementById("twitterTitle").setAttribute("content", item.name);
    document.getElementById("twitterDesc").setAttribute("content", desc);
    document.getElementById("twitterImage").setAttribute("content", imgUrl);

    // Product schema
    const schema = {
      "@context": "https://schema.org",
      "@type": "Product",
      name: item.name,
      description: desc,
      image: imgUrl,
      brand: {
        "@type": "Brand",
        name: "BuccaneerSalvage",
      },
      manufacturer: {
        "@type": "Organization",
        name: "BuccaneerSalvage",
      },
      offers: {
        "@type": "Offer",
        url: item.url || "",
        priceCurrency: "USD",
        price: item.price?.toString() || "0.00",
        availability: "https://schema.org/InStock",
        seller: {
          "@type": "Organization",
          name: "BuccaneerSalvage",
          url: "https://buccaneersalvage.github.io/",
        },
      },
    };
    document.getElementById("productSchema").textContent = JSON.stringify(schema);
  }

  function renderProduct(item) {
    // Breadcrumb
    document.getElementById("pdpBreadcrumb").textContent = item.name;

    // Image
    const imgUrl = safeUrl(item.image);
    const imgEl = document.getElementById("pdpImage");
    if (imgUrl) {
      imgEl.src = imgUrl;
      imgEl.alt = item.name;
    } else {
      imgEl.style.display = "none";
    }

    // Title, category, price
    document.getElementById("pdpTitle").textContent = item.name;
    document.getElementById("pdpCategory").textContent = catLabel(item.category);
    document.getElementById("pdpPrice").textContent = money(item.price) || "Contact for price";

    // Checkout button
    const checkoutEl = document.getElementById("pdpCheckout");
    const checkoutUrl = safeUrl(item.url);
    if (checkoutUrl) {
      checkoutEl.href = checkoutUrl;
      checkoutEl.setAttribute("target", "_blank");
      checkoutEl.setAttribute("rel", "noopener noreferrer");
    } else {
      checkoutEl.disabled = true;
      checkoutEl.textContent = "Not available for purchase";
    }

    // Core warning
    if (isCore(item)) {
      document.getElementById("pdpCTALabel").textContent = "Checkout — for parts · no returns";
      const warnEl = document.getElementById("pdpWarn");
      warnEl.textContent = CORE_WARN;
      warnEl.removeAttribute("hidden");
    } else {
      document.getElementById("pdpCTALabel").textContent = "Buy · secure checkout";
    }

    // Interchange / vehicle notes from title
    renderFitment(item);

    // Update SEO
    updateSEO(item);

    // Show content, hide error
    document.getElementById("productContent").removeAttribute("hidden");
    document.getElementById("pdpError").setAttribute("hidden", "");
  }

  function showError(msg) {
    document.getElementById("pdpErrorMsg").textContent = msg;
    document.getElementById("productContent")?.setAttribute("hidden", "");
    document.getElementById("pdpError")?.removeAttribute("hidden");
  }

  async function boot() {
    try {
      // Get item ID from URL
      const params = new URLSearchParams(window.location.search);
      const itemId = params.get("id");
      if (!itemId) {
        showError("No product ID specified.");
        return;
      }

      // Load catalog
      const res = await fetch(CATALOG_URL, { cache: "no-cache" });
      if (!res.ok) {
        throw new Error(`Catalog ${res.status}`);
      }
      const data = await res.json();
      const catalog = Array.isArray(data.items) ? data.items : [];

      // Find item
      const item = catalog.find((i) => i.id === itemId);
      if (!item) {
        showError(`Product "${itemId}" not found in catalog.`);
        return;
      }

      renderProduct(item);
    } catch (err) {
      showError(`Could not load product: ${err.message}`);
      console.warn("[item]", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
