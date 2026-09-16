/* 按需获取授权图片；不把身份信息放进URL。 / Loads authorized image evidence. */
(function (root) {
  function attachImageEvidence(card, source, getHeaders) {
    if (!source.image_url) return;
    // 只允许本项目图片API，防止向外部地址发送身份Header。
    const pattern = /^\/api\/documents\/[A-Za-z0-9][A-Za-z0-9._-]{0,199}\/versions\/[A-Za-z0-9][A-Za-z0-9._-]{0,199}\/assets\/img_[0-9a-f]{64}$/;
    if (!pattern.test(source.image_url)) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "image-evidence-button";
    button.textContent = "查看图片 / View image";
    const status = document.createElement("p");
    status.setAttribute("aria-live", "polite");
    const image = document.createElement("img");
    image.className = "evidence-image";
    image.alt = source.location || source.source_name || "来源图片";
    image.hidden = true;
    let objectUrl = null;
    let controller = null;
    let disposed = false;

    function clearImage() {
      image.hidden = true;
      image.removeAttribute("src");
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }

    button.addEventListener("click", async () => {
      clearImage();
      button.disabled = true;
      status.textContent = "正在检查权限并加载图片…";
      controller = new AbortController();
      try {
        const response = await fetch(source.image_url, {
          headers: getHeaders(), signal: controller.signal,
          cache: "no-store", redirect: "error",
        });
        if (response.status === 403) throw new Error("无权查看图片，权限可能已撤销。");
        if (response.status === 404) throw new Error("图片不存在或已删除。");
        if (!response.ok) throw new Error("图片加载失败，请确认身份后重试。");
        const blob = await response.blob();
        const types = ["image/png", "image/jpeg", "image/gif", "image/bmp", "image/webp"];
        if (!types.includes(blob.type)) throw new Error("返回内容不是受支持的图片。");
        if (disposed) return;
        objectUrl = URL.createObjectURL(blob);
        image.src = objectUrl;
        image.hidden = false;
        status.textContent = "图片证据（来源位置见上方）";
        button.textContent = "重新验证并加载 / Reload";
      } catch (error) {
        if (!disposed) status.textContent = error.message || "图片暂时无法加载。";
      } finally {
        button.disabled = false;
      }
    });
    image.addEventListener("error", () => {
      clearImage();
      status.textContent = "图片内容无法显示。";
    });
    card.append(button, status, image);
    return function dispose() {
      disposed = true;
      if (controller) controller.abort();
      clearImage();
    };
  }
  root.attachImageEvidence = attachImageEvidence;
})(globalThis);
