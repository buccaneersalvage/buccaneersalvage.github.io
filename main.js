(() => {
  "use strict";

  const year = document.getElementById("y");
  if (year) year.textContent = String(new Date().getFullYear());

  /* Sticky nav solid state */
  const nav = document.getElementById("nav");
  const onScroll = () => {
    if (!nav) return;
    nav.classList.toggle("is-solid", window.scrollY > 24);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* Mobile drawer */
  const toggle = document.getElementById("navToggle");
  const drawer = document.getElementById("drawer");
  if (toggle && drawer) {
    const main = document.getElementById("main");
    const setOpen = (open) => {
      drawer.classList.toggle("is-open", open);
      drawer.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      document.body.classList.toggle("nav-open", open);
      if (main) {
        if (open) main.setAttribute("inert", "");
        else main.removeAttribute("inert");
      }
      if (open) {
        const first = drawer.querySelector("a");
        if (first) first.focus();
      }
    };
    setOpen(false);
    toggle.addEventListener("click", () => {
      setOpen(!drawer.classList.contains("is-open"));
    });
    drawer.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => setOpen(false));
    });
    document.addEventListener("click", (e) => {
      if (!drawer.classList.contains("is-open")) return;
      if (drawer.contains(e.target) || toggle.contains(e.target)) return;
      setOpen(false);
    });
    document.addEventListener("keydown", (e) => {
      if (!drawer.classList.contains("is-open")) return;
      if (e.key === "Escape") {
        setOpen(false);
        toggle.focus();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = [...drawer.querySelectorAll("a, button")].filter(
        (el) => !el.hasAttribute("disabled")
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  /* Scroll reveals */
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nodes = document.querySelectorAll(".reveal");
  if (prefersReduced || !("IntersectionObserver" in window)) {
    nodes.forEach((el) => el.classList.add("is-in"));
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
    );
    nodes.forEach((el) => io.observe(el));
  }
})();

(() => {
  "use strict";

  const KEY = "buc-cart-v1";
  const ID_RE = /^[A-Z0-9]{16,32}$/;
  const MAX_QTY = 20;
  const MAX_LINES = 30;
  const CHECKOUT_API = "https://buc-square-checkout.jollyroger1480.workers.dev/checkout";

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isSafeImageSrc(u) {
    const s = String(u || "").trim();
    if (/^(?:\.\.\/)?assets\/(?:pdp-gallery\/[A-Z0-9]{16,32}\/\d{2}|product-thumbs\/[A-Z0-9]{16,32})\.webp$/.test(s)) {
      return true;
    }
    if (!/^https:\/\//i.test(s)) return false;
    try {
      const host = new URL(s).hostname.toLowerCase();
      return (
        host === "buccaneersalvage.github.io" ||
        host.endsWith(".squareup.com") ||
        host.endsWith(".squarecdn.com") ||
        host === "items-images-production.s3.us-west-2.amazonaws.com"
      );
    } catch (_) {
      return false;
    }
  }

  function isSafeCheckout(u) {
    const s = String(u || "").trim();
    try {
      const url = new URL(s);
      if (url.protocol !== "https:") return false;
      const host = url.hostname.toLowerCase();
      return (
        host === "square.link" ||
        host.endsWith(".square.link") ||
        host === "checkout.square.site" ||
        host.endsWith(".square.site") ||
        host === "checkout.squareup.com" ||
        host.endsWith(".squareup.com")
      );
    } catch (_) {
      return false;
    }
  }

  function parseCents(raw) {
    const n = Number(String(raw == null ? "" : raw).replace(/[^0-9.]/g, ""));
    if (!Number.isFinite(n)) return 0;
    return Math.round(n * 100);
  }

  function money(cents) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
      (Number(cents) || 0) / 100
    );
  }

  function normalize(raw) {
    if (!raw || typeof raw !== "object") return null;
    const id = String(raw.id || "").trim();
    if (!ID_RE.test(id)) return null;
    const checkout = String(raw.checkout || "").trim();
    if (!isSafeCheckout(checkout)) return null;
    // stock comes from the PDP's data-stock (baked from the catalog at build
    // time). null = unknown/legacy page, treat as unlimited (MAX_QTY only).
    const rawStock = Number(raw.stock);
    const stock = Number.isFinite(rawStock) && rawStock >= 0 ? Math.floor(rawStock) : null;
    const cap = stock === null ? MAX_QTY : Math.min(MAX_QTY, stock);
    let qty = Number(raw.qty);
    if (!Number.isFinite(qty)) qty = 1;
    qty = Math.max(1, Math.min(cap, Math.floor(qty)));
    const photo = isSafeImageSrc(raw.photo) ? String(raw.photo).trim() : "";
    return {
      id,
      title: String(raw.title || "Part").slice(0, 200),
      price: String(raw.price || "").slice(0, 32),
      cents: parseCents(raw.price),
      photo,
      ship: String(raw.ship || "").slice(0, 80),
      checkout,
      qty,
      stock,
    };
  }

  function load() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw.map(normalize).filter(Boolean).slice(0, MAX_LINES);
    } catch (_) {
      return [];
    }
  }

  function save(items) {
    localStorage.setItem(KEY, JSON.stringify(items));
    render();
  }

  function countOf(items) {
    return items.reduce((n, it) => n + (it.qty || 0), 0);
  }

  function fromTrigger(el) {
    return normalize({
      id: el.getAttribute("data-id"),
      title: el.getAttribute("data-title"),
      price: el.getAttribute("data-price"),
      photo: el.getAttribute("data-photo"),
      ship: el.getAttribute("data-ship"),
      checkout: el.getAttribute("data-checkout"),
      stock: el.getAttribute("data-stock"),
      qty: 1,
    });
  }

  function add(item) {
    const next = normalize(item);
    if (!next) return load();
    const items = load();
    const hit = items.find((it) => it.id === next.id);
    if (hit) {
      const cap = hit.stock == null ? MAX_QTY : Math.min(MAX_QTY, hit.stock);
      hit.qty = Math.min(cap, hit.qty + (next.qty || 1));
    } else if (items.length < MAX_LINES) {
      items.push(next);
    }
    save(items);
    return items;
  }

  function setQty(id, qty) {
    const items = load();
    const hit = items.find((it) => it.id === id);
    if (!hit) return items;
    const n = Math.floor(Number(qty));
    if (!Number.isFinite(n) || n < 1) {
      save(items.filter((it) => it.id !== id));
      return load();
    }
    const cap = hit.stock == null ? MAX_QTY : Math.min(MAX_QTY, hit.stock);
    hit.qty = Math.min(cap, n);
    save(items);
    return items;
  }

  function remove(id) {
    save(load().filter((it) => it.id !== id));
    return load();
  }

  function clear() {
    save([]);
    return load();
  }

  function ensureDrawer() {
    let overlay = document.getElementById("pdpCartOverlay");
    let drawer = document.getElementById("pdpCartDrawer");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "pdpCartOverlay";
      overlay.className = "pdp-cart-overlay";
      overlay.hidden = true;
      document.body.appendChild(overlay);
    }
    if (!drawer) {
      drawer = document.createElement("aside");
      drawer.id = "pdpCartDrawer";
      drawer.className = "pdp-cart-drawer";
      drawer.hidden = true;
      drawer.setAttribute("aria-label", "Cart");
      drawer.innerHTML =
        '<button type="button" class="pdp-cart-close" aria-label="Close">×</button>' +
        '<div id="pdpCartBody"></div>' +
        '<p class="pdp-cart-note">Local pickup by appointment in Carbondale, PA. Checkout opens Square with this item\'s real shipping.</p>' +
        '<button type="button" class="btn btn-primary" data-bind="checkout">Continue to checkout</button>';
      document.body.appendChild(drawer);
    } else if (!document.getElementById("pdpCartBody")) {
      const close = drawer.querySelector(".pdp-cart-close");
      const body = document.createElement("div");
      body.id = "pdpCartBody";
      if (close && close.nextSibling) drawer.insertBefore(body, close.nextSibling);
      else drawer.insertBefore(body, drawer.firstChild);
    }
    return { overlay, drawer };
  }

  function paintBadge(n) {
    document.querySelectorAll(".nav-cart-count").forEach((el) => {
      if (n > 0) {
        el.hidden = false;
        el.textContent = String(n);
      } else {
        el.hidden = true;
        el.textContent = "";
      }
    });
    document.querySelectorAll(".nav-cart").forEach((el) => {
      el.setAttribute("aria-label", n > 0 ? `Cart, ${n} items` : "Cart");
    });
  }

  function lineHtml(it) {
    const img = it.photo
      ? `<img class="pdp-cart-line-photo" src="${escapeHtml(it.photo)}" alt="" width="64" height="64" />`
      : `<span class="pdp-cart-line-photo" aria-hidden="true"></span>`;
    const href = `p/${encodeURIComponent(it.id)}.html`;
    const pdp = document.body.classList.contains("page-item") ? `../${href}` : href;
    // The per-line link is the item's static SINGLE-quantity Square payment
    // link — it has no way to encode "qty 2". Only show it at qty 1; any
    // higher quantity must go through "Checkout all items" (combined-cart
    // Worker), which actually knows the quantity and checks real stock.
    const checkout =
      it.qty === 1 && isSafeCheckout(it.checkout)
        ? `<a class="pdp-cart-line-pay" href="${escapeHtml(it.checkout)}" target="_blank" rel="noopener noreferrer">Checkout</a>`
        : "";
    const atCap = it.stock != null && it.qty >= it.stock;
    const incTitle = atCap ? ` title="Only ${it.stock} in stock"` : "";
    return `<div class="pdp-cart-line" data-id="${escapeHtml(it.id)}">
      ${img}
      <div class="pdp-cart-line-meta">
        <a class="pdp-cart-line-title" href="${escapeHtml(pdp)}">${escapeHtml(it.title)}</a>
        <p class="pdp-cart-line-price">${escapeHtml(it.price || money(it.cents))}${it.ship ? ` · ${escapeHtml(it.ship)}` : ""}</p>
        <div class="pdp-cart-line-ops">
          <button type="button" class="pdp-cart-qty" data-cart-act="dec" data-id="${escapeHtml(it.id)}" aria-label="Fewer">−</button>
          <span class="pdp-cart-qty-n">${it.qty}</span>
          <button type="button" class="pdp-cart-qty" data-cart-act="inc" data-id="${escapeHtml(it.id)}" aria-label="More"${atCap ? " disabled" : ""}${incTitle}>+</button>
          <button type="button" class="pdp-cart-rm" data-cart-act="rm" data-id="${escapeHtml(it.id)}">Remove</button>
          ${checkout}
        </div>
      </div>
    </div>`;
  }

  function render() {
    const items = load();
    const n = countOf(items);
    paintBadge(n);
    const body = document.getElementById("pdpCartBody");
    const checkout = document.querySelector("#pdpCartDrawer [data-bind=checkout]");
    const note = document.querySelector("#pdpCartDrawer .pdp-cart-note");
    if (!body) return;
    if (!items.length) {
      body.innerHTML = '<p class="pdp-cart-empty">Cart is empty.</p>';
      if (checkout) {
        checkout.hidden = true;
        checkout.setAttribute("hidden", "");
        checkout.removeAttribute("href");
        checkout.setAttribute("aria-disabled", "true");
        checkout.disabled = true;
      }
      if (note) note.hidden = true;
      return;
    }
    const sub = items.reduce((s, it) => s + it.cents * it.qty, 0);
    body.innerHTML =
      `<div class="pdp-cart-head">` +
      `<h2 class="pdp-cart-title">Cart (${n})</h2>` +
      `<button type="button" class="pdp-cart-rm" data-cart-act="rm-all">Remove all</button>` +
      `</div>` +
      `<div class="pdp-cart-lines">${items.map(lineHtml).join("")}</div>` +
      `<p class="pdp-cart-price">Subtotal ${escapeHtml(money(sub))}</p>`;
    if (note) {
      note.hidden = false;
      note.textContent =
        items.length === 1
          ? "Local pickup by appointment in Carbondale, PA. Checkout opens Square with this item's real shipping."
          : "Local pickup by appointment in Carbondale, PA. Checkout opens one Square order for everything in the cart. Square will ask for a ship-to address; pickup is also fine.";
    }
    if (checkout) {
      checkout.hidden = false;
      checkout.removeAttribute("hidden");
      checkout.removeAttribute("href");
      checkout.removeAttribute("aria-disabled");
      checkout.disabled = false;
      checkout.textContent = items.length > 1 ? "Checkout all items" : "Continue to checkout";
    }
  }

  function open() {
    const { overlay, drawer } = ensureDrawer();
    render();
    drawer.hidden = false;
    if (overlay) overlay.hidden = false;
    document.body.classList.add("pdp-drawer-open");
    const closeBtn = drawer.querySelector(".pdp-cart-close");
    if (closeBtn) closeBtn.focus();
  }

  function close() {
    const drawer = document.getElementById("pdpCartDrawer");
    const overlay = document.getElementById("pdpCartOverlay");
    if (!drawer || drawer.hidden) return;
    drawer.hidden = true;
    if (overlay) overlay.hidden = true;
    document.body.classList.remove("pdp-drawer-open");
  }

  async function startCheckout(btn) {
    const items = load();
    if (!items.length) return;
    // Bug fixed 2026-08-19: this shortcut opened the item's pre-built (qty-1)
    // payment link for ANY single-item cart, silently dropping qty>1 instead
    // of checking out that many. Only take the shortcut at qty===1; anything
    // else falls through to the combined-cart Worker, which now also
    // enforces real stock (see cf-checkout-worker/src/index.js).
    if (items.length === 1 && items[0].qty === 1 && isSafeCheckout(items[0].checkout)) {
      window.open(items[0].checkout, "_blank", "noopener,noreferrer");
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Opening checkout…";
    }
    try {
      const res = await fetch(CHECKOUT_API, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          items: items.map((it) => ({ id: it.id, qty: it.qty })),
        }),
      });
      const data = await res.json().catch(() => ({}));
      const url = data && data.url;
      if (!res.ok || !isSafeCheckout(url)) {
        throw new Error((data && data.error) || "checkout_failed");
      }
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (_) {
      const note = document.querySelector("#pdpCartDrawer .pdp-cart-note");
      if (note) {
        note.hidden = false;
        note.textContent =
          "Could not open combined checkout. Use Checkout on each line, or try again.";
      }
    } finally {
      if (btn && btn.isConnected) {
        btn.disabled = false;
        const n = load().length;
        btn.textContent = n > 1 ? "Checkout all items" : "Continue to checkout";
      }
    }
  }

  function markAdded(btn) {
    if (!btn || btn.dataset.addedLock) return;
    const prev = btn.textContent;
    btn.dataset.addedLock = "1";
    btn.textContent = "Added";
    window.setTimeout(() => {
      if (btn.isConnected) btn.textContent = prev;
      delete btn.dataset.addedLock;
    }, 1200);
  }

  function onClick(e) {
    const addBtn = e.target.closest(".pdp-add-cart");
    if (addBtn) {
      e.preventDefault();
      e.stopPropagation();
      const item = fromTrigger(addBtn);
      if (!item) return;
      add(item);
      markAdded(addBtn);
      const drawer = document.getElementById("pdpCartDrawer");
      const drawerOpen = drawer && !drawer.hidden;
      // Store overlay covers the grid — opening it here makes the next
      // Add to cart click do nothing. Keep shopping; open from Cart / PDP.
      if (drawerOpen || document.body.classList.contains("page-item")) {
        open();
      }
      return;
    }
    if (e.target.closest(".pdp-cart-close") || e.target.id === "pdpCartOverlay") {
      close();
      return;
    }
    const pay = e.target.closest("#pdpCartDrawer [data-bind=checkout]");
    if (pay) {
      e.preventDefault();
      startCheckout(pay);
      return;
    }
    const nav = e.target.closest(".nav-cart");
    if (nav) {
      e.preventDefault();
      open();
      return;
    }
    const actBtn = e.target.closest("[data-cart-act]");
    if (!actBtn) return;
    const id = actBtn.getAttribute("data-id") || "";
    const act = actBtn.getAttribute("data-cart-act");
    const items = load();
    const hit = items.find((it) => it.id === id);
    if (act === "rm-all") clear();
    else if (act === "rm") remove(id);
    else if (act === "inc") setQty(id, (hit ? hit.qty : 0) + 1);
    else if (act === "dec") setQty(id, (hit ? hit.qty : 1) - 1);
    if (!load().length) close();
  }

  function parseMetaProductsParam(raw) {
    const s = String(raw || "").trim();
    if (!s) return [];
    const out = [];
    for (const part of s.split(",")) {
      const bit = part.trim();
      if (!bit) continue;
      const colon = bit.lastIndexOf(":");
      const id = (colon === -1 ? bit : bit.slice(0, colon)).trim();
      const qtyRaw = colon === -1 ? "1" : bit.slice(colon + 1).trim();
      if (!ID_RE.test(id)) continue;
      let qty = Number(qtyRaw);
      if (!Number.isFinite(qty)) qty = 1;
      qty = Math.max(1, Math.min(MAX_QTY, Math.floor(qty)));
      out.push({ id, qty });
    }
    return out.slice(0, MAX_LINES);
  }

  function catalogItemToCart(item, qty) {
    if (!item || item.checkout === false) return null;
    return normalize({
      id: item.id,
      title: item.name,
      price: item.price == null ? "" : String(item.price),
      photo: item.image || "",
      ship: "",
      checkout: item.url,
      qty,
    });
  }

  async function hydrateFromMetaQuery() {
    let raw = "";
    try {
      raw = new URLSearchParams(window.location.search).get("products") || "";
    } catch (_) {
      return;
    }
    const wanted = parseMetaProductsParam(raw);
    if (!wanted.length) return;
    let cat;
    try {
      const res = await fetch("/assets/square-catalog.json", { credentials: "same-origin" });
      cat = await res.json();
    } catch (_) {
      return;
    }
    const list = cat && Array.isArray(cat.items) ? cat.items : [];
    const byId = Object.create(null);
    for (const it of list) {
      if (it && it.id) byId[it.id] = it;
    }
    const next = [];
    for (const w of wanted) {
      const line = catalogItemToCart(byId[w.id], w.qty);
      if (line) next.push(line);
    }
    if (!next.length) return;
    save(next);
    open();
  }

  function init() {
    ensureDrawer();
    render();
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
    hydrateFromMetaQuery();
  }

  window.BucCart = {
    add,
    remove,
    clear,
    setQty,
    load,
    open,
    close,
    parseMetaProductsParam,
    count: () => countOf(load()),
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

(() => {
  "use strict";

  const PHONE = "(570) 468-2901";
  const PHONE_HREF = "tel:+15704682901";
  const EMAIL = "jollyroger1480@gmail.com";
  const EMAIL_HREF = "mailto:jollyroger1480@gmail.com";
  const EMAIL_LINK = "<a href=\"" + EMAIL_HREF + "\">" + EMAIL + "</a>";
  const PHONE_LINK = "<a href=\"" + PHONE_HREF + "\">" + PHONE + "</a>";
  const PAGE = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  const PHONE_OK = PAGE === "scrap.html" || PAGE === "map.html";
  const SCRAP_HINT = PHONE_OK
    ? "see <a href=\"/scrap.html\">Scrap Removal</a> or call " + PHONE_LINK
    : "see <a href=\"/scrap.html\">Scrap Removal</a>";
  const CONTACT_SCRAP = PHONE_OK ? PHONE_LINK : "<a href=\"/scrap.html\">Scrap Removal</a>";
  const ASK_SUB = PHONE_OK
    ? "Basic answers. Call if you need a person."
    : "Basic answers. Email if you need a person.";

  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^\w\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  const RULES = [
    {
      id: "dispute",
      escalate: true,
      keys: ["dispute", "attorney", "lawyer", "lawsuit", "legal action"],
      html: "We will review this. Please email " + EMAIL_LINK + ".",
    },
    {
      id: "damage",
      escalate: true,
      keys: ["damaged", "broken", "defect", "crushed", "wrong item"],
      html: "Sorry that happened. Email " + EMAIL_LINK + " and we will sort it.",
    },
    {
      id: "order",
      escalate: true,
      keys: [
        "tracking",
        "track my",
        "shipped yet",
        "where is my order",
        "never arrived",
        "cancel my order",
      ],
      html:
        "This chat cannot look up orders. Bought here: email " +
        EMAIL_LINK +
        ". Bought on eBay: message that listing.",
    },
    {
      id: "scrap",
      escalate: false,
      keys: [
        "scrap",
        "junk removal",
        "junk haul",
        "e-waste",
        "ewaste",
        "electronics recycling",
        "metal haul",
        "pick up scrap",
      ],
      html:
        "Free scrap metal haul by appointment. Junk removal and e-waste are paid. Drop-off is cheaper than pickup. " +
        SCRAP_HINT.charAt(0).toUpperCase() +
        SCRAP_HINT.slice(1) +
        ".",
    },
    {
      id: "pickup",
      escalate: false,
      keys: ["pickup", "pick up", "pick it up", "come get", "come by", "appointment"],
      html:
        "Local parts pickup at 12 Beech St, Carbondale, PA 18407, by appointment. Email " +
        EMAIL_LINK +
        " to set a time. Scrap or junk: " +
        SCRAP_HINT +
        ".",
    },
    {
      id: "hours",
      escalate: false,
      keys: ["hours", "are you open", "when are you open", "business hours"],
      html:
        "By appointment. Store questions: email " +
        EMAIL_LINK +
        ". Scrap or junk: " +
        SCRAP_HINT +
        ".",
    },
    {
      id: "shipping",
      escalate: false,
      keys: ["shipping", "delivery", "ship to", "freight", "how long to ship"],
      html: "US shipping at Square checkout, or local pickup by appointment. Rates shown at checkout.",
    },
    {
      id: "returns",
      escalate: false,
      keys: ["return", "refund", "warranty"],
      html:
        "Store terms: <a href=\"/terms.html\">Terms</a>. eBay orders follow that listing’s return policy.",
    },
    {
      id: "fitment",
      escalate: false,
      keys: ["will this fit", "fits", "compatible", "will this work", "year make"],
      html:
        "Check the product page for fitment. If you are unsure, email " +
        EMAIL_LINK +
        " with the year, make, model, and part.",
    },
    {
      id: "pay",
      escalate: false,
      keys: ["cash app", "cashapp", "paypal", "venmo", "how to pay", "how do i pay", "checkout"],
      html:
        "We do not take PayPal. Site checkout is Square. Cash App $jollyroger1480 is for arranged local deals only.",
    },
    {
      id: "contact",
      escalate: false,
      keys: ["phone", "call", "text", "email", "address", "where are you"],
      html:
        "Store and listings: " +
        EMAIL_LINK +
        ". Scrap or junk: " +
        CONTACT_SCRAP +
        ". 12 Beech St, Carbondale, PA 18407.",
    },
  ];

  const OTHER = {
    id: "other",
    escalate: true,
    html:
      "I am a basic helper. Email " +
      EMAIL_LINK +
      ". Scrap or junk: " +
      SCRAP_HINT +
      ".",
  };

  function classify(text) {
    const n = normalize(text);
    if (!n) return { id: OTHER.id, escalate: OTHER.escalate };
    for (const rule of RULES) {
      for (const key of rule.keys) {
        if (n.includes(normalize(key))) {
          return { id: rule.id, escalate: rule.escalate };
        }
      }
    }
    return { id: OTHER.id, escalate: OTHER.escalate };
  }

  function reply(text) {
    const hit = classify(text);
    const rule = RULES.find((r) => r.id === hit.id) || OTHER;
    return { id: hit.id, escalate: hit.escalate, html: rule.html };
  }

  function inject() {
    if (document.getElementById("bucAskRoot")) return;
    const root = document.createElement("div");
    root.id = "bucAskRoot";
    root.innerHTML =
      '<button type="button" class="buc-ask-launch" id="bucAskLaunch" aria-expanded="false" aria-controls="bucAskPanel">Ask</button>' +
      '<div class="buc-ask-panel" id="bucAskPanel" hidden>' +
      '<div class="buc-ask-head">' +
      '<div><p class="buc-ask-title">Ask BuccaneerSalvage</p>' +
      '<p class="buc-ask-sub">' + ASK_SUB + "</p></div>" +
      '<button type="button" class="buc-ask-close" id="bucAskClose" aria-label="Close">×</button>' +
      "</div>" +
      '<div class="buc-ask-chips" id="bucAskChips">' +
      '<button type="button" data-ask="hours">Hours</button>' +
      '<button type="button" data-ask="Can I pick it up?">Pickup</button>' +
      '<button type="button" data-ask="scrap">Scrap Removal</button>' +
      '<button type="button" data-ask="shipping">Shipping</button>' +
      '<button type="button" data-ask="phone">Contact</button>' +
      "</div>" +
      '<div class="buc-ask-log" id="bucAskLog" aria-live="polite"></div>' +
      '<form class="buc-ask-form" id="bucAskForm">' +
      '<label class="visually-hidden" for="bucAskInput">Your question</label>' +
      '<input id="bucAskInput" type="text" maxlength="240" autocomplete="off" placeholder="Ask about pickup, scrap, shipping…" />' +
      '<button type="submit">Send</button>' +
      "</form></div>";
    document.body.appendChild(root);

    const launch = document.getElementById("bucAskLaunch");
    const panel = document.getElementById("bucAskPanel");
    const closeBtn = document.getElementById("bucAskClose");
    const form = document.getElementById("bucAskForm");
    const input = document.getElementById("bucAskInput");
    const log = document.getElementById("bucAskLog");

    function setOpen(open) {
      panel.hidden = !open;
      launch.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.classList.toggle("buc-ask-open", open);
      if (open) input.focus();
    }

    function addTurn(q, html) {
      const wrap = document.createElement("div");
      wrap.className = "buc-ask-turn";
      const qEl = document.createElement("p");
      qEl.className = "buc-ask-q";
      qEl.textContent = q;
      const aEl = document.createElement("div");
      aEl.className = "buc-ask-a";
      aEl.innerHTML = html;
      wrap.appendChild(qEl);
      wrap.appendChild(aEl);
      log.appendChild(wrap);
      log.scrollTop = log.scrollHeight;
    }

    function ask(text) {
      const q = String(text || "").trim();
      if (!q) return;
      const out = reply(q);
      addTurn(q, out.html);
    }

    launch.addEventListener("click", () => setOpen(panel.hidden));
    closeBtn.addEventListener("click", () => setOpen(false));
    document.getElementById("bucAskChips").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-ask]");
      if (!btn) return;
      setOpen(true);
      ask(btn.getAttribute("data-ask"));
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = input.value;
      input.value = "";
      ask(q);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !panel.hidden) {
        setOpen(false);
        launch.focus();
      }
    });
  }

  window.BucSupport = { classify, reply };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();

