(() => {
  "use strict";

  /**
   * BuccaneerSalvage PDP — Product Detail Page
   * Load item by URL param; display from static catalog JSON.
   * Primary CTA opens Square checkout (catalog item.url).
   */
  const CATALOG_URL = "assets/square-catalog.json";
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

    // Update SEO
    updateSEO(item);

    // Show content, hide error
    document.getElementById("productContent").removeAttribute("hidden");
    document.getElementById("pdpError").setAttribute("hidden", "");
  }

  function showError(msg) {
    document.getElementById("pdpErrorMsg").textContent = msg;
    document.getElementById("pdpContent").setAttribute("hidden", "");
    document.getElementById("pdpError").removeAttribute("hidden");
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
