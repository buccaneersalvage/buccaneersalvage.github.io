/* One shuffle for the whole hub: a fresh order on every page load.
   shuffle(list)          returns a shuffled copy (Fisher-Yates, crypto.getRandomValues when present).
   shuffleChildren(el)    reorders el's children in place. Layout belongs to the slot, not the item:
                          each slot keeps its class list and image sizes, and "N of M" labels are
                          renumbered to the new position. Lists marked data-shuffle run on load.
   Load it (defer) before the scripts that read those lists, so they see the new order. */
(function () {
  "use strict";
  const c = window.crypto;
  const buf = new Uint32Array(1);
  const below = (n) => {
    if (c && c.getRandomValues) {
      // Rejection sampling keeps every index equally likely.
      const lim = 0x100000000 - (0x100000000 % n);
      let x;
      do { c.getRandomValues(buf); x = buf[0]; } while (x >= lim);
      return x % n;
    }
    return Math.floor(Math.random() * n);
  };

  function shuffle(list) {
    const a = Array.from(list || []);
    for (let i = a.length - 1; i > 0; i--) {
      const j = below(i + 1);
      const t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  const SIZED = "img[sizes], source[sizes]";
  const NUM = /\b\d+ of (\d+)\b/;

  function shuffleChildren(el) {
    if (!el) return;
    const kids = Array.from(el.children);
    if (kids.length < 2) return;
    const slots = kids.map((k) => ({
      cls: k.className,
      sizes: Array.from(k.querySelectorAll(SIZED), (n) => n.getAttribute("sizes")),
    }));
    const order = shuffle(kids);
    order.forEach((k, i) => {
      const s = slots[i];
      k.className = s.cls;
      k.querySelectorAll(SIZED).forEach((n, j) => {
        if (s.sizes[j] != null) n.setAttribute("sizes", s.sizes[j]);
      });
      k.querySelectorAll("[aria-label]").forEach((n) => {
        const v = n.getAttribute("aria-label");
        if (NUM.test(v)) n.setAttribute("aria-label", v.replace(NUM, (m, total) => (i + 1) + " of " + total));
      });
    });
    el.append(...order);
  }

  window.BucShuffle = { shuffle, shuffleChildren };
  document.querySelectorAll("[data-shuffle]").forEach(shuffleChildren);
})();
