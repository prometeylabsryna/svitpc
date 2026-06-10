/**
 * Shipping module:
 * - Delivery type toggle (NP / pickup)
 * - City/warehouse autocomplete via event delegation
 * - HTMX delivery cost refresh
 */

export const initShipping = (root = document) => {
  _initDeliveryToggle(root);
  _initAutocomplete(root);
};

const _initDeliveryToggle = (root) => {
  const form = root.querySelector(".checkout-delivery__form");
  if (!form) return;

  const npSection = root.getElementById("delivery-np-section");
  const pickupSection = root.getElementById("delivery-pickup-section");
  const npCost = root.getElementById("delivery-cost-container");

  const show = (el) => el?.classList.remove("delivery-section--hidden");
  const hide = (el) => el?.classList.add("delivery-section--hidden");

  const toggle = (type) => {
    if (type === "nova_poshta") {
      show(npSection); hide(pickupSection);
      show(npCost);
    } else if (type === "pickup") {
      hide(npSection); show(pickupSection);
      hide(npCost);
    }
    _setSectionFields(root, npSection, type === "nova_poshta");
    _setSectionFields(root, pickupSection, type === "pickup");
  };

  form.querySelectorAll("input[name='delivery_type']").forEach((radio) => {
    radio.addEventListener("change", () => toggle(radio.value));
  });

  const checked = form.querySelector("input[name='delivery_type']:checked");
  if (checked) toggle(checked.value);
};

const _setSectionFields = (root, section, enabled) => {
  if (!section) return;
  section.querySelectorAll("input, textarea, select").forEach((field) => {
    if (field.name === "delivery_type") return;
    field.disabled = !enabled;
  });
};

const _initAutocomplete = (root) => {
  root.addEventListener("click", (e) => {
    const cityBtn = e.target.closest("[data-city-name]");
    if (cityBtn) {
      const cityInput = root.getElementById("city");
      const cityRef = root.getElementById("city_ref");
      const whInput = root.getElementById("warehouse");
      const whRef = root.getElementById("warehouse_ref");
      if (cityInput) cityInput.value = cityBtn.dataset.cityName;
      if (cityRef) {
        cityRef.value = cityBtn.dataset.cityRef;
        cityRef.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (whInput) whInput.value = "";
      if (whRef) whRef.value = "";
      const cityContainer = root.getElementById("city-results");
      if (cityContainer) cityContainer.innerHTML = "";
      const whContainer = root.getElementById("warehouse-results");
      if (whContainer) whContainer.innerHTML = "";
      whInput?.dispatchEvent(new Event("input", { bubbles: true }));
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
