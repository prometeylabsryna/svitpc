/**
 * Interactive star picker for review submit form.
 * Works on initial load and after HTMX swaps.
 */

export function initReviewStars() {
  _bindAll();
  document.body.addEventListener("htmx:afterSettle", _bindAll);
}

function _bindAll() {
  document.querySelectorAll(".review-form__rating:not([data-stars-ready])").forEach(_bindContainer);
}

function _bindContainer(container) {
  container.dataset.starsReady = "1";

  const labels = Array.from(container.querySelectorAll(".review-form__star-label"));
  const inputs = Array.from(container.querySelectorAll("input[type='radio'][name='rating']"));

  _reflect(container);

  inputs.forEach((input) => {
    input.addEventListener("change", () => _reflect(container));
  });

  labels.forEach((label) => {
    label.addEventListener("mouseenter", () => {
      const val = parseInt(label.dataset.starValue, 10);
      _highlightTo(labels, val);
    });
    label.addEventListener("mouseleave", () => _reflect(container));
  });
}

function _reflect(container) {
  const checked = container.querySelector("input[type='radio']:checked");
  const val = checked ? parseInt(checked.value, 10) : 0;
  _highlightTo(
    Array.from(container.querySelectorAll(".review-form__star-label")),
    val,
  );
}

function _highlightTo(labels, val) {
  labels.forEach((label) => {
    const starVal = parseInt(label.dataset.starValue, 10);
    label.classList.toggle("is-active", starVal <= val);
  });
}
