/** Generic tab component. */

/** Load a lazy HTMX tab panel (e.g. product reviews) when it becomes visible. */
const loadLazyPanel = (panel) => {
  if (!panel?.hasAttribute("hx-get")) {
    return;
  }
  if (panel.querySelector("#reviews-container")) {
    return;
  }
  if (typeof htmx !== "undefined") {
    htmx.trigger(panel, "revealed");
  }
};

const initTabs = (root = document) => {
  root.querySelectorAll("[data-tabs]").forEach((tabsEl) => {
    const buttons = tabsEl.querySelectorAll("[data-tab-btn]");
    const panels = tabsEl.querySelectorAll("[data-tab-panel]");

    const activate = (id) => {
      buttons.forEach((b) => b.classList.toggle("is-active", b.dataset.tabBtn === id));
      panels.forEach((p) => {
        const isActive = p.dataset.tabPanel === id;
        p.classList.toggle("is-active", isActive);
        if (isActive) {
          loadLazyPanel(p);
        }
      });
    };

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => activate(btn.dataset.tabBtn));
    });

    const hashId = window.location.hash.replace("#", "");
    const hashTab = hashId && Array.from(buttons).some((b) => b.dataset.tabBtn === hashId)
      ? hashId
      : null;

    if (hashTab) {
      activate(hashTab);
    } else if (buttons.length > 0) {
      activate(buttons[0].dataset.tabBtn);
    }
  });
};

export { initTabs };
