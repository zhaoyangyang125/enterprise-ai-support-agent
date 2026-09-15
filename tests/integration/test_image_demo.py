"""检查浏览器演示入口的实际HTTP链路。 / Tests the offline demo HTTP flow."""
from fastapi.testclient import TestClient

from scripts.image_acceptance_demo import create_demo


def test_demo_chat_image_and_user_switch(tmp_path):
    """正式页面和聊天API使用同一隔离索引，其他用户无证据。 / Verifies isolation and access."""
    app = create_demo(tmp_path)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "/static/image-evidence.js" in page.text
        assert client.get("/static/image-evidence.js").status_code == 200
        headers = {"X-User-Id": "U001", "X-Role-Ids": "ADMIN"}
        statuses = client.get("/api/admin/documents", headers=headers)
        assert statuses.status_code == 200
        assert statuses.json()[0]["document_version_id"] == "DEMO-V1"
        question = {"message": "虚构导航画面保持显示"}
        answer = client.post("/api/chat", headers=headers, json=question)
        assert answer.status_code == 200
        sources = answer.json()["sources"]
        assert len(sources) == 1
        citation = sources[0]
        image_url = citation["image_url"]
        image = client.get(image_url, headers=headers)
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.content == (tmp_path / "fictional.png").read_bytes()
        denied_headers = {"X-User-Id": "U002"}
        denied = client.post("/api/chat", headers=denied_headers, json=question)
        assert denied.status_code == 200
        assert denied.json()["sources"] == []
        assert client.get(image_url, headers=denied_headers).status_code == 403
