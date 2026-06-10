/**
 * Returns page — file dropzone for optional product photo.
 */

const MAX_SIZE = 5 * 1024 * 1024;
const ALLOWED = ["image/jpeg", "image/png", "image/webp"];

function initReturnsForm() {
  const form = document.querySelector("[data-returns-form]");
  if (!form) return;

  const dropzone = form.querySelector("[data-returns-dropzone]");
  const input = form.querySelector("[data-returns-file-input]");
  const nameEl = form.querySelector("[data-returns-file-name]");
  if (!dropzone || !input) return;

  const showName = (file) => {
    if (!nameEl) return;
    if (file) {
      nameEl.textContent = file.name;
      nameEl.hidden = false;
      dropzone.classList.add("has-file");
    } else {
      nameEl.textContent = "";
      nameEl.hidden = true;
      dropzone.classList.remove("has-file");
    }
  };

  const assignFile = (file) => {
    if (!file) return;
    if (!ALLOWED.includes(file.type) || file.size > MAX_SIZE) {
      input.value = "";
      showName(null);
      return;
    }
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    showName(file);
  };

  dropzone.addEventListener("click", () => input.click());

  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });

  input.addEventListener("change", () => {
    assignFile(input.files?.[0] ?? null);
  });

  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("is-dragover");
  });

  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
    assignFile(event.dataTransfer?.files?.[0] ?? null);
  });
}

document.addEventListener("DOMContentLoaded", initReturnsForm);

export { initReturnsForm };
