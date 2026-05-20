/**
 * Compare module — toggle compare button state and update header badge.
 * Uses document-level event delegation to avoid duplicate listeners
 * when initAll() is called after HTMX swaps.
 */

// No per-element setup needed; delegation handles dynamically added buttons.
const initCompare = (_root = document) => {};

// Single module-level listener.
// Server returns 204 + HX-Trigger: {"compareUpdated": N}
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail?.xhr;
  const elt = e.detail?.elt;
  if (!xhr || !elt?.hasAttribute("data-compare-toggle")) return;
  if (xhr.status < 200 || xhr.status >= 300) return;

  try {
    const trigger = xhr.getResponseHeader?.("HX-Trigger");
    if (!trigger) return;
    const data = JSON.parse(trigger);

    if ("compareUpdated" in data) {
      const count = data.compareUpdated;
      document.querySelectorAll("[data-compare-count]").forEach((el) => {
        el.textContent = count;
        el.hidden = count === 0;
      });
      // Toggle active state on the clicked button.
      // If count increased the product was added; if decreased — removed.
      // Simplest reliable signal: just toggle the class on success.
      elt.classList.toggle("is-active");
    }
  } catch {
    // malformed header — ignore
  }
});

export { initCompare };
