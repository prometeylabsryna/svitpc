/**
 * Site nav — mark active category and keep its accordion open.
 * Runs on every page load; pure DOM/CSS, no server round-trip.
 */

export function initSiteNav() {
  const currentPath = window.location.pathname;

  document.querySelectorAll(".site-nav__group").forEach((group) => {
    const link = group.querySelector(".site-nav__item");
    if (!link) return;

    const href = link.getAttribute("href");
    if (!href || href === "/") return;

    // Mark active when current path starts with the category URL
    if (currentPath === href || currentPath.startsWith(href + "/") || currentPath.startsWith(href.replace(/\/$/, "") + "/")) {
      link.classList.add("is-active");
      group.classList.add("is-open");
    }
  });
}
