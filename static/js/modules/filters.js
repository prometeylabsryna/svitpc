/**
 * Filter panel — collapsible groups + mobile drawer.
 *
 * One document-level click listener (delegation). HTMX OOB replaces <form>
 * nodes freely; we never re-bind per-button handlers, so toggles cannot
 * "work only once" or open+close in a single click.
 */

const FILTER_PANEL_SEL = "form.filters-panel, form[data-catalog-filters], .filter-group--subcats";

let documentDelegationReady = false;
let mobileDelegationReady = false;

const syncGroupVisibility = (btn) => {
  const items = btn.closest(".filter-group")?.querySelector(".filter-group__items");
  if (!items) return;
  items.hidden = btn.getAttribute("aria-expanded") !== "true";
};

const onDocumentClick = (e) => {
  const toggleBtn = e.target.closest("[data-filter-toggle]");
  if (toggleBtn?.closest(FILTER_PANEL_SEL)) {
    e.preventDefault();
    const items = toggleBtn.closest(".filter-group")?.querySelector(".filter-group__items");
    if (!items) return;
    const expanded = toggleBtn.getAttribute("aria-expanded") === "true";
    toggleBtn.setAttribute("aria-expanded", String(!expanded));
    items.hidden = expanded;
    return;
  }

  const moreBtn = e.target.closest("[data-filters-more]");
  if (moreBtn?.closest(FILTER_PANEL_SEL)) {
    e.preventDefault();
    const panel = moreBtn.closest(FILTER_PANEL_SEL);
    const expanded = moreBtn.getAttribute("aria-expanded") === "true";
    moreBtn.setAttribute("aria-expanded", String(!expanded));
    panel?.querySelectorAll(".filter-group--extra").forEach((g) => {
      g.classList.toggle("is-visible", !expanded);
    });
    return;
  }

  const subcatsBtn = e.target.closest("[data-subcats-more]");
  if (subcatsBtn?.closest(".filter-group--subcats")) {
    e.preventDefault();
    const group = subcatsBtn.closest(".filter-group--subcats");
    const expanded = subcatsBtn.getAttribute("aria-expanded") === "true";
    subcatsBtn.setAttribute("aria-expanded", String(!expanded));
    group?.querySelectorAll(".filter-subcats__item--extra").forEach((li) => {
      li.classList.toggle("is-visible", !expanded);
    });
  }
};

const onMobileClick = (e) => {
  if (e.target.closest("[data-filters-open]")) {
    document.querySelector("[data-filters-sidebar]")?.classList.add("is-open");
    return;
  }
  if (e.target.closest("[data-filters-close], [data-filters-backdrop]")) {
    document.querySelector("[data-filters-sidebar]")?.classList.remove("is-open");
  }
};

/**
 * Sync aria-expanded → hidden for groups in `root`, and ensure document
 * listeners exist (idempotent).
 */
const initFilterPanel = (root = document) => {
  const scope = root?.querySelectorAll ? root : document;
  scope.querySelectorAll?.("[data-filter-toggle]")?.forEach(syncGroupVisibility);
  // When root itself is a freshly swapped form, sync its toggles too.
  if (root?.querySelectorAll && root.matches?.(FILTER_PANEL_SEL)) {
    root.querySelectorAll("[data-filter-toggle]").forEach(syncGroupVisibility);
  }

  if (!documentDelegationReady) {
    documentDelegationReady = true;
    document.addEventListener("click", onDocumentClick);
  }
  if (!mobileDelegationReady) {
    mobileDelegationReady = true;
    document.addEventListener("click", onMobileClick);
  }
};

export { initFilterPanel };
