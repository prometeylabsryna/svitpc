/**
 * Wishlist module — toggle active state on wishlist buttons.
 * Uses document-level event delegation to avoid duplicate listeners
 * when initAll() is called after HTMX swaps.
 */

// No per-element setup needed; delegation handles dynamically added buttons.
const initWishlist = (_root = document) => {};

// Single module-level listener.
// Server returns 204 + HX-Trigger: {"wishlistUpdated": N, "wishlistActive": bool}
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail?.xhr;
  const elt = e.detail?.elt;
  if (!xhr || !elt?.hasAttribute("data-wishlist-toggle")) return;
  if (xhr.status < 200 || xhr.status >= 300) return;

  try {
    const trigger = xhr.getResponseHeader?.("HX-Trigger");
    if (!trigger) return;
    const data = JSON.parse(trigger);

    if ("wishlistActive" in data) {
      elt.classList.toggle("is-active", Boolean(data.wishlistActive));
    }
    if ("wishlistUpdated" in data) {
      const count = data.wishlistUpdated;
      document.querySelectorAll("[data-wishlist-count]").forEach((el) => {
        el.textContent = count;
        el.hidden = count === 0;
      });
    }
  } catch {
    // malformed header — ignore
  }
});

export { initWishlist };
