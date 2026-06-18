/**
 * Site nav — mark active category and keep its accordion open.
 * Checks both top-level category links AND subcategory links to
 * correctly identify the active parent group.
 */

export function initSiteNav() {
  const currentPath = window.location.pathname;
  const nav = document.querySelector(".page-body__nav .site-nav");
  if (!nav) return;

  let activeGroup = null;

  nav.querySelectorAll(".site-nav__group").forEach((group) => {
    const parentLink = group.querySelector(":scope > a.site-nav__item");
    const dropdown = group.querySelector(".site-nav__dropdown");

    // 1. Check if current page IS this top-level category
    if (parentLink) {
      const href = parentLink.getAttribute("href") || "";
      const norm = href.replace(/\/$/, "");
      if (currentPath === href || currentPath === norm) {
        parentLink.classList.add("is-active");
        activeGroup = group;
      }
    }

    // 2. Check if current page is a subcategory inside this group
    if (dropdown) {
      dropdown.querySelectorAll(".site-nav__dropdown-item").forEach((sub) => {
        const href = sub.getAttribute("href") || "";
        const norm = href.replace(/\/$/, "");
        if (currentPath === href || currentPath === norm) {
          sub.classList.add("is-active");
          activeGroup = group;
        }
      });
    }

    // Open the group that contains the active page
    if (activeGroup === group) {
      group.classList.add("is-open");
    }
  });

  // Scroll sidebar so the active parent link is visible
  if (activeGroup && nav.scrollTo) {
    const linkEl = activeGroup.querySelector(":scope > a.site-nav__item");
    if (linkEl) {
      requestAnimationFrame(() => {
        const navRect = nav.getBoundingClientRect();
        const linkRect = linkEl.getBoundingClientRect();
        const offset = linkRect.top - navRect.top - 12;
        if (offset > 0) {
          nav.scrollTo({ top: nav.scrollTop + offset, behavior: "smooth" });
        }
      });
    }
  }

  // Click on nav item with subcategories — toggle accordion
  nav.querySelectorAll(".site-nav__group").forEach((group) => {
    const dropdown = group.querySelector(".site-nav__dropdown");
    if (!dropdown) return;

    const parentLink = group.querySelector(":scope > a.site-nav__item");
    if (!parentLink) return;

    // Add a toggle chevron indicator
    const chevron = document.createElement("span");
    chevron.className = "site-nav__chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = `<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    parentLink.appendChild(chevron);

    parentLink.addEventListener("click", (e) => {
      const isOpen = group.classList.contains("is-open");
      // Close all other groups
      nav.querySelectorAll(".site-nav__group.is-open").forEach((g) => {
        if (g !== group) g.classList.remove("is-open");
      });
      if (isOpen) {
        group.classList.remove("is-open");
        e.preventDefault(); // prevent nav when closing
      } else {
        group.classList.add("is-open");
        // Still navigate on second click (link already set as active)
      }
    });
  });
}
