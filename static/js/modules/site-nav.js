/**
 * Site nav — mark active category and keep its accordion open.
 * Runs on every page load; pure DOM/CSS, no server round-trip.
 */

export function initSiteNav() {
  const currentPath = window.location.pathname;
  const nav = document.querySelector(".page-body__nav .site-nav");
  if (!nav) return;

  let activeGroup = null;

  nav.querySelectorAll(".site-nav__group").forEach((group) => {
    const link = group.querySelector(".site-nav__item");
    if (!link) return;

    const href = link.getAttribute("href");
    if (!href || href === "/") return;

    // Exact match or current path is a child of this category
    const normalised = href.replace(/\/$/, "");
    if (
      currentPath === href ||
      currentPath === normalised ||
      currentPath.startsWith(normalised + "/")
    ) {
      link.classList.add("is-active");
      group.classList.add("is-open");
      activeGroup = group;
    }
  });

  // Scroll sidebar so the active parent link is visible (not just the sub-items)
  if (activeGroup && nav.scrollTo) {
    const linkEl = activeGroup.querySelector(".site-nav__item");
    if (linkEl) {
      requestAnimationFrame(() => {
        const navTop = nav.getBoundingClientRect().top;
        const linkTop = linkEl.getBoundingClientRect().top;
        const offset = linkTop - navTop - 16; // 16px breathing room
        if (offset > 0) {
          nav.scrollTo({ top: nav.scrollTop + offset, behavior: "smooth" });
        }
      });
    }
  }
}
