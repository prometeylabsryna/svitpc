/**
 * Countdown timers for promotions — elements with [data-countdown] (Unix timestamp).
 */

export function initCountdownTimers(root = document) {
  const timers = root.querySelectorAll("[data-countdown]");

  timers.forEach((el) => {
    const endTime = parseInt(el.dataset.countdown, 10);
    if (!endTime) return;

    const expiredLabel = el.dataset.expiredLabel || "Акція завершена";
    const labelDays = el.dataset.labelDays || "дн";
    const labelHours = el.dataset.labelHours || "год";
    const labelMinutes = el.dataset.labelMinutes || "хв";
    const labelSeconds = el.dataset.labelSeconds || "сек";

    function update() {
      const now = Math.floor(Date.now() / 1000);
      const diff = endTime - now;

      if (diff <= 0) {
        el.innerHTML = `<span class="timer__expired">${expiredLabel}</span>`;
        return;
      }

      const days = Math.floor(diff / 86400);
      const hours = Math.floor((diff % 86400) / 3600);
      const minutes = Math.floor((diff % 3600) / 60);
      const seconds = diff % 60;

      el.innerHTML =
        '<div class="timer">' +
        (days > 0
          ? `<div class="timer__block"><span class="timer__num">${days}</span><span class="timer__label">${labelDays}</span></div>`
          : "") +
        `<div class="timer__block"><span class="timer__num">${String(hours).padStart(2, "0")}</span><span class="timer__label">${labelHours}</span></div>` +
        `<div class="timer__block"><span class="timer__num">${String(minutes).padStart(2, "0")}</span><span class="timer__label">${labelMinutes}</span></div>` +
        `<div class="timer__block"><span class="timer__num">${String(seconds).padStart(2, "0")}</span><span class="timer__label">${labelSeconds}</span></div>` +
        "</div>";

      setTimeout(update, 1000);
    }

    update();
  });
}
