/**
 * Ecommerce dataLayer module.
 * Listens for HTMX HX-Trigger events and meta tags — no inline scripts.
 */

const dl = window.dataLayer ?? [];
window.dataLayer = dl;

/** Push an event object to dataLayer. */
const push = (obj) => dl.push(obj);

/** Prevent duplicate meta-based events (e.g. HTMX afterSettle on category filters). */
const trackedMeta = new Set();

const parseMetaJson = (name) => {
  const meta = document.querySelector(`meta[name="${name}"]`);
  if (!meta?.content) return null;
  try {
    return JSON.parse(meta.content);
  } catch {
    return null;
  }
};

const trackMetaOnce = (key, fn) => {
  if (trackedMeta.has(key)) return;
  trackedMeta.add(key);
  fn();
};

/** Fire purchase from checkout success meta tag. */
const firePurchaseFromMeta = () => {
  const meta = document.querySelector('meta[name="ecommerce-purchase"]');
  if (!meta) return;
  trackMetaOnce(`purchase:${meta.content}`, () => {
    const data = parseMetaJson("ecommerce-purchase");
    if (!data) return;
    push({
      event: "purchase",
      ecommerce: {
        transaction_id: String(data.order_id),
        value: parseFloat(data.total),
        currency: "UAH",
        items: data.items ?? [],
      },
    });
  });
};

/** Fire view_item from product detail meta tag. */
const fireViewItemFromMeta = () => {
  const meta = document.querySelector('meta[name="ecommerce-product"]');
  if (!meta) return;
  trackMetaOnce(`view_item:${meta.content}`, () => {
    const data = parseMetaJson("ecommerce-product");
    if (!data) return;
    push({
      event: "view_item",
      ecommerce: {
        currency: "UAH",
        value: parseFloat(data.price),
        items: [{
          item_id: String(data.id),
          item_name: data.name,
          price: parseFloat(data.price),
          quantity: 1,
        }],
      },
    });
  });
};

/** Fire view_item_list from category/list meta tag. */
const fireViewItemListFromMeta = () => {
  const meta = document.querySelector('meta[name="ecommerce-list"]');
  if (!meta) return;
  trackMetaOnce(`view_item_list:${meta.content}`, () => {
    const data = parseMetaJson("ecommerce-list");
    if (!data?.items?.length) return;
    const value = data.items.reduce(
      (sum, item) => sum + parseFloat(item.price) * (item.quantity || 1),
      0,
    );
    push({
      event: "view_item_list",
      ecommerce: {
        item_list_id: data.list_id,
        item_list_name: data.list_name,
        currency: "UAH",
        value,
        items: data.items,
      },
    });
  });
};

/** Fire begin_checkout when checkout step 1 meta is present. */
const fireBeginCheckoutFromMeta = () => {
  const meta = document.querySelector('meta[name="ecommerce-checkout"]');
  if (!meta || meta.content !== "begin") return;
  trackMetaOnce("begin_checkout", () => {
    push({ event: "begin_checkout" });
  });
};

const trackCartEvent = (eventName, detail) => {
  const { id, name, price, qty } = detail ?? {};
  if (!id) return;
  const quantity = qty || 1;
  push({
    event: eventName,
    ecommerce: {
      currency: "UAH",
      value: parseFloat(price) * quantity,
      items: [{
        item_id: String(id),
        item_name: name,
        price: parseFloat(price),
        quantity,
      }],
    },
  });
};

/** Run all page-level ecommerce events (meta tags). */
const firePageEvents = () => {
  firePurchaseFromMeta();
  fireViewItemFromMeta();
  fireViewItemListFromMeta();
  fireBeginCheckoutFromMeta();
};

document.addEventListener("cart:add", (e) => {
  trackCartEvent("add_to_cart", e.detail);
});

document.addEventListener("cart:remove", (e) => {
  trackCartEvent("remove_from_cart", e.detail);
});

document.addEventListener("checkout:begin", () => {
  push({ event: "begin_checkout" });
});

document.addEventListener("DOMContentLoaded", firePageEvents);

/** HTMX modal success (1-click buy) injects purchase meta after initial load. */
document.addEventListener("htmx:afterSettle", (e) => {
  const target = e.detail?.target;
  if (target?.querySelector?.('meta[name="ecommerce-purchase"]')) {
    firePurchaseFromMeta();
  }
});

export { push, firePageEvents };
