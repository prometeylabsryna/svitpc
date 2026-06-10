/**
 * Password visibility toggle for auth forms.
 */

/** @param {HTMLElement} btn */
const setVisible = (btn, visible) => {
  const wrap = btn.closest(".form-password");
  const input = wrap?.querySelector(".form-password__input");
  if (!input) return;

  input.type = visible ? "text" : "password";
  btn.classList.toggle("is-visible", visible);
  btn.setAttribute("aria-pressed", String(visible));
  btn.setAttribute(
    "aria-label",
    visible ? btn.dataset.labelHide ?? "" : btn.dataset.labelShow ?? "",
  );
};

/** @param {ParentNode} [root] */
export const initPasswordToggle = (root = document) => {
  root.querySelectorAll("[data-password-toggle]").forEach((btn) => {
    if (!(btn instanceof HTMLButtonElement) || btn.dataset.passwordToggleInit) return;
    btn.dataset.passwordToggleInit = "1";
    btn.addEventListener("click", () => {
      setVisible(btn, btn.getAttribute("aria-pressed") !== "true");
    });
  });
};
