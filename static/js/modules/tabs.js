/** Generic tab component. */

const initTabs = (root = document) => {
  root.querySelectorAll("[data-tabs]").forEach((tabsEl) => {
    const buttons = tabsEl.querySelectorAll("[data-tab-btn]");
    const panels = tabsEl.querySelectorAll("[data-tab-panel]");

    const activate = (id) => {
      buttons.forEach((b) => b.classList.toggle("is-active", b.dataset.tabBtn === id));
      panels.forEach((p) => p.classList.toggle("is-active", p.dataset.tabPanel === id));
    };

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => activate(btn.dataset.tabBtn));
    });

    // Activate first tab by default
    if (buttons.length > 0) activate(buttons[0].dataset.tabBtn);
  });
};

export { initTabs };
