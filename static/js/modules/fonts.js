/**
 * Load Google Fonts without blocking first paint (CSP-safe, no inline handlers).
 */

const FONT_HREF = "https://fonts.googleapis.com/css2?family=PT+Sans:wght@400;700&display=swap";

const loadFonts = () => {
  if (document.querySelector(`link[href="${FONT_HREF}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = FONT_HREF;
  document.head.appendChild(link);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadFonts);
} else {
  loadFonts();
}

export { loadFonts };
