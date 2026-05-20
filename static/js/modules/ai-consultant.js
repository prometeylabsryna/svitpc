/**
 * AI Consultant — SSE streaming chat + compatibility check.
 * Uses fetch + ReadableStream for streaming (POST endpoint → text/event-stream).
 */

const STREAM_URL = document.querySelector("[data-ai-stream-url]")?.dataset.aiStreamUrl ?? "";
const COMPAT_URL = document.querySelector("[data-ai-compat-url]")?.dataset.aiCompatUrl ?? "";

// ── Helpers ──────────────────────────────────────────────────────────────────

function getCsrf() {
  return document.cookie
    .split("; ")
    .find((r) => r.startsWith("csrftoken="))
    ?.split("=")[1] ?? "";
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function scrollBottom(el) {
  el.scrollTop = el.scrollHeight;
}

// ── Message rendering ─────────────────────────────────────────────────────────

function appendUserMessage(container, text) {
  const div = document.createElement("div");
  div.className = "ai-msg ai-msg--user";
  div.textContent = text;
  container.appendChild(div);
  scrollBottom(container);
}

function createAssistantBubble(container) {
  const div = document.createElement("div");
  div.className = "ai-msg ai-msg--assistant";
  container.appendChild(div);
  scrollBottom(container);
  return div;
}

// ── SSE stream via fetch ──────────────────────────────────────────────────────

async function streamMessage(userText, messagesEl, sendBtn, inputEl) {
  if (!userText || !STREAM_URL) return;

  appendUserMessage(messagesEl, userText);
  inputEl.value = "";
  sendBtn.disabled = true;
  sendBtn.setAttribute("aria-busy", "true");

  const bubble = createAssistantBubble(messagesEl);
  bubble.textContent = "…";

  const body = new FormData();
  body.append("message", userText);
  body.append("csrfmiddlewaretoken", getCsrf());

  let accumulated = "";

  try {
    const resp = await fetch(STREAM_URL, { method: "POST", body });

    if (!resp.ok || !resp.body) {
      bubble.textContent = "Помилка з'єднання. Спробуйте ще раз.";
      bubble.classList.add("ai-msg--error");
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    bubble.textContent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") break;
        try {
          const parsed = JSON.parse(raw);
          if (parsed.text) {
            accumulated += parsed.text;
            bubble.textContent = accumulated;
            scrollBottom(messagesEl);
          }
        } catch {
          // malformed chunk — skip
        }
      }
    }

    if (!accumulated) {
      bubble.textContent = "Не вдалося отримати відповідь. Спробуйте пізніше.";
      bubble.classList.add("ai-msg--error");
    }
  } catch {
    bubble.textContent = "Помилка мережі. Перевірте підключення.";
    bubble.classList.add("ai-msg--error");
  } finally {
    sendBtn.disabled = false;
    sendBtn.removeAttribute("aria-busy");
    inputEl.focus();
  }
}

// ── Compatibility check ───────────────────────────────────────────────────────

async function runCompatibilityCheck(productIds, resultEl, checkBtn) {
  if (!COMPAT_URL || productIds.length < 2) return;

  checkBtn.disabled = true;
  checkBtn.setAttribute("aria-busy", "true");
  resultEl.textContent = "Перевіряю сумісність…";
  resultEl.className = "compat-result compat-result--loading";

  const body = new FormData();
  body.append("product_ids", JSON.stringify(productIds));
  body.append("csrfmiddlewaretoken", getCsrf());

  try {
    const resp = await fetch(COMPAT_URL, { method: "POST", body });
    const data = await resp.json();

    if (!resp.ok) {
      resultEl.textContent = data.error ?? "Помилка перевірки";
      resultEl.className = "compat-result compat-result--error";
      return;
    }

    resultEl.textContent = data.result;
    const isOk = data.result.startsWith("✅");
    resultEl.className = `compat-result ${isOk ? "compat-result--ok" : "compat-result--warn"}`;
  } catch {
    resultEl.textContent = "Помилка мережі";
    resultEl.className = "compat-result compat-result--error";
  } finally {
    checkBtn.disabled = false;
    checkBtn.removeAttribute("aria-busy");
  }
}

// ── Tab switching ─────────────────────────────────────────────────────────────

function initTabs(root) {
  const tabs = root.querySelectorAll("[data-tab-btn]");
  const panels = root.querySelectorAll("[data-tab-panel]");

  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tabBtn;
      tabs.forEach((t) => {
        t.classList.toggle("ai-tab--active", t.dataset.tabBtn === target);
        t.setAttribute("aria-selected", t.dataset.tabBtn === target ? "true" : "false");
      });
      panels.forEach((p) => {
        p.hidden = p.dataset.tabPanel !== target;
      });
    });
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

function initConsultant() {
  const root = document.querySelector(".ai-consultant");
  if (!root) return;

  initTabs(root);

  // Chat panel
  const form = root.querySelector("#ai-chat-form");
  const messagesEl = root.querySelector("#ai-chat-messages");
  const inputEl = root.querySelector("#ai-chat-input");
  const sendBtn = root.querySelector("#ai-chat-send");

  if (form && messagesEl && inputEl && sendBtn) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = inputEl.value.trim();
      if (text) streamMessage(text, messagesEl, sendBtn, inputEl);
    });

    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const text = inputEl.value.trim();
        if (text) streamMessage(text, messagesEl, sendBtn, inputEl);
      }
    });

    // Quick-prompt chips
    root.querySelectorAll("[data-chip]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const text = chip.textContent.trim();
        if (text) streamMessage(text, messagesEl, sendBtn, inputEl);
      });
    });

    // Pre-fill from ?product= query param (passed via data attribute)
    const prefill = root.dataset.aiPrefill?.trim();
    if (prefill) {
      const question = `Розкажи детальніше про товар: ${prefill}. Які характеристики важливі і чи підійде він для типових задач?`;
      streamMessage(question, messagesEl, sendBtn, inputEl);
    }
  }

  // Compatibility panel
  const compatForm = root.querySelector("#ai-compat-form");
  const compatResult = root.querySelector("#ai-compat-result");
  const compatBtn = root.querySelector("#ai-compat-btn");

  if (compatForm && compatResult && compatBtn) {
    compatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const rawIds = compatForm.querySelector("#ai-compat-ids")?.value ?? "";
      const ids = rawIds
        .split(/[\s,]+/)
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !isNaN(n));
      await runCompatibilityCheck(ids, compatResult, compatBtn);
    });
  }
}

document.addEventListener("DOMContentLoaded", initConsultant);
