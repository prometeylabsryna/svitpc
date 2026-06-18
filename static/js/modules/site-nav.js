/**
 * Site nav — mark the active top-level category based on current URL.
 * No dropdowns, no accordion — just highlight the active item.
 */

export function initSiteNav() {
  const currentPath = window.location.pathname;
  const nav = document.querySelector(".page-body__nav .site-nav");
  if (!nav) return;

  nav.querySelectorAll("a.site-nav__item[data-nav-href]").forEach((link) => {
    const href = link.getAttribute("data-nav-href") || "";
    const norm = href.replace(/\/$/, "");
    if (
      currentPath === href ||
      currentPath === norm ||
      currentPath.startsWith(norm + "/")
    ) {
      link.classList.add("is-active");
    }
  });
}
