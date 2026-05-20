/**
 * Cart module — handles add-to-cart, quantity, delete.
 * All mutations go through HTMX (no direct fetch here).
 */

const CART_BADGE_SEL = "[data-cart-count]";

const updateCartBadge = (count) => {
  document.querySelectorAll(CART_BADGE_SEL).forEach((el) => {
    el.textContent = count;
    el.hidden = count === 0;
  });
};

/**
 * Element-level init (quantity inputs handled by hx-trigger="change" on the
 * element itself — nothing extra needed here).
 */
const initCart = (_root = document) => {};

// Single module-level listener: update cart badge from HX-Trigger response header.
// cart_add_view returns 204 + HX-Trigger: {"cartUpdated": N} — no HTML body.
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail?.xhr;
  if (!xhr) return;
  try {
    const trigger = xhr.getResponseHeader?.("HX-Trigger");
    if (!trigger) return;
    const data = JSON.parse(trigger);
    if ("cartUpdated" in data) updateCartBadge(data.cartUpdated);
  } catch {
    // malformed header — ignore
  }
});

export { initCart, updateCartBadge };
