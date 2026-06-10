/**
 * Compare module — toggle compare button state and update header badge.
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
const setCompareActive = (elt, active) => {
  if (!elt?.hasAttribute("data-compare-toggle")) return;

  const productId = elt.dataset.productId;
  const targets = productId
    ? document.querySelectorAll(`[data-compare-toggle][data-product-id="${productId}"]`)
    : [elt];

  targets.forEach((btn) => {
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-pressed", String(active));
    if (active) pulseActive(btn);
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

// No per-element setup needed; delegation handles dynamically added buttons.
const initCompare = (_root = document) => {};

const isCompareToggle = (elt) => elt?.hasAttribute("data-compare-toggle");

// Optimistic UI before request completes.
document.addEventListener("htmx:beforeRequest", (e) => {
  const elt = e.detail?.elt;
  if (!isCompareToggle(elt)) return;
  const next = elt.getAttribute("aria-pressed") !== "true";
  setCompareActive(elt, next);
});

// Server returns 204 + HX-Trigger: {"compareUpdated": N, "compareActive": bool}
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail?.xhr;
  const elt = e.detail?.elt;
  const isCompareAction =
    isCompareToggle(elt) ||
    elt?.hasAttribute("data-compare-remove") ||
    elt?.hasAttribute("data-compare-clear");
  if (!xhr || !isCompareAction) return;

  const data = parseHxTrigger(xhr);
  const ok = xhr.status >= 200 && xhr.status < 300;

  if (isCompareToggle(elt)) {
    if (!ok) {
      setCompareActive(elt, elt.getAttribute("aria-pressed") !== "true");
      return;
    }
    if (data && "compareActive" in data) {
      setCompareActive(elt, Boolean(data.compareActive));
    }
  } else if (!ok) {
    return;
  }

  if (!data || !("compareUpdated" in data)) return;

  const count = data.compareUpdated;
  document.querySelectorAll("[data-compare-count]").forEach((el) => {
    el.textContent = count;
    el.hidden = count === 0;
  });
});

export { initCompare };
