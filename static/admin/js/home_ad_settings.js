/**
 * Updates recommended banner size hint when visible_columns changes.
 */
(function () {
  "use strict";

  function init() {
    const hint = document.getElementById("home-ad-size-hint");
    const select = document.getElementById("id_visible_columns");
    if (!hint || !select) {
      return;
    }

    const sizes = JSON.parse(hint.dataset.sizes || "{}");
    const ratios = JSON.parse(hint.dataset.ratios || "{}");

    const render = () => {
      const cols = select.value;
      const size = sizes[cols];
      if (!size) {
        return;
      }
      const [w, h] = size;
      const strong = hint.querySelector("[data-size-dims]");
      if (strong) {
        strong.textContent = `${w} × ${h} px`;
      }
      const ratioEl = hint.querySelector("[data-size-ratio]");
      if (ratioEl && ratios[cols]) {
        ratioEl.textContent = ratios[cols];
      }
    };

    select.addEventListener("change", render);
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
