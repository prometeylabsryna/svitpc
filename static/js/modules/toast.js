/** Toast notification system — auto-dismisses after delay. */

const TOAST_DURATION = 4000;

const createToast = (message, type = "info") => {
  const container = document.querySelector(".toasts") ?? (() => {
    const el = document.createElement("div");
    el.className = "toasts";
    document.body.appendChild(el);
    return el;
  })();

  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.setAttribute("role", "alert");
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  const remove = () => toast.remove();
  setTimeout(remove, TOAST_DURATION);
  toast.addEventListener("click", remove);
};

// Listen for Django messages injected via HTMX OOB swap
document.addEventListener("htmx:afterSwap", () => {
  document.querySelectorAll("[data-toast]").forEach((el) => {
    createToast(el.dataset.toast, el.dataset.toastType ?? "info");
    el.remove();
  });
});

export { createToast };
