/** Mobile navigation menu. */

const initMobileMenu = () => {
  const openBtns = document.querySelectorAll("[data-menu-open]");
  const closeBtn = document.querySelector("[data-menu-close]");
  const backdrop = document.querySelector("[data-menu-backdrop]");
  const menu = document.querySelector("[data-mobile-menu]");

  const setExpanded = (value) => {
    openBtns.forEach((btn) => btn.setAttribute("aria-expanded", String(value)));
  };

  const open = () => {
    menu?.classList.add("is-open");
    document.body.classList.add("scroll-lock");
    setExpanded(true);
    // Return focus to close button when menu opens
    closeBtn?.focus();
  };

  const close = () => {
    menu?.classList.remove("is-open");
    document.body.classList.remove("scroll-lock");
    setExpanded(false);
    // Return focus to first open trigger (burger in header)
    openBtns[0]?.focus();
  };

  openBtns.forEach((btn) => btn.addEventListener("click", open));
  closeBtn?.addEventListener("click", close);
  backdrop?.addEventListener("click", close);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && menu?.classList.contains("is-open")) close();
  });
};

export { initMobileMenu };
