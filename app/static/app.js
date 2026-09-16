const chatForm = document.querySelector("#chat-form");
const chatFeed = document.querySelector("#chat-feed");
const messageInput = document.querySelector("#message");
const sendButton = document.querySelector("#send-button");
const uploadForm = document.querySelector("#upload-form");
const uploadButton = document.querySelector("#upload-button");
const uploadFeedback = document.querySelector("#upload-feedback");
const fileInput = document.querySelector("#document-file");
const fileLabel = document.querySelector("#file-label");
const statusList = document.querySelector("#document-status-list");
const imageDisposers = [];
let identityGeneration = 0;

// 切换身份时释放图片并清除旧用户结果。 / Clears previous identity results.
for (const selector of ["#user-id", "#department-id", "#role-ids"]) {
  document.querySelector(selector).addEventListener("input", () => {
    identityGeneration += 1;
    for (const dispose of imageDisposers) dispose();
    imageDisposers.length = 0;
    chatFeed.replaceChildren();
    statusList.replaceChildren();
  });
}
window.addEventListener("pagehide", () => {
  for (const dispose of imageDisposers) dispose();
});

function authenticationHeaders() {
  const headers = {
    "X-User-Id": document.querySelector("#user-id").value.trim(),
  };
  const departmentId = document.querySelector("#department-id").value.trim();
  const roleIds = document.querySelector("#role-ids").value.trim();
  if (departmentId) headers["X-Department-Id"] = departmentId;
  if (roleIds) headers["X-Role-Ids"] = roleIds;
  return headers;
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function addMessage(role, text, options = {}) {
  const article = createElement(
    "article",
    `message ${role === "user" ? "user-message" : "assistant-message"}`,
  );
  if (options.error) article.classList.add("error-message");
  if (options.loading) article.classList.add("loading-message");

  article.append(
    createElement("div", "message-label", role === "user" ? "You" : "Assistant"),
    createElement("p", "", text),
  );
  chatFeed.append(article);
  chatFeed.scrollTop = chatFeed.scrollHeight;
  return article;
}

function addSources(messageElement, sources) {
  if (!sources || sources.length === 0) return;

  messageElement.append(
    createElement("span", "evidence-note", `${sources.length} 个可追踪来源`),
  );
  const list = createElement("div", "source-list");
  for (const source of sources) {
    const card = createElement("article", "source-card");
    const line = createElement("div", "source-line");
    line.append(
      createElement("strong", "", source.location || source.source_name),
      createElement(
        "span",
        "source-score",
        `score ${Number(source.score || 0).toFixed(3)}`,
      ),
    );
    const detail = [source.content_type, source.section].filter(Boolean).join(" · ");
    card.append(line);
    if (detail) card.append(createElement("div", "source-meta", detail));
    const dispose = attachImageEvidence(card, source, authenticationHeaders);
    if (dispose) imageDisposers.push(dispose);
    list.append(card);
  }
  messageElement.append(list);
}

async function responseError(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch (_error) {
    // The fallback below is intentionally safe and does not expose response internals.
  }
  return `请求失败（HTTP ${response.status}）`;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  const requestGeneration = identityGeneration;

  addMessage("user", message);
  messageInput.value = "";
  sendButton.disabled = true;
  const loading = addMessage("assistant", "正在确认权限并检索资料…", {
    loading: true,
  });

  const contentType = document.querySelector("#content-type").value;
  const sheet = document.querySelector("#sheet-filter").value.trim();
  const retrievalFilter = {};
  if (contentType) retrievalFilter.content_types = [contentType];
  if (sheet) retrievalFilter.sheets = [sheet];

  const requestBody = { message };
  if (Object.keys(retrievalFilter).length > 0) {
    requestBody.retrieval_filter = retrievalFilter;
  }

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        ...authenticationHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });
    if (!response.ok) throw new Error(await responseError(response));

    const result = await response.json();
    if (requestGeneration !== identityGeneration) return;
    loading.remove();
    const answer = addMessage("assistant", result.answer);
    addSources(answer, result.sources);
  } catch (error) {
    loading.remove();
    if (requestGeneration !== identityGeneration) return;
    addMessage("assistant", error.message || "无法完成查询。", { error: true });
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});

for (const button of document.querySelectorAll("[data-prompt]")) {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.prompt;
    messageInput.focus();
  });
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileLabel.textContent = file.name;

  const stem = file.name.replace(/\.[^.]+$/, "");
  const normalized = stem.replace(/[^a-zA-Z0-9_-]+/g, "-").toUpperCase();
  const timestamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  document.querySelector("#document-id").value ||= normalized || "DOCUMENT";
  document.querySelector("#document-version-id").value ||=
    `${normalized || "DOCUMENT"}-${timestamp}`;
  document.querySelector("#document-title").value ||= stem;
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  uploadButton.disabled = true;
  uploadFeedback.className = "form-feedback";
  uploadFeedback.textContent = "正在保存原本、解析结构并建立索引…";

  try {
    const response = await fetch("/api/admin/documents", {
      method: "POST",
      headers: authenticationHeaders(),
      body: new FormData(uploadForm),
    });
    if (!response.ok) throw new Error(await responseError(response));

    const result = await response.json();
    uploadFeedback.classList.add("success");
    uploadFeedback.textContent =
      `处理完成：${result.status}，生成 ${result.chunk_count} 个 Chunk。`;
    await loadDocumentStatuses();
  } catch (error) {
    uploadFeedback.classList.add("error");
    uploadFeedback.textContent = error.message || "文档处理失败。";
  } finally {
    uploadButton.disabled = false;
  }
});

function renderStatuses(statuses) {
  statusList.replaceChildren();
  if (statuses.length === 0) {
    statusList.append(createElement("p", "empty-state", "尚无文档版本记录。"));
    return;
  }

  for (const item of statuses) {
    const card = createElement("article", "document-status");
    const title = createElement("strong", "", item.title);
    const meta = createElement(
      "small",
      "",
      `${item.document_version_id} · ${item.version_label}`,
    );
    const knownStatus = ["active", "failed", "processing", "inactive"].includes(
      item.status,
    )
      ? item.status
      : "inactive";
    const status = createElement("span", `status-pill ${knownStatus}`, item.status);
    card.append(title, meta, status);
    statusList.append(card);
  }
}

async function loadDocumentStatuses() {
  const requestGeneration = identityGeneration;
  statusList.replaceChildren(
    createElement("p", "empty-state", "正在读取状态…"),
  );
  try {
    const response = await fetch("/api/admin/documents", {
      headers: authenticationHeaders(),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const statuses = await response.json();
    if (requestGeneration !== identityGeneration) return;
    renderStatuses(statuses);
  } catch (error) {
    if (requestGeneration !== identityGeneration) return;
    statusList.replaceChildren(
      createElement(
        "p",
        "empty-state",
        error.message || "暂时无法读取文档状态。",
      ),
    );
  }
}

document
  .querySelector("#refresh-status")
  .addEventListener("click", loadDocumentStatuses);

loadDocumentStatuses();
