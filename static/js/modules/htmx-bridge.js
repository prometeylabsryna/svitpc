/**
 * HTMX bridge — re-initializes JS components after HTMX swaps.
 * Listens to htmx:afterSwap and triggers module re-init.
 */

import "./toast.js";
import "./svitik.js";
import { initCart } from "./cart.js";
import { initWishlist } from "./wishlist.js";
import { initCompare } from "./compare.js";
import { initGallery } from "./gallery.js";
import { initTabs } from "./tabs.js";
import { initFilterPanel } from "./filters.js";
import { closeModal, openModal } from "./modal.js";
import { initPasswordToggle } from "./password-toggle.js";
import { initWarrantyClaims } from "./warranty-claims.js";

/** Scroll modal/page to the first invalid field after a failed form submit. */
const scrollToFirstFormError = (root) => {
  const invalid = root.querySelector(".is-invalid");
  const anchor =
    invalid?.closest(".form-field") ??
    root.querySelector(".auth-form__alert") ??
    root.querySelector(".form-error")?.closest(".form-field");
  anchor?.scrollIntoView({ behavior: "smooth", block: "center" });
};

/** Run all initializers on a given root element. */
const initAll = (root = document) => {
  initCart(root);
  initWishlist(root);
  initCompare(root);
  initGallery(root);
  initTabs(root);
  initFilterPanel(root);
  initPasswordToggle(root);
  initWarrantyClaims(root);
};

document.body.addEventListener("modalClose", () => closeModal());

document.addEventListener("htmx:afterSwap", (e) => {
  const detail = /** @type {CustomEvent} */ (e).detail;
  const target = detail?.target ?? document;
  const xhr = detail?.xhr;

  // After product-grid swap: update count from the newly placed element
  if (target?.id === "product-grid") {
    const grid = document.getElementById("product-grid");
    const countEl = document.getElementById("sort-bar-count");
    if (grid && countEl) {
      countEl.textContent = grid.dataset.total ?? countEl.textContent;
    }
  }

  // OOB filter-form swaps replace the whole <form> — re-bind collapse toggles.
  if (target?.matches?.("form.filters-panel, form[data-catalog-filters]")) {
    initFilterPanel(target);
  }

  if (target?.id === "modal-container") {
    // Registration success uses HX-Reswap: none — form stays in DOM; do not re-open.
    if (xhr?.getResponseHeader?.("HX-Reswap") === "none") {
      closeModal();
    } else if (target.querySelector(".modal-dialog")) {
      openModal();
      if (
        target.querySelector(".auth-form__alert")
        || target.querySelector(".warranty-form .is-invalid")
      ) {
        requestAnimationFrame(() => scrollToFirstFormError(target));
      }
    }
  }

  initAll(target);
});

document.addEventListener("htmx:afterSettle", () => {
  // Scroll to top on full-page swap
  if (document.querySelector("[data-scroll-top]")) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
});

// Initial page load
initAll();

export { initAll };
