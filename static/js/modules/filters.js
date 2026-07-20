/** Filter panel — collapsible groups + mobile sidebar + "more filters" toggle. */

const initFilterPanel = (root = document) => {
  // Collapsible groups — use DOM traversal instead of getElementById
  // to correctly handle duplicate filter panels (desktop + mobile sidebar).
  // Guard with data-init: без нього повторний initFilterPanel (HTMX OOB +
  // initAll) вішає 2 listeners → клік відкриває і одразу закриває групу.
  root.querySelectorAll("[data-filter-toggle]:not([data-filter-toggle-init])").forEach((btn) => {
    const items = btn.closest(".filter-group")?.querySelector(".filter-group__items");
    if (!items) return;

    btn.dataset.filterToggleInit = "1";
    items.hidden = btn.getAttribute("aria-expanded") !== "true";
    btn.addEventListener("click", () => {
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!expanded));
      items.hidden = expanded;
    });
  });

  // "More filters" toggle — guard with data-init to prevent duplicate listeners
  root.querySelectorAll("[data-filters-more]:not([data-filters-more-init])").forEach((btn) => {
    btn.dataset.filtersMoreInit = "1";
    btn.addEventListener("click", () => {
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!expanded));
      const panel = btn.closest(".filters-panel");
      panel?.querySelectorAll(".filter-group--extra").forEach((g) => {
        g.classList.toggle("is-visible", !expanded);
      });
    });
  });

  // "More subcategories" toggle — same DOM-relative approach (no id/for:
  // subcategories render inside both desktop and mobile panels).
  root.querySelectorAll("[data-subcats-more]:not([data-subcats-more-init])").forEach((btn) => {
    btn.dataset.subcatsMoreInit = "1";
    const group = btn.closest(".filter-group--subcats");
    btn.addEventListener("click", () => {
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!expanded));
      group?.querySelectorAll(".filter-subcats__item--extra").forEach((li) => {
        li.classList.toggle("is-visible", !expanded);
      });
    });
  });

  // Mobile sidebar open/close
  const openBtn = root.querySelector("[data-filters-open]");
  const closeBtn = root.querySelector("[data-filters-close]");
  const backdrop = root.querySelector("[data-filters-backdrop]");
  const sidebar = root.querySelector("[data-filters-sidebar]");

  const open = () => sidebar?.classList.add("is-open");
  const close = () => sidebar?.classList.remove("is-open");

  openBtn?.addEventListener("click", open);
  closeBtn?.addEventListener("click", close);
  backdrop?.addEventListener("click", close);
};

export { initFilterPanel };
