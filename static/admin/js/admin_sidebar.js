/** Preserve admin sidebar scroll position across page navigations. */
(function () {
  const STORAGE_KEY = "svitpc.admin.sidebarScroll";

  function getSidebarNav() {
    return document.getElementById("nav-sidebar-apps");
  }

  function getScrollElement() {
    const sidebarNav = getSidebarNav();
    if (!sidebarNav) {
      return null;
    }

    const instance = window.SimpleBar?.instances?.get(sidebarNav);
    return instance?.getScrollElement?.() ?? sidebarNav;
  }

  function readScrollTop() {
    const scrollEl = getScrollElement();
    return scrollEl ? scrollEl.scrollTop : null;
  }

  function writeScrollTop(value) {
    const scrollEl = getScrollElement();
    if (scrollEl) {
      scrollEl.scrollTop = value;
    }
  }

  function saveScrollTop() {
    const scrollTop = readScrollTop();
    if (scrollTop !== null) {
      sessionStorage.setItem(STORAGE_KEY, String(scrollTop));
    }
  }

  function restoreScrollTop() {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved === null) {
      return;
    }

    writeScrollTop(Number(saved));
  }

  function bindSidebarLinks() {
    const sidebarNav = getSidebarNav();
    if (!sidebarNav || sidebarNav.dataset.scrollPreserveBound === "1") {
      return;
    }

    sidebarNav.dataset.scrollPreserveBound = "1";
    sidebarNav.addEventListener("click", (event) => {
      if (event.target.closest("a[href]")) {
        saveScrollTop();
      }
    });
  }

  window.addEventListener("load", () => {
    // Unfold scrolls the active item to the top on load; restore afterwards.
    setTimeout(() => {
      restoreScrollTop();
      bindSidebarLinks();
    }, 0);
  });
})();
