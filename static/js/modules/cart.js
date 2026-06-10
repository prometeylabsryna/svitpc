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

const parseHxTrigger = (xhr) => {
  try {
    const trigger = xhr?.getResponseHeader?.("HX-Trigger");
    return trigger ? JSON.parse(trigger) : null;
  } catch {
    return null;
  }
};

/**
 * Element-level init (quantity inputs handled by hx-trigger="change" on the
 * element itself — nothing extra needed here).
 */
const initCart = (_root = document) => {};

// cart_add_view returns 204 + HX-Trigger: {"cartUpdated": N, "toast": …} — no HTML body.
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail?.xhr;
  if (!xhr || xhr.status < 200 || xhr.status >= 300) return;

  const data = parseHxTrigger(xhr);
  if (!data) return;

  if ("cartUpdated" in data) updateCartBadge(data.cartUpdated);
});

export { initCart, updateCartBadge };
