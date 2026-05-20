/**
 * Ecommerce dataLayer module.
 * Listens for custom events and fires GA4 Ecommerce pushes.
 * No inline scripts — event data is carried via CustomEvent.detail or data-* attrs.
 */

const dl = window.dataLayer ?? [];
window.dataLayer = dl;

/** Push an event object to dataLayer. */
const push = (obj) => dl.push(obj);

/** Read product JSON from a <meta name="ecommerce-purchase"> tag and fire purchase. */
const firePurchaseFromMeta = () => {
  const meta = document.querySelector('meta[name="ecommerce-purchase"]');
  if (!meta) return;
  try {
    const data = JSON.parse(meta.content);
    push({
      event: "purchase",
      ecommerce: {
        transaction_id: String(data.order_id),
        value: parseFloat(data.total),
        currency: "UAH",
        items: data.items ?? [],
      },
    });
  } catch {
    // invalid JSON — skip
  }
};

/** Fire view_item from a <meta name="ecommerce-product"> tag (product detail page). */
const fireViewItemFromMeta = () => {
  const meta = document.querySelector('meta[name="ecommerce-product"]');
  if (!meta) return;
  try {
    const p = JSON.parse(meta.content);
    push({
      event: "view_item",
      ecommerce: {
        currency: "UAH",
        value: parseFloat(p.price),
        items: [{ item_id: String(p.id), item_name: p.name, price: parseFloat(p.price) }],
      },
    });
  } catch {
    // skip
  }
};

/** Listen for cart:add custom event dispatched by cart module. */
document.addEventListener("cart:add", (e) => {
  const { id, name, price, qty } = e.detail ?? {};
  if (!id) return;
  push({
    event: "add_to_cart",
    ecommerce: {
      currency: "UAH",
      value: parseFloat(price) * (qty || 1),
      items: [{ item_id: String(id), item_name: name, price: parseFloat(price), quantity: qty || 1 }],
    },
  });
});

/** Listen for cart:remove. */
document.addEventListener("cart:remove", (e) => {
  const { id, name, price, qty } = e.detail ?? {};
  if (!id) return;
  push({
    event: "remove_from_cart",
    ecommerce: {
      currency: "UAH",
      items: [{ item_id: String(id), item_name: name, price: parseFloat(price), quantity: qty || 1 }],
    },
  });
});

/** Listen for checkout:begin. */
document.addEventListener("checkout:begin", () => {
  push({ event: "begin_checkout" });
});

// ── Init on page load ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  firePurchaseFromMeta();
  fireViewItemFromMeta();
});
