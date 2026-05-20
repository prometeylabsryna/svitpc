/**
 * SvitPC — main JavaScript entry point.
 * ES modules, no globals, no inline handlers.
 */

import { initMobileMenu } from "./modules/mobile-menu.js";
import { initSearch } from "./modules/search.js";
import { createToast } from "./modules/toast.js";
import { initShipping } from "./modules/shipping.js";
import { initPushNotifications } from "./modules/push.js";
import { initChat } from "./modules/chat.js";
import { initReviewStars } from "./modules/review-stars.js";
import "./modules/ecommerce.js";
// htmx-bridge auto-init runs on import
import "./modules/htmx-bridge.js";

// ── Bootstrap ──────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initMobileMenu();
  initSearch();

  // Header shadow on scroll
  const header = document.querySelector(".site-header");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 4);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
  initShipping();
  initPushNotifications();
  initChat();
  initReviewStars();

  // Django messages → toasts
  document.querySelectorAll("[data-toast]").forEach((el) => {
    createToast(el.dataset.toast, el.dataset.toastType ?? "info");
    el.remove();
  });

  // Language switcher form submission
  document.querySelectorAll("[data-lang-form]").forEach((form) => {
    form.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const nextInput = form.querySelector("[name='next']");
        // Strip any /xx/ language prefix so Django's translate_url
        // always receives a prefix-free path it can resolve correctly.
        nextInput.value = nextInput.value.replace(/^\/[a-z]{2}\//, "/");
        form.querySelector("[name='language']").value = btn.dataset.langBtn;
        form.submit();
      });
    });
  });
});
