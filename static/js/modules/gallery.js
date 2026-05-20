/** Product image gallery — thumbnail switcher. */

const initGallery = (root = document) => {
  const galleries = root.querySelectorAll("[data-gallery]");
  galleries.forEach((gallery) => {
    const mainImg = gallery.querySelector("[data-gallery-main] img");
    if (!mainImg) return;

    gallery.querySelectorAll("[data-gallery-thumb]").forEach((thumb) => {
      thumb.addEventListener("click", () => {
        const src = thumb.dataset.src ?? thumb.querySelector("img")?.src;
        if (!src) return;
        mainImg.src = src;
        gallery.querySelectorAll("[data-gallery-thumb]").forEach((t) => t.classList.remove("is-active"));
        thumb.classList.add("is-active");
      });
    });
  });
};

export { initGallery };
