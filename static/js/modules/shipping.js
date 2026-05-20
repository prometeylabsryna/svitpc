/**
 * Shipping module:
 * - Delivery type toggle (NP / Ukrposhta / pickup)
 * - City/warehouse autocomplete via event delegation
 * - HTMX warehouse include update on city selection
 */

export const initShipping = (root = document) => {
  _initDeliveryToggle(root);
  _initAutocomplete(root);
};

const _initDeliveryToggle = (root) => {
  const form = root.querySelector(".checkout-delivery__form");
  if (!form) return;

  const npSection = root.getElementById("delivery-np-section");
  const upSection = root.getElementById("delivery-up-section");
  const pickupSection = root.getElementById("delivery-pickup-section");

  const show = (el) => el?.classList.remove("delivery-section--hidden");
  const hide = (el) => el?.classList.add("delivery-section--hidden");

  const toggle = (type) => {
    if (type === "nova_poshta") {
      show(npSection); hide(upSection); hide(pickupSection);
    } else if (type === "ukrposhta") {
      hide(npSection); show(upSection); hide(pickupSection);
    } else if (type === "pickup") {
      hide(npSection); hide(upSection); show(pickupSection);
    }
  };

  form.querySelectorAll("input[name='delivery_type']").forEach((radio) => {
    radio.addEventListener("change", () => toggle(radio.value));
  });

  // Initial state on page load
  const checked = form.querySelector("input[name='delivery_type']:checked");
  if (checked) toggle(checked.value);
};

const _initAutocomplete = (root) => {
  root.addEventListener("click", (e) => {
    const cityBtn = e.target.closest("[data-city-name]");
    if (cityBtn) {
      const cityInput = root.getElementById("city");
      const cityRef = root.getElementById("city_ref");
      if (cityInput) cityInput.value = cityBtn.dataset.cityName;
      if (cityRef) {
        cityRef.value = cityBtn.dataset.cityRef;
        // Re-trigger HTMX on city_ref change so warehouse list refreshes
        cityRef.dispatchEvent(new Event("change", { bubbles: true }));
      }
      const container = root.getElementById("city-results");
      if (container) container.innerHTML = "";
      return;
    }

    const whBtn = e.target.closest("[data-warehouse-name]");
    if (whBtn) {
      const whInput = root.getElementById("warehouse");
      const whRef = root.getElementById("warehouse_ref");
      if (whInput) whInput.value = whBtn.dataset.warehouseName;
      if (whRef) {
        whRef.value = whBtn.dataset.warehouseRef;
        whRef.dispatchEvent(new Event("change", { bubbles: true }));
      }
      const container = root.getElementById("warehouse-results");
      if (container) container.innerHTML = "";
    }
  });
};
