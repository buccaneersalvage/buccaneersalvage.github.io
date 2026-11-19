(() => {
  "use strict";

  function initLanePicker(root) {
    const tabs = [...root.querySelectorAll(".lane-tab")];
    if (!tabs.length) return;

    function activateTab(tab, focusTab) {
      const id = tab.getAttribute("aria-controls");
      tabs.forEach((t) => {
        const on = t === tab;
        t.classList.toggle("is-on", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.setAttribute("tabindex", on ? "0" : "-1");
      });
      root.querySelectorAll(".lane-panel").forEach((panel) => {
        const on = panel.id === id;
        panel.classList.toggle("is-on", on);
        panel.hidden = !on;
      });
      if (focusTab) tab.focus();
    }

    // Initialize roving tabindex cleanly
    const initial =
      tabs.find((t) => t.getAttribute("aria-selected") === "true") || tabs[0];
    activateTab(initial, false);

    tabs.forEach((tab, idx) => {
      tab.addEventListener("click", () => activateTab(tab, false));
      tab.addEventListener("keydown", (e) => {
        let nextIdx = -1;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          nextIdx = (idx + 1) % tabs.length;
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          nextIdx = (idx - 1 + tabs.length) % tabs.length;
        } else if (e.key === "Home") {
          nextIdx = 0;
        } else if (e.key === "End") {
          nextIdx = tabs.length - 1;
        }
        if (nextIdx >= 0) {
          e.preventDefault();
          activateTab(tabs[nextIdx], true);
        }
      });
    });
  }

  function init() {
    document.querySelectorAll(".lane-picker").forEach(initLanePicker);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
