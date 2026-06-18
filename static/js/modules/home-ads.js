/**
 * Home page ad carousel: scroll-snap with dot navigation.
 */

const MOBILE_MQ = "(max-width: 639px)";
const TABLET_MQ = "(max-width: 1023px)";

function effectiveColumns(root) {
  const configured = parseInt(root.dataset.columns, 10) || 4;
  if (window.matchMedia(MOBILE_MQ).matches) {
    return 1;
  }
  if (window.matchMedia(TABLET_MQ).matches) {
    return Math.min(2, configured);
  }
  return configured;
}

function buildDots(container, count) {
  container.replaceChildren();
  for (let i = 0; i < count; i += 1) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "home-ads__dot";
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-label", `Slide ${i + 1}`);
    btn.dataset.index = String(i);
    if (i === 0) {
      btn.classList.add("is-active");
      btn.setAttribute("aria-selected", "true");
    } else {
      btn.setAttribute("aria-selected", "false");
    }
    container.appendChild(btn);
  }
}

function setActiveDot(container, index) {
  container.querySelectorAll(".home-ads__dot").forEach((dot, i) => {
    const active = i === index;
    dot.classList.toggle("is-active", active);
    dot.setAttribute("aria-selected", active ? "true" : "false");
  });
}

export function initHomeAds() {
  document.querySelectorAll("[data-home-ads]").forEach((root) => {
    const viewport = root.querySelector(".home-ads__viewport");
    const track = root.querySelector("[data-home-ads-track]");
    const dotsRoot = root.querySelector("[data-home-ads-dots]");
    const prevBtn = root.querySelector("[data-home-ads-prev]");
    const nextBtn = root.querySelector("[data-home-ads-next]");
    if (!viewport || !track || !dotsRoot) {
      return;
    }

    const slides = [...track.querySelectorAll(".home-ads__slide")];
    if (!slides.length) {
      return;
    }

    let index = 0;
    let columns = effectiveColumns(root);
    let maxIndex = Math.max(0, slides.length - columns);
    let autoplayTimer;

    const updateArrows = () => {
      if (!prevBtn || !nextBtn) return;
      if (maxIndex <= 0) {
        prevBtn.hidden = true;
        nextBtn.hidden = true;
        return;
      }
      prevBtn.hidden = false;
      nextBtn.hidden = false;
      prevBtn.disabled = index === 0;
      nextBtn.disabled = index >= maxIndex;
    };

    const scrollToIndex = (next) => {
      index = Math.max(0, Math.min(maxIndex, next));
      const slide = slides[index];
      if (slide) {
        const offset =
          slide.getBoundingClientRect().left -
          viewport.getBoundingClientRect().left +
          viewport.scrollLeft;
        viewport.scrollTo({ left: offset, behavior: "smooth" });
      }
      setActiveDot(dotsRoot, index);
      updateArrows();
    };

    const syncFromScroll = () => {
      const scrollLeft = viewport.scrollLeft;
      let nearest = 0;
      let minDist = Infinity;
      for (let i = 0; i <= maxIndex; i += 1) {
        const dist = Math.abs(slides[i].offsetLeft - scrollLeft);
        if (dist < minDist) {
          minDist = dist;
          nearest = i;
        }
      }
      index = nearest;
      setActiveDot(dotsRoot, index);
      updateArrows();
    };

    const updateLayout = () => {
      columns = effectiveColumns(root);
      maxIndex = Math.max(0, slides.length - columns);
      root.style.setProperty("--home-ads-cols", String(columns));

      if (maxIndex > 0) {
        buildDots(dotsRoot, maxIndex + 1);
        dotsRoot.hidden = false;
        viewport.classList.add("home-ads__viewport--scroll");
      } else {
        dotsRoot.replaceChildren();
        dotsRoot.hidden = true;
        viewport.classList.remove("home-ads__viewport--scroll");
        viewport.scrollLeft = 0;
      }
      updateArrows();
    };

    const resetAutoplay = () => {
      clearInterval(autoplayTimer);
      startAutoplay();
    };

    dotsRoot.addEventListener("click", (event) => {
      const btn = event.target.closest(".home-ads__dot");
      if (!btn) return;
      scrollToIndex(parseInt(btn.dataset.index, 10));
      resetAutoplay();
    });

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        scrollToIndex(index - 1);
        resetAutoplay();
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        scrollToIndex(index + 1);
        resetAutoplay();
      });
    }

    viewport.addEventListener("scroll", () => {
      window.requestAnimationFrame(syncFromScroll);
    }, { passive: true });

    const startAutoplay = () => {
      clearInterval(autoplayTimer);
      if (maxIndex <= 0) return;
      autoplayTimer = setInterval(() => {
        scrollToIndex(index >= maxIndex ? 0 : index + 1);
      }, 6000);
    };

    root.addEventListener("mouseenter", () => clearInterval(autoplayTimer));
    root.addEventListener("mouseleave", startAutoplay);

    window.addEventListener("resize", updateLayout, { passive: true });
    updateLayout();
    startAutoplay();
  });
}
