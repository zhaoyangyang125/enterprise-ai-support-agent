/* 按需获取授权图片；不把身份信息放进URL。 / Loads authorized image evidence. */
(function (root) {
  function attachImageEvidence(card, source, getHeaders) {
    if (!source.image_url) return;
    // 只允许本项目图片API，防止向外部地址送信身份Header。
    const pattern = /^\/api\/documents\/[A-Za-z0-9][A-Za-z0-9._-]{0,199}\/versions\/[A-Za-z0-9][A-Za-z0-9._-]{0,199}\/assets\/img_[0-9a-f]{64}$/;
    if (!pattern.test(source.image_url)) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "image-evidence-button";
    button.textContent = "画像を表示";
    const status = document.createElement("p");
    status.setAttribute("aria-live", "polite");
    const image = document.createElement("img");
    image.className = "evidence-image";
    image.alt = source.location || source.source_name || "出典画像";
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
      status.textContent = "権限を確認し、画像を読み込んでいます…";
      controller = new AbortController();
      try {
        const response = await fetch(source.image_url, {
          headers: getHeaders(), signal: controller.signal,
          cache: "no-store", redirect: "error",
        });
        if (response.status === 403) throw new Error("画像の閲覧権限がありません。権限が変更された可能性があります。");
        if (response.status === 404) throw new Error("画像が見つかりません。削除された可能性があります。");
        if (!response.ok) throw new Error("画像を読み込めません。ユーザー設定を確認して再試行してください。");
        const blob = await response.blob();
        const types = ["image/png", "image/jpeg", "image/gif", "image/bmp", "image/webp"];
        if (!types.includes(blob.type)) throw new Error("対応する画像形式ではありません。");
        if (disposed) return;
        objectUrl = URL.createObjectURL(blob);
        image.src = objectUrl;
        image.hidden = false;
        status.textContent = "根拠画像（出典は上部に表示）";
        button.textContent = "権限を再確認して読み込む";
      } catch (error) {
        if (!disposed) status.textContent = error instanceof TypeError ? "通信に失敗しました。再試行してください。" : (error.message || "画像を読み込めませんでした。");
      } finally {
        button.disabled = false;
      }
    });
    image.addEventListener("error", () => {
      clearImage();
      status.textContent = "画像を表示できませんでした。";
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
