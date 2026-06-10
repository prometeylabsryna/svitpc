/**
 * Logout confirmation — opens a native <dialog> before POST logout.
 */

export const initLogoutConfirm = () => {
  document.querySelectorAll("[data-logout-open]").forEach((btn) => {
    const dialog = btn.closest(".account-sidebar")?.querySelector(".logout-confirm");
    if (!dialog) return;

    const cancelBtn = dialog.querySelector("[data-logout-cancel]");

    btn.addEventListener("click", () => {
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
        cancelBtn?.focus();
      } else {
        dialog.querySelector("form")?.requestSubmit();
      }
    });

    cancelBtn?.addEventListener("click", () => dialog.close());
  });
};
