/** Filter panel — collapsible groups + mobile sidebar + "more filters" toggle.

Event delegation on each panel: HTMX OOB замінює <form>, тож per-button
addEventListener легко подвоюється (клік = open+close). Один listener на
panel з data-filters-panel-init — безпечно при будь-якій кількості init*.
*/

const syncGroupVisibility = (btn) => {
  const items = btn.closest(".filter-group")?.querySelector(".filter-group__items");
  if (!items) return;
  items.hidden = btn.getAttribute("aria-expanded") !== "true";
};

const onPanelClick = (e) => {
  const panel = e.currentTarget;

  const toggleBtn = e.target.closest("[data-filter-toggle]");
  if (toggleBtn && panel.contains(toggleBtn)) {
    e.preventDefault();
    const items = toggleBtn.closest(".filter-group")?.querySelector(".filter-group__items");
    if (!items) return;
    const expanded = toggleBtn.getAttribute("aria-expanded") === "true";
    toggleBtn.setAttribute("aria-expanded", String(!expanded));
    items.hidden = expanded;
    return;
  }

  const moreBtn = e.target.closest("[data-filters-more]");
  if (moreBtn && panel.contains(moreBtn)) {
    e.preventDefault();
    const expanded = moreBtn.getAttribute("aria-expanded") === "true";
    moreBtn.setAttribute("aria-expanded", String(!expanded));
    panel.querySelectorAll(".filter-group--extra").forEach((g) => {
      g.classList.toggle("is-visible", !expanded);
    });
    return;
  }

  const subcatsBtn = e.target.closest("[data-subcats-more]");
  if (subcatsBtn && panel.contains(subcatsBtn)) {
    e.preventDefault();
    const group = subcatsBtn.closest(".filter-group--subcats");
    const expanded = subcatsBtn.getAttribute("aria-expanded") === "true";
    subcatsBtn.setAttribute("aria-expanded", String(!expanded));
    group?.querySelectorAll(".filter-subcats__item--extra").forEach((li) => {
      li.classList.toggle("is-visible", !expanded);
    });
  }
};

const initFilterPanel = (root = document) => {
  // Sync initial open/closed from aria-expanded (also after OOB swap).
  root.querySelectorAll("[data-filter-toggle]").forEach(syncGroupVisibility);

  // Panels: filters form OR subcats block (subcats live outside the form).
  const panels = root.querySelectorAll(
    "form.filters-panel, form[data-catalog-filters], .filter-group--subcats",
  );
  panels.forEach((panel) => {
    if (panel.dataset.filtersPanelInit === "1") return;
    panel.dataset.filtersPanelInit = "1";
    panel.addEventListener("click", onPanelClick);
  });

  // If root itself is a panel (OOB swap target = the <form>).
  if (
    root !== document
    && root.matches?.("form.filters-panel, form[data-catalog-filters], .filter-group--subcats")
    && root.dataset.filtersPanelInit !== "1"
  ) {
    root.dataset.filtersPanelInit = "1";
    root.addEventListener("click", onPanelClick);
  }

  // Mobile sidebar open/close — bind once per control.
  const openBtn = root.querySelector("[data-filters-open]");
  const closeBtn = root.querySelector("[data-filters-close]");
  const backdrop = root.querySelector("[data-filters-backdrop]");
  const sidebar = root.querySelector("[data-filters-sidebar]");

  const open = () => sidebar?.classList.add("is-open");
  const close = () => sidebar?.classList.remove("is-open");

  if (openBtn && openBtn.dataset.filtersOpenInit !== "1") {
    openBtn.dataset.filtersOpenInit = "1";
    openBtn.addEventListener("click", open);
  }
  if (closeBtn && closeBtn.dataset.filtersCloseInit !== "1") {
    closeBtn.dataset.filtersCloseInit = "1";
    closeBtn.addEventListener("click", close);
  }
  if (backdrop && backdrop.dataset.filtersBackdropInit !== "1") {
    backdrop.dataset.filtersBackdropInit = "1";
    backdrop.addEventListener("click", close);
  }
};

export { initFilterPanel };
