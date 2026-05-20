/**
 * HTMX bridge — re-initializes JS components after HTMX swaps.
 * Listens to htmx:afterSwap and triggers module re-init.
 */

import { initCart } from "./cart.js";
import { initWishlist } from "./wishlist.js";
import { initCompare } from "./compare.js";
import { initGallery } from "./gallery.js";
import { initTabs } from "./tabs.js";
import { initFilterPanel } from "./filters.js";
import { openModal } from "./modal.js";

/** Run all initializers on a given root element. */
const initAll = (root = document) => {
  initCart(root);
  initWishlist(root);
  initCompare(root);
  initGallery(root);
  initTabs(root);
  initFilterPanel(root);
};

document.addEventListener("htmx:afterSwap", (e) => {
  const target = /** @type {CustomEvent} */ (e).detail?.target ?? document;

  // After product-grid swap: update count from the newly placed element
  if (target?.id === "product-grid") {
    const grid = document.getElementById("product-grid");
    const countEl = document.getElementById("sort-bar-count");
    if (grid && countEl) {
      countEl.textContent = grid.dataset.total ?? countEl.textContent;
    }
  }

  // Open modal when content is injected into #modal-container
  if (target?.id === "modal-container") {
    openModal();
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
