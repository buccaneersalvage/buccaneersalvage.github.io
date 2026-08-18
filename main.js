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
    let qty = Number(raw.qty);
    if (!Number.isFinite(qty)) qty = 1;
    qty = Math.max(1, Math.min(MAX_QTY, Math.floor(qty)));
    const photo = isSafeImageSrc(raw.photo) ? String(raw.photo).trim() : "";
    return {
      id,
      title: String(raw.title || "Part").slice(0, 200),
      price: String(raw.price || "").slice(0, 32),
      cents: parseCents(raw.cents != null ? raw.cents / 100 : raw.price),
      photo,
      ship: String(raw.ship || "").slice(0, 80),
      checkout,
      qty,
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
      qty: 1,
    });
  }

  function add(item) {
    const next = normalize(item);
    if (!next) return load();
    const items = load();
    const hit = items.find((it) => it.id === next.id);
    if (hit) {
      hit.qty = Math.min(MAX_QTY, hit.qty + (next.qty || 1));
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
    hit.qty = Math.min(MAX_QTY, n);
    save(items);
    return items;
  }

  function remove(id) {
    save(load().filter((it) => it.id !== id));
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
        '<p class="pdp-cart-note">Local pickup by appointment in Carbondale, PA. Square checkout is one item at a time, with that item&apos;s real shipping.</p>' +
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
    const checkout = isSafeCheckout(it.checkout)
      ? `<a class="pdp-cart-line-pay" href="${escapeHtml(it.checkout)}" target="_blank" rel="noopener noreferrer">Checkout</a>`
      : "";
    return `<div class="pdp-cart-line" data-id="${escapeHtml(it.id)}">
      ${img}
      <div class="pdp-cart-line-meta">
        <a class="pdp-cart-line-title" href="${escapeHtml(pdp)}">${escapeHtml(it.title)}</a>
        <p class="pdp-cart-line-price">${escapeHtml(it.price || money(it.cents))}${it.ship ? ` · ${escapeHtml(it.ship)}` : ""}</p>
        <div class="pdp-cart-line-ops">
          <button type="button" class="pdp-cart-qty" data-cart-act="dec" data-id="${escapeHtml(it.id)}" aria-label="Fewer">−</button>
          <span class="pdp-cart-qty-n">${it.qty}</span>
          <button type="button" class="pdp-cart-qty" data-cart-act="inc" data-id="${escapeHtml(it.id)}" aria-label="More">+</button>
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
      `<h2 class="pdp-cart-title">Cart (${n})</h2>` +
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
    if (items.length === 1 && isSafeCheckout(items[0].checkout)) {
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
    if (act === "rm") remove(id);
    else if (act === "inc") setQty(id, (hit ? hit.qty : 0) + 1);
    else if (act === "dec") setQty(id, (hit ? hit.qty : 1) - 1);
    if (!load().length) close();
  }

  function init() {
    ensureDrawer();
    render();
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
  }

  window.BucCart = { add, remove, setQty, load, open, close, count: () => countOf(load()) };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
