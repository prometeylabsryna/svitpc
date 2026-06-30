/**
 * Pan Svitik — floating mascot hints.
 * Triggered via HX-Trigger: {"svitik": {…}} or data-svitik-welcome on first visit.
 */

const STORAGE_KEY = "svitik-welcome-v1";
const DEFAULT_DURATION = 7000;
const COIN_SRC = "/static/images/svitpc-coin-light.png";
const ASSET_VERSION = "5";

const MASCOT_BY_KEY = {
  guide: "/static/images/pan-svitik-tech.webp",
  welcome: "/static/images/pan-svitik-choice.webp",
  cart: "/static/images/pan-svitik-coins.webp",
  choice: "/static/images/pan-svitik-choice.webp",
  search: "/static/images/pan-svitik-search.webp",
  tech: "/static/images/pan-svitik-tech.webp",
  coins: "/static/images/pan-svitik-coins.webp",
  progress: "/static/images/pan-svitik-celebrate.webp",
  celebrate: "/static/images/pan-svitik-celebrate.webp",
};

const MASCOT_DIMS = {
  "pan-svitik-choice.webp": [368, 441],
  "pan-svitik-choice-sm.webp": [184, 221],
  "pan-svitik-coins.webp": [368, 565],
  "pan-svitik-coins-sm.webp": [184, 283],
  "pan-svitik-search.webp": [368, 525],
  "pan-svitik-search-sm.webp": [184, 263],
  "pan-svitik-tech.webp": [368, 474],
  "pan-svitik-tech-sm.webp": [184, 237],
  "pan-svitik-celebrate.webp": [368, 407],
  "pan-svitik-celebrate-sm.webp": [184, 204],
};

const VARIANT_MASCOT = {
  welcome: "welcome",
  cart: "cart",
  choice: "choice",
  success: "celebrate",
  checkout: "progress",
  tip: "tech",
  search: "search",
  coins: "coins",
  guide: "guide",
  progress: "progress",
  celebrate: "celebrate",
  tech: "tech",
};

const useSmMascot = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(max-width: 640px)").matches;

const mascotSrc = (variant, mascotFile) => {
  let src;
  if (mascotFile) {
    if (mascotFile.startsWith("/") || mascotFile.startsWith("http")) {
      src = mascotFile;
    } else if (mascotFile.endsWith(".png") || mascotFile.endsWith(".webp")) {
      src = `/static/images/${mascotFile}`;
    } else {
      src = MASCOT_BY_KEY[mascotFile] ?? MASCOT_BY_KEY.guide;
    }
  } else {
    const key = VARIANT_MASCOT[variant] ?? "guide";
    src = MASCOT_BY_KEY[key] ?? MASCOT_BY_KEY.guide;
  }
  if (useSmMascot() && src.includes("/pan-svitik-") && !src.includes("-sm.")) {
    src = src.replace(".webp", "-sm.webp");
  }
  const join = src.includes("?") ? "&" : "?";
  return `${src}${join}v=${ASSET_VERSION}`;
};

const mascotDims = (src) => {
  const file = src.split("/").pop()?.split("?")[0] ?? "";
  return MASCOT_DIMS[file] ?? null;
};

const ensureContainer = () => {
  let el = document.querySelector(".svitik-popups");
  if (!el) {
    el = document.createElement("div");
    el.className = "svitik-popups";
    el.setAttribute("aria-live", "polite");
    document.body.appendChild(el);
  }
  return el;
};

const createBadge = (coins) => {
  const badge = document.createElement("span");
  badge.className = "svitik-popup__badge";
  const icon = document.createElement("img");
  icon.src = COIN_SRC;
  icon.width = 52;
  icon.height = 52;
  icon.alt = "";
  icon.className = "svitik-popup__badge-icon";
  icon.loading = "lazy";
  icon.decoding = "async";
  const value = document.createElement("span");
  value.className = "svitik-popup__badge-value";
  value.textContent = String(coins);
  const label = document.createElement("span");
  label.className = "svitik-popup__badge-label";
  label.textContent = "монет";
  badge.append(icon, value, label);
  return badge;
};

