(() => {
  "use strict";

  function initLanePicker(root) {
    const tabs = root.querySelectorAll(".lane-tab");
    if (!tabs.length) return;
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const id = tab.getAttribute("aria-controls");
        tabs.forEach((t) => {
          const on = t === tab;
          t.classList.toggle("is-on", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
        root.querySelectorAll(".lane-panel").forEach((panel) => {
          const on = panel.id === id;
          panel.classList.toggle("is-on", on);
          panel.hidden = !on;
        });
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
