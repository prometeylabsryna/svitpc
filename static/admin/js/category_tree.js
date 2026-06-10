const initCategoryTree = (root) => {
  const search = root.querySelector("[data-category-tree-search]");
  const items = root.querySelectorAll("[data-category-tree-item]");
  const emptyState = root.querySelector("[data-category-tree-empty]");

  if (!search || !items.length) {
    return;
  }

  const update = () => {
    const query = search.value.trim().toLowerCase();
    let visibleCount = 0;

    items.forEach((item) => {
      const label = item.dataset.label || "";
      const matches = !query || label.includes(query);
      item.hidden = !matches;
      if (matches) {
        visibleCount += 1;
      }
    });

    if (emptyState) {
      emptyState.hidden = visibleCount > 0;
    }
  };

  search.addEventListener("input", update);
  update();
};

const initAllCategoryTrees = () => {
  document.querySelectorAll("[data-category-tree]").forEach(initCategoryTree);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAllCategoryTrees);
} else {
  initAllCategoryTrees();
}
