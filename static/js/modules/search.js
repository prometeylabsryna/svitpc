/** Live search — HTMX triggers the request, this module handles UI state. */

const initSearch = (root = document) => {
  const input = root.querySelector("[data-search-input]");
  const results = root.querySelector("[data-search-results]");
  if (!input || !results) return;

  // Hide results when clicking outside
  document.addEventListener("click", (e) => {
    if (!input.contains(/** @type {Node} */ (e.target)) && !results.contains(/** @type {Node} */ (e.target))) {
      results.hidden = true;
    }
  });

  // Show results when input focused and has value
  input.addEventListener("focus", () => {
    if (input.value.trim().length > 1) results.hidden = false;
  });

  // HTMX puts results in; show the dropdown
  document.addEventListener("htmx:afterSwap", (e) => {
    if (e.detail?.target === results) results.hidden = false;
  });

  // Keyboard nav
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      results.hidden = true;
      input.blur();
    }
  });
};

export { initSearch };
