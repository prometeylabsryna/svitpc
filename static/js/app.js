/**
 * SvitPC — main JavaScript entry point.
 * ES modules, no globals, no inline handlers.
 */

import { initMobileMenu } from "./modules/mobile-menu.js";
import { initSearch } from "./modules/search.js";
import { createToast } from "./modules/toast.js";
import { initReviewStars } from "./modules/review-stars.js";
import { initLogoutConfirm } from "./modules/logout-confirm.js";
import { initPasswordToggle } from "./modules/password-toggle.js";
import { initCountdownTimers } from "./modules/timer.js";
import { initSiteNav } from "./modules/site-nav.js";
import "./modules/fonts.js";
import "./modules/ecommerce.js";
import "./modules/htmx-bridge.js";

const loadOptionalModule = async (selector, modulePath, initName) => {
  if (!document.querySelector(selector)) {
    return;
  }
  const module = await import(modulePath);
  module[initName]?.();
};

document.addEventListener("DOMContentLoaded", () => {
  initMobileMenu();
  initSearch();

  const header = document.querySelector(".site-header");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 4);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  initReviewStars();
  initLogoutConfirm();
  initPasswordToggle();
  initCountdownTimers();
  initSiteNav();

  void loadOptionalModule("[data-home-ads]", "./modules/home-ads.js", "initHomeAds");
  void loadOptionalModule(
    "[data-svitik-welcome], [data-svitik-deferred], .svitik-hint",
    "./modules/svitik.js",
    "initSvitik",
  );
  if (document.querySelector(".coins-progress__fill, .coins-coupon__copy")) {
    void import("./modules/coins.js").then((module) => {
      if (document.querySelector(".coins-progress__fill")) {
        module.initCoinsProgress();
      }
      if (document.querySelector(".coins-coupon__copy")) {
        module.initCouponCopy();
      }
    });
  }
  void loadOptionalModule(".checkout-delivery__form", "./modules/shipping.js", "initShipping");

  if (document.querySelector('meta[name="vapid-pub"]')) {
    void import("./modules/push.js").then((module) => module.initPushNotifications());
  }

  document.querySelectorAll("[data-toast]").forEach((el) => {
    createToast(el.dataset.toast, el.dataset.toastType ?? "info");
    el.remove();
  });

  document.querySelectorAll("[data-lang-form]").forEach((form) => {
    form.querySelectorAll("[data-lang-btn]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const nextInput = form.querySelector("[name='next']");
        nextInput.value = nextInput.value.replace(/^\/[a-z]{2}\//, "/");
        form.querySelector("[name='language']").value = btn.dataset.langBtn;
        form.submit();
      });
    });
  });
});
