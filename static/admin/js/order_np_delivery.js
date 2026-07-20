/**
 * Nova Poshta city/warehouse autocomplete for Order admin form.
 */
(function () {
  const DELIVERY_NP = "nova_poshta";
  const CITIES_URL = "/shipping/np/cities/";
  const WAREHOUSES_URL = "/shipping/np/warehouses/";
  const DEBOUNCE_MS = 400;

  const debounce = (fn, delay) => {
    let timer = null;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), delay);
    };
  };

  const fieldRow = (form, name) =>
    form.querySelector(`.field-${name}`) ||
    form.querySelector(`[class*="field-${name}"]`);

  const createResults = (input) => {
    const box = document.createElement("div");
    box.className = "np-admin-autocomplete";
    box.setAttribute("role", "listbox");
    input.insertAdjacentElement("afterend", box);
    return box;
  };

  const clearResults = (box) => {
    box.innerHTML = "";
    box.hidden = true;
  };

  const showResults = (box) => {
    box.hidden = false;
  };

  const mountButtons = (box, nodes, onSelect) => {
    box.innerHTML = "";
    nodes.forEach((node) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "np-admin-autocomplete__option";
      btn.textContent = node.label;
      btn.addEventListener("click", () => onSelect(node));
      box.appendChild(btn);
    });
    box.hidden = nodes.length === 0;
  };

  const parseCityOptions = (html) => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    return Array.from(doc.querySelectorAll("[data-city-name]")).map((el) => ({
      label: el.textContent.trim(),
      name: el.dataset.cityName || "",
      ref: el.dataset.cityRef || "",
    }));
  };

  const parseWarehouseOptions = (html) => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    return Array.from(doc.querySelectorAll("[data-warehouse-name]")).map((el) => ({
      label: el.textContent.trim(),
      name: el.dataset.warehouseName || "",
      ref: el.dataset.warehouseRef || "",
    }));
  };

  const fetchHtml = async (url) => {
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "text/html" },
    });
    if (!response.ok) {
      return "";
    }
    return response.text();
  };

  const toggleDeliveryFields = (form, deliveryType) => {
    const npFields = ["city", "city_ref", "warehouse", "warehouse_ref"];

    npFields.forEach((name) => {
      const row = fieldRow(form, name);
      if (row) {
        row.hidden = deliveryType !== DELIVERY_NP;
      }
    });
  };

  const initOrderNpDelivery = (form) => {
    const deliveryType = form.querySelector("#id_delivery_type");
    const cityInput = form.querySelector("#id_city");
    const cityRefInput = form.querySelector("#id_city_ref");
    const warehouseInput = form.querySelector("#id_warehouse");
    const warehouseRefInput = form.querySelector("#id_warehouse_ref");

    if (!deliveryType || !cityInput || !cityRefInput || !warehouseInput || !warehouseRefInput) {
      return;
    }

    const cityResults = createResults(cityInput);
    const warehouseResults = createResults(warehouseInput);

    const resetWarehouse = () => {
      warehouseInput.value = "";
      warehouseRefInput.value = "";
      clearResults(warehouseResults);
    };

    const onCityInput = debounce(async () => {
      cityRefInput.value = "";
      resetWarehouse();
      const query = cityInput.value.trim();
      if (query.length < 2) {
        clearResults(cityResults);
        return;
      }
      const html = await fetchHtml(`${CITIES_URL}?city=${encodeURIComponent(query)}`);
      const options = parseCityOptions(html);
      mountButtons(cityResults, options, (option) => {
        cityInput.value = option.name;
        cityRefInput.value = option.ref;
        clearResults(cityResults);
        resetWarehouse();
        warehouseInput.focus();
        warehouseInput.dispatchEvent(new Event("input", { bubbles: true }));
      });
      showResults(cityResults);
    }, DEBOUNCE_MS);

    const onWarehouseInput = debounce(async () => {
      warehouseRefInput.value = "";
      const cityRef = cityRefInput.value.trim();
      if (!cityRef) {
        clearResults(warehouseResults);
        return;
      }
      const query = warehouseInput.value.trim();
      const params = new URLSearchParams({ city_ref: cityRef });
      if (query) {
        params.set("warehouse", query);
      }
      const html = await fetchHtml(`${WAREHOUSES_URL}?${params.toString()}`);
      const options = parseWarehouseOptions(html);
      mountButtons(warehouseResults, options, (option) => {
        warehouseInput.value = option.name;
        warehouseRefInput.value = option.ref;
        clearResults(warehouseResults);
      });
      showResults(warehouseResults);
    }, DEBOUNCE_MS);

    cityInput.addEventListener("input", onCityInput);
    warehouseInput.addEventListener("input", onWarehouseInput);

    deliveryType.addEventListener("change", () => {
      toggleDeliveryFields(form, deliveryType.value);
    });

    document.addEventListener("click", (event) => {
      if (!form.contains(event.target)) {
        clearResults(cityResults);
        clearResults(warehouseResults);
      }
    });

    toggleDeliveryFields(form, deliveryType.value);
  };

  const initAll = () => {
    const form = document.getElementById("order_form");
    if (form) {
      initOrderNpDelivery(form);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
