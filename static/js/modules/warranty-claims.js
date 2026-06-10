/**
 * Warranty claim form — serial lookup, product pick (event delegation).
 */

import { createToast } from "./toast.js";

const formEl = () => document.querySelector("#warranty-claim-form");

const i18n = (key, fallback = "") => formEl()?.dataset[key] ?? fallback;

const lookupUrl = () => formEl()?.dataset.warrantyLookupUrl ?? "";

const productPickUrl = (id) => {
  const tpl = document.querySelector("#warranty-claim-form")?.dataset.warrantyProductPickTemplate;
  if (!tpl || !id) return "";
  return tpl.replace("/0/", `/${id}/`);
};

const setField = (id, value) => {
  const el = document.getElementById(id);
  if (el && value !== undefined && value !== null) {
    el.value = value;
  }
};

const applyLookup = (data, mode = "fill") => {
  setField("id_serial_number", data.serial_number);
  setField("id_product", data.product_id ?? "");
  setField("id_product_name", data.product_name);
  setField("id_product_code", data.product_code);
  setField("id_articul", data.articul);
  setField("id_sale_document", data.sale_document);
  setField("id_sale_date", data.sale_date);
  setField("id_warranty_until", data.warranty_until);
  const ps = document.getElementById("warranty-product-serial-id");
  if (ps) ps.value = data.product_serial_id ?? "";

  const statusEl = document.querySelector("[data-warranty-status]");
  if (statusEl) {
    if (data.warranty_status_label) {
      statusEl.textContent = data.warranty_status_label;
      statusEl.hidden = false;
      statusEl.classList.toggle("is-warranty-ok", data.is_under_warranty === true);
      statusEl.classList.toggle("is-warranty-expired", data.is_under_warranty === false);
    } else {
      statusEl.hidden = true;
      statusEl.textContent = "";
    }
  }

  const msg = document.querySelector("[data-warranty-lookup-msg]");
  if (msg) {
    if (data.found) {
      msg.textContent = "";
      msg.hidden = true;
    } else {
      msg.textContent = i18n(
        "i18nSerialNotFound",
        "Serial number not found in the registry.",
      );
      msg.hidden = false;
    }
  }

  if (data.found) {
    createToast(
      mode === "sale"
        ? i18n("i18nSaleFilled", "Sale data filled in")
        : i18n("i18nFieldsFilled", "Fields filled from serial number"),
      "success",
    );
    if (mode === "sale") {
      document.getElementById("id_sale_document")?.focus();
    }
  } else {
    createToast(i18n("i18nSerialNotFoundShort", "Serial number not found in the registry"), "warning");
  }
};

const fetchSerial = async (serial, mode = "fill") => {
  const base = lookupUrl();
  if (!base) {
    createToast(i18n("i18nConfigError", "Form configuration error. Reload the page."), "error");
    return;
  }
  if (!serial.trim()) {
    createToast(i18n("i18nEnterSerial", "Enter a serial number first"), "warning");
    document.querySelector("[data-warranty-serial]")?.focus();
    return;
  }

  const url = `${base}?serial=${encodeURIComponent(serial.trim())}`;
  let resp;
  try {
    resp = await fetch(url, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
  } catch {
    createToast(i18n("i18nNetworkError", "Network error. Please try again."), "error");
    return;
  }

  if (resp.status === 403) {
    createToast(i18n("i18nAccessDenied", "Access denied."), "error");
    return;
  }
  if (!resp.ok) {
    const lookupError = i18n("i18nLookupError", "Lookup error");
    createToast(`${lookupError} (${resp.status})`, "error");
    return;
  }

  const data = await resp.json();
  applyLookup(data, mode);
};

let delegationBound = false;

const bindDelegation = () => {
  if (delegationBound) return;
  delegationBound = true;

  document.body.addEventListener("click", (e) => {
    const fillBtn = e.target.closest("[data-warranty-fill-sn]");
    const saleBtn = e.target.closest("[data-warranty-find-sale]");
    if (fillBtn || saleBtn) {
      e.preventDefault();
      const form = (fillBtn || saleBtn).closest("#warranty-claim-form");
      const serial = form?.querySelector("[data-warranty-serial]")?.value ?? "";
      fetchSerial(serial, saleBtn ? "sale" : "fill");
      return;
    }

    const pickBtn = e.target.closest("[data-warranty-pick-product]");
    if (pickBtn) {
      e.preventDefault();
      const id = pickBtn.dataset.warrantyPickProduct;
      const url = productPickUrl(id);
      if (!url) return;
      fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then((resp) => (resp.ok ? resp.json() : null))
        .then((data) => {
          if (!data) return;
          setField("id_product", data.product_id ?? "");
          setField("id_product_name", data.product_name);
          setField("id_product_code", data.product_code);
          setField("id_articul", data.articul);
          if (data.warranty_until) setField("id_warranty_until", data.warranty_until);
          const results = document.getElementById("warranty-product-results");
          if (results) results.innerHTML = "";
          createToast(i18n("i18nProductPicked", "Product selected"), "success");
        });
      return;
    }

    const actionBtn = e.target.closest("[data-warranty-action]");
    if (actionBtn) {
      const actionInput = document.getElementById("warranty-form-action");
      if (actionInput) actionInput.value = actionBtn.dataset.warrantyAction ?? "save";
    }
  });

  document.body.addEventListener("change", (e) => {
    const noSerial = e.target.closest("[data-warranty-no-serial]");
    if (!noSerial) return;
    const form = noSerial.closest("#warranty-claim-form");
    const serialInput = form?.querySelector("[data-warranty-serial]");
    if (serialInput) {
      serialInput.disabled = noSerial.checked;
      serialInput.required = !noSerial.checked;
    }
  });
};

export const initWarrantyClaims = (root = document) => {
  bindDelegation();
  const form = root.querySelector?.("#warranty-claim-form") ?? document.getElementById("warranty-claim-form");
  if (!form) return;
  const noSerial = form.querySelector("[data-warranty-no-serial]");
  const serialInput = form.querySelector("[data-warranty-serial]");
  if (noSerial && serialInput) {
    serialInput.disabled = noSerial.checked;
    serialInput.required = !noSerial.checked;
  }
};

document.addEventListener("DOMContentLoaded", () => bindDelegation());
