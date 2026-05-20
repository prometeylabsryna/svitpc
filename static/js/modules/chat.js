/**
 * Live chat widget — toggle panel, auto-scroll, clear input after send.
 * No globals; uses event delegation on #live-chat.
 */

const PANEL_ID = "live-chat-panel";
const MESSAGES_ID = "chat-messages";

export function initChat() {
  const root = document.getElementById("live-chat");
  if (!root) return;

  const panel = document.getElementById(PANEL_ID);
  const toggleBtns = root.querySelectorAll("[data-chat-toggle]");
  const form = root.querySelector("[data-chat-form]");

  toggleBtns.forEach((btn) => {
    btn.addEventListener("click", () => togglePanel(root, panel));
  });

  if (form) {
    // Clear textarea after successful HTMX request
    form.addEventListener("htmx:afterRequest", (e) => {
      if (e.detail.successful) {
        const textarea = form.querySelector("textarea[name='text']");
        if (textarea) {
          textarea.value = "";
          textarea.focus();
        }
        scrollToBottom();
      }
    });
  }
}

function togglePanel(root, panel) {
  const isOpen = !panel.hidden;
  panel.hidden = isOpen;

  const toggleBtn = root.querySelector("[data-chat-toggle][aria-expanded]");
  if (toggleBtn) toggleBtn.setAttribute("aria-expanded", String(!isOpen));

  if (!isOpen) {
    scrollToBottom();
    const textarea = panel?.querySelector("textarea[name='text']");
    textarea?.focus();
  }
}

function scrollToBottom() {
  const messages = document.getElementById(MESSAGES_ID);
  if (messages) messages.scrollTop = messages.scrollHeight;
}
