const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const send = document.querySelector("#send-button");
const feed = document.querySelector("#chat-feed");

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function message(role, text) {
  const article = element("article", `message ${role}-message`, "");
  article.append(element("div", "message-label", role === "user" ? "You" : "Assistant"));
  article.append(element("p", "", text));
  feed.append(article);
  feed.scrollTop = feed.scrollHeight;
  return article;
}

for (const button of document.querySelectorAll("[data-prompt]")) {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    input.focus();
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question || send.disabled) return;
  message("user", question);
  input.value = "";
  send.disabled = true;
  const pending = message("assistant", "資料を検索しています…");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 35000);
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question }),
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 429) throw new Error("利用上限に達しました。時間をおいて再試行してください。");
      if (response.status === 422 || response.status === 413) throw new Error("質問は1〜500文字で入力してください。");
      if (response.status === 504) throw new Error("処理時間の上限に達しました。時間をおいて再試行してください。");
      throw new Error("デモを利用できません。時間をおいて再試行してください。");
    }
    const result = await response.json();
    pending.remove();
    const answer = message("assistant", result.answer);
    if (result.sources && result.sources.length) {
      answer.append(element("span", "evidence-note", `${result.sources.length} 件の出典`));
      const sources = element("div", "source-list", "");
      for (const source of result.sources) {
        const card = element("article", "source-card", "");
        card.append(element("strong", "", source.location));
        if (source.section) card.append(element("div", "source-meta", source.section));
        sources.append(card);
      }
      answer.append(sources);
    }
  } catch (error) {
    pending.remove();
    const text = error.name === "AbortError" || error instanceof TypeError
      ? "通信を完了できませんでした。時間をおいて再試行してください。" : error.message;
    message("assistant", text);
  } finally {
    clearTimeout(timer);
    send.disabled = false;
    input.focus();
    feed.scrollTop = feed.scrollHeight;
  }
});
