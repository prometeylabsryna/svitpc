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
/** True when pointer down started on the backdrop (not the dialog). */
let _backdropPointerDown = false;

const getEl = () => document.getElementById("modal-container");

const firstFocusable = (el) =>
  el.querySelector(
    ".modal-dialog .is-invalid, .modal-dialog input, .modal-dialog textarea, .modal-dialog select",
  ) ?? el.querySelector("[data-modal-close]");

const openModal = () => {
  const el = getEl();
  if (!el) return;

  if (el.classList.contains("is-open")) {
    firstFocusable(el)?.focus();
    return;
  }

  _prevFocus = document.activeElement;
  el.classList.add("modal-backdrop", "is-open");
  document.body.classList.add("scroll-lock");
  el.setAttribute("aria-modal", "true");
  el.removeAttribute("hidden");

  firstFocusable(el)?.focus();
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

  const isBackdropTarget = (target) => target === el;

  // Track pointer down on backdrop only — avoids closing when text/date selection
  // ends outside the dialog (mousedown in form, mouseup on backdrop).
  el.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const inDialog = e.target.closest(".modal-dialog");
    _backdropPointerDown = !inDialog && isBackdropTarget(e.target);
  });

  el.addEventListener("click", (e) => {
    if (e.target.closest("[data-modal-close]")) {
      closeModal();
      return;
    }
    if (_backdropPointerDown && isBackdropTarget(e.target)) {
      closeModal();
    }
    _backdropPointerDown = false;
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
