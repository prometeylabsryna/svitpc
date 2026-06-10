/**
 * Wishlist module — toggle active state on wishlist buttons.
 * Uses document-level event delegation to avoid duplicate listeners
 * when initAll() is called after HTMX swaps.
 */

const pulseActive = (elt) => {
  elt.classList.remove("is-animating");
  void elt.offsetWidth;
  elt.classList.add("is-animating");
  elt.addEventListener("animationend", () => elt.classList.remove("is-animating"), { once: true });
};

/** Apply active state to all toggles for the same product. */
const setWishlistActive = (elt, active) => {
  const productId = elt?.dataset?.productId;
  const targets = productId
    ? document.querySelectorAll(`[data-wishlist-toggle][data-product-id="${productId}"]`)
    : [elt];

  targets.forEach((btn) => {
    if (!btn) return;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-pressed", String(active));
    if (active) pulseActive(btn);
  });
};

/** Remove product card from wishlist page after toggle-off. */
const removeCardFromWishlistPage = (btn) => {
  const section = document.querySelector("[data-wishlist-page]");
  if (!section) return;

  const card = btn.closest(".product-card");
  if (!card) return;

  const grid = section.querySelector("[data-wishlist-grid]");
  card.remove();

  if (grid && !grid.querySelector(".product-card")) {
    grid.remove();
    const empty = section.querySelector("[data-wishlist-empty]");
    if (empty) empty.hidden = false;
  }
};

const parseHxTrigger = (xhr) => {
  try {
    const trigger = xhr?.getResponseHeader?.("HX-Trigger");
    return trigger ? JSON.parse(trigger) : null;
  } catch {
    return null;
  }
};

// No per-element setup needed; delegation handles dynamically added buttons.
const initWishlist = (_root = document) => {};

// Optimistic UI before request completes.
document.addEventListener("htmx:beforeRequest", (e) => {
  const elt = e.detail?.elt;
  if (!elt?.hasAttribute("data-wishlist-toggle")) return;
  const next = elt.getAttribute("aria-pressed") !== "true";
  setWishlistActive(elt, next);
});

// Server returns 204 + HX-Trigger: {"wishlistUpdated": N, "wishlistActive": bool}
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail?.xhr;
  const elt = e.detail?.elt;
  if (!xhr || !elt?.hasAttribute("data-wishlist-toggle")) return;

  const data = parseHxTrigger(xhr);
  const ok = xhr.status >= 200 && xhr.status < 300;

  if (!ok) {
    setWishlistActive(elt, elt.getAttribute("aria-pressed") !== "true");
    return;
  }

  if (!data) return;

  if ("wishlistActive" in data) {
    const active = Boolean(data.wishlistActive);
    setWishlistActive(elt, active);
    if (!active) removeCardFromWishlistPage(elt);
  }

  if ("wishlistUpdated" in data) {
    const count = data.wishlistUpdated;
    document.querySelectorAll("[data-wishlist-count]").forEach((el) => {
      el.textContent = count;
      el.hidden = count === 0;
    });
  }
});

export { initWishlist };
