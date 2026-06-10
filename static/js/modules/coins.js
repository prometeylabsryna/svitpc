import { createToast } from "./toast.js";

const COPY_RESET_MS = 2000;

/** @param {string} text */
async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
}

/** Progress bar width for SvitPC coins page. */
export function initCoinsProgress() {
  document.querySelectorAll(".coins-progress__fill").forEach((el) => {
    const current = Number(el.dataset.progress || 0);
    const target = Number(el.dataset.target || 1);
    const pct = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;
    el.style.setProperty("--coins-progress", `${pct}%`);
  });
}

/** Copy coupon code to clipboard on button click. */
export function initCouponCopy() {
  document.querySelectorAll("[data-coupon-copy]").forEach((btn) => {
    if (!(btn instanceof HTMLButtonElement) || btn.dataset.couponCopyInit) return;
    btn.dataset.couponCopyInit = "1";
    btn.addEventListener("click", async () => {
      const code = btn.dataset.couponCopy;
      if (!code) return;
      try {
        await copyText(code);
        btn.classList.add("is-copied");
        createToast(btn.dataset.labelCopied ?? "Скопійовано", "success");
        window.setTimeout(() => btn.classList.remove("is-copied"), COPY_RESET_MS);
      } catch {
        createToast(btn.dataset.labelError ?? "Не вдалося скопіювати", "error");
      }
    });
  });
}