/* Scrap page yard-photo carousel + zoom lightbox — no-op on any other page. */
(() => {
  "use strict";

  const carousel = document.getElementById("scrapCarousel");
  const track = document.getElementById("scrapTrack");
  if (!carousel || !track) return;

  const slides = Array.from(track.querySelectorAll(".scrap-slide"));
  if (!slides.length) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let index = 0;
  let timer = null;
  let hovering = false;
  let dots = [];
  const dotsHost = document.getElementById("scrapDots");

  // How many slides are actually visible at once at the current breakpoint
  // (must match the .scrap-slide flex-basis media queries in styles.css).
  // The nav is clamped to this so the last "page" never scrolls past the
  // point where a full row still fits — otherwise the last slide(s) leave
  // dead empty space where the next card(s) would have been.
  function visibleCount() {
    if (window.matchMedia("(min-width: 1020px)").matches) return 3;
    if (window.matchMedia("(min-width: 640px)").matches) return 2;
    return 1;
  }

  function maxIndex() {
    return Math.max(0, slides.length - visibleCount());
  }

  function slideStep() {
    const first = slides[0];
    const gap = parseFloat(getComputedStyle(track).gap || "0") || 0;
    return first.getBoundingClientRect().width + gap;
  }

  function paint() {
    track.style.transform = `translateX(-${index * slideStep()}px)`;
    dots.forEach((d, i) => d.classList.toggle("is-active", i === index));
  }

  function goTo(n) {
    const span = maxIndex() + 1;
    index = ((n % span) + span) % span;
    paint();
  }

  function next() {
    goTo(index + 1);
  }
  function prev() {
    goTo(index - 1);
  }

  function startAutoplay() {
    if (reduceMotion || timer || hovering) return;
    timer = window.setInterval(next, 4200);
  }
  function stopAutoplay() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }
  function kickAutoplay() {
    stopAutoplay();
    if (!hovering) startAutoplay();
  }

  function buildDots() {
    const count = maxIndex() + 1;
    if (dots.length === count) return; // already correct for this breakpoint
    if (dotsHost) dotsHost.replaceChildren();
    dots = Array.from({ length: count }, (_, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-label", `Go to photo ${i + 1}`);
      b.addEventListener("click", () => {
        goTo(i);
        kickAutoplay();
      });
      if (dotsHost) dotsHost.appendChild(b);
      return b;
    });
  }

  function handleResize() {
    buildDots();
    if (index > maxIndex()) index = maxIndex();
    paint();
  }

  buildDots();

  const prevBtn = carousel.querySelector(".scrap-carousel-nav.prev");
  const nextBtn = carousel.querySelector(".scrap-carousel-nav.next");
  if (prevBtn) prevBtn.addEventListener("click", () => { prev(); kickAutoplay(); });
  if (nextBtn) nextBtn.addEventListener("click", () => { next(); kickAutoplay(); });

  carousel.addEventListener("mouseenter", () => { hovering = true; stopAutoplay(); });
  carousel.addEventListener("mouseleave", () => { hovering = false; startAutoplay(); });
  carousel.addEventListener("focusin", () => { hovering = true; stopAutoplay(); });
  carousel.addEventListener("focusout", () => { hovering = false; startAutoplay(); });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopAutoplay();
    else startAutoplay();
  });
  window.addEventListener("resize", handleResize, { passive: true });

  /* Lightbox — click any slide to zoom, with prev/next between all photos. */
  const box = document.getElementById("scrapLightbox");
  const img = document.getElementById("scrapLightboxImage");
  const caption = document.getElementById("scrapLightboxCaption");
  if (box && img) {
    const stage = box.querySelector(".scrap-lightbox-stage") || box;
    const closeBtn = box.querySelector(".scrap-lightbox-close");
    const lbPrev = box.querySelector(".scrap-lightbox-nav.prev");
    const lbNext = box.querySelector(".scrap-lightbox-nav.next");
    let lbIndex = 0;
    let scale = 1;
    let lastTap = 0;
    let pinch0 = 0;
    let scale0 = 1;

    function setScale(n) {
      scale = Math.min(4, Math.max(1, n));
      img.style.transform = `scale(${scale})`;
    }
    function resetZoom() {
      setScale(1);
    }

    function showLb(n) {
      lbIndex = ((n % slides.length) + slides.length) % slides.length;
      const slide = slides[lbIndex];
      const srcImg = slide.querySelector("img");
      const fig = slide.querySelector("figcaption");
      if (!srcImg) return;
      img.src = srcImg.currentSrc || srcImg.src;
      img.alt = srcImg.alt || "";
      if (caption) caption.textContent = fig ? fig.textContent : "";
      resetZoom();
    }

    function openLb(n) {
      stopAutoplay();
      showLb(n);
      box.hidden = false;
      document.body.classList.add("scrap-lightbox-open");
      if (closeBtn) closeBtn.focus();
    }
    function closeLb() {
      if (box.hidden) return;
      box.hidden = true;
      document.body.classList.remove("scrap-lightbox-open");
      resetZoom();
      startAutoplay();
    }
    function lbNextFn() { showLb(lbIndex + 1); }
    function lbPrevFn() { showLb(lbIndex - 1); }

    slides.forEach((slide, i) => {
      slide.setAttribute("tabindex", "0");
      slide.setAttribute("role", "button");
      slide.setAttribute("aria-label", "Zoom photo");
      slide.addEventListener("click", () => openLb(i));
      slide.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openLb(i);
        }
      });
    });

    if (closeBtn) closeBtn.addEventListener("click", closeLb);
    if (lbNext) lbNext.addEventListener("click", lbNextFn);
    if (lbPrev) lbPrev.addEventListener("click", lbPrevFn);
    box.addEventListener("click", (e) => {
      if (e.target === box) closeLb();
    });
    document.addEventListener("keydown", (e) => {
      if (box.hidden) return;
      if (e.key === "Escape") closeLb();
      else if (e.key === "ArrowRight") lbNextFn();
      else if (e.key === "ArrowLeft") lbPrevFn();
    });
    stage.addEventListener(
      "wheel",
      (e) => {
        if (box.hidden) return;
        e.preventDefault();
        setScale(scale + (e.deltaY < 0 ? 0.2 : -0.2));
      },
      { passive: false }
    );
    img.addEventListener("pointerup", () => {
      if (box.hidden) return;
      const now = Date.now();
      if (now - lastTap < 280) {
        setScale(scale > 1 ? 1 : 2);
        lastTap = 0;
      } else {
        lastTap = now;
      }
    });
    stage.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length === 2) {
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          pinch0 = Math.hypot(dx, dy) || 1;
          scale0 = scale;
        }
      },
      { passive: true }
    );
    stage.addEventListener(
      "touchmove",
      (e) => {
        if (e.touches.length === 2 && pinch0) {
          e.preventDefault();
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          setScale(scale0 * (Math.hypot(dx, dy) / pinch0));
        }
      },
      { passive: false }
    );
  }

  paint();
  startAutoplay();
})();
