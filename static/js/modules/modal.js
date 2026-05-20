/**
 * Modal — manages #modal-container as an HTMX-powered overlay.
 *
 * Lifecycle:
 *   openModal()  → adds .modal-backdrop + .is-open, locks scroll, traps focus
 *   closeModal() → removes .is-open, unlocks scroll, clears innerHTML after fade
 *
 * Called externally by htmx-bridge after swap into #modal-container.
 * Close triggers: backdrop click, [data-modal-close] click, Escape key.
 */

const CLOSE_MS = 250; // matches --transition-base

let _prevFocus = null;

const getEl = () => document.getElementById("modal-container");

const openModal = () => {
  const el = getEl();
  if (!el) return;

  if (el.classList.contains("is-open")) {
    // Already open (e.g. success partial replaced the form) — just re-focus close btn
    el.querySelector("[data-modal-close]")?.focus();
    return;
  }

  _prevFocus = document.activeElement;
  el.classList.add("modal-backdrop", "is-open");
  document.body.classList.add("scroll-lock");
  el.setAttribute("aria-modal", "true");
  el.removeAttribute("hidden");

  // Focus close button first; if absent, first focusable element
  const focusTarget =
    el.querySelector("[data-modal-close]") ??
    el.querySelector("input, textarea, select, button, [tabindex]");
  focusTarget?.focus();
};

const closeModal = () => {
  const el = getEl();
  if (!el || !el.classList.contains("is-open")) return;

  el.classList.remove("is-open");
  document.body.classList.remove("scroll-lock");

  setTimeout(() => {
    if (!el.classList.contains("is-open")) {
      el.classList.remove("modal-backdrop");
      el.removeAttribute("aria-modal");
      el.innerHTML = "";
    }
  }, CLOSE_MS);

  _prevFocus?.focus();
  _prevFocus = null;
};

const initModal = () => {
  const el = getEl();
  if (!el) return;

  // Backdrop click or [data-modal-close] button
  el.addEventListener("click", (e) => {
    if (e.target === el || e.target.closest("[data-modal-close]")) {
      closeModal();
    }
  });

  // ESC key — only when modal is open
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && el.classList.contains("is-open")) {
      e.preventDefault();
      closeModal();
    }
  });
};

document.addEventListener("DOMContentLoaded", initModal);

export { openModal, closeModal };