/**
 * @param {object} opts
 * @param {string} opts.message
 * @param {string} [opts.title]
 * @param {string} [opts.variant]
 * @param {string} [opts.mascot]
 * @param {number} [opts.coins]
 * @param {number} [opts.duration]
 */
export const showSvitik = ({
  message,
  title = "",
  variant = "tip",
  mascot = "",
  coins = null,
  duration = DEFAULT_DURATION,
}) => {
  if (!message) return;

  const container = ensureContainer();
  const popup = document.createElement("aside");
  popup.className = `svitik-popup svitik-popup--${variant}`;
  popup.setAttribute("role", "status");

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "svitik-popup__close";
  closeBtn.setAttribute("aria-label", "Закрити");
  closeBtn.textContent = "×";

  const body = document.createElement("div");
  body.className = "svitik-popup__body";

  if (title) {
    const titleEl = document.createElement("p");
    titleEl.className = "svitik-popup__title";
    titleEl.textContent = title;
    body.append(titleEl);
  }

  const text = document.createElement("p");
  text.className = "svitik-popup__text";
  text.textContent = message;
  body.append(text);

  if (coins != null && coins > 0) {
    body.append(createBadge(coins));
  }

  const mascotWrap = document.createElement("div");
  mascotWrap.className = "svitik-popup__mascot-wrap";

  const mascotEl = document.createElement("img");
  mascotEl.className = "svitik-popup__mascot";
  const src = mascotSrc(variant, mascot);
  mascotEl.src = src;
  mascotEl.alt = "";
  const dims = mascotDims(src);
  if (dims) {
    mascotEl.width = dims[0];
    mascotEl.height = dims[1];
  }
  mascotEl.loading = "lazy";
  mascotEl.decoding = "async";
  mascotWrap.append(mascotEl);

  popup.append(closeBtn, body, mascotWrap);
  container.appendChild(popup);

  const remove = () => popup.remove();
  closeBtn.addEventListener("click", remove);
  popup.addEventListener("click", (e) => {
    if (e.target === popup) remove();
  });
  if (duration > 0) {
    setTimeout(remove, duration);
  }
};

const showWelcomeIfNeeded = () => {
  if (window.matchMedia("(max-width: 768px)").matches) {
    const el = document.querySelector("[data-svitik-welcome]");
    if (el) el.remove();
    return;
  }
  const el = document.querySelector("[data-svitik-welcome]");
  if (!el || sessionStorage.getItem(STORAGE_KEY)) return;

  showSvitik({
    title: el.dataset.svitikTitle ?? "",
    message: el.dataset.svitikMessage ?? "",
    variant: el.dataset.svitikVariant ?? "welcome",
    mascot: el.dataset.svitikMascot ?? "",
    duration: 9000,
  });
  sessionStorage.setItem(STORAGE_KEY, "1");
  el.remove();
};

/** Page-level delayed hint (e.g. checkout encouragement). */
const showDeferredHints = () => {
  document.querySelectorAll("[data-svitik-deferred]").forEach((el) => {
    const delay = Number(el.dataset.svitikDelay ?? 1200);
    setTimeout(() => {
      showSvitik({
        title: el.dataset.svitikTitle ?? "",
        message: el.dataset.svitikMessage ?? "",
        variant: el.dataset.svitikVariant ?? "tip",
        mascot: el.dataset.svitikMascot ?? "",
        coins: el.dataset.svitikCoins ? Number(el.dataset.svitikCoins) : null,
      });
      el.remove();
    }, delay);
  });
};

document.body.addEventListener("svitik", (e) => {
  const detail = e.detail ?? {};
  if (detail.message) showSvitik(detail);
});

export const initSvitik = () => {
  showWelcomeIfNeeded();
  showDeferredHints();
};
