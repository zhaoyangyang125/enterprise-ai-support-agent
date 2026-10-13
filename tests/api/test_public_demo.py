import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.context import CurrentUser
from app.public_demo import PUBLIC_USER, PublicSettings, create_public_app
from app.public_demo_data import bundle_hashes, prepare_bundle
from app.tools.get_leave_balance_tool import GetLeaveBalanceTool


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    directory = tmp_path_factory.mktemp("public-fixture") / "data"
    prepare_bundle(directory)
    return directory


@pytest.fixture
def settings(bundle, tmp_path):
    return PublicSettings(data_dir=bundle, state_dir=tmp_path / "state", per_minute=60)


@pytest.fixture
def client(settings):
    application = create_public_app(settings)
    with TestClient(application) as active:
        yield active


def test_home_and_minimal_static_resources(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'lang="ja"' in response.text
    assert "架空データを使用した公開デモです" in response.text
    for removed in ("user-id", "role-ids", "upload-form", "ADMIN", "Mock", "leave-requests"):
        assert removed not in response.text
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/public.js").status_code == 200
    assert client.get("/static/public.css").status_code == 200
    assert client.get("/static/app.js").status_code == 404
    assert client.get("/static/image-evidence.js").status_code == 404
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_japanese_rag_and_citation(client):
    response = client.post("/api/chat", json={"message": "国内出張の宿泊費上限はいくらですか？"})
    assert response.status_code == 200
    result = response.json()
    assert result["intent"] == "knowledge_query"
    assert result["evidence_found"] is True
    assert result["answer"] == "国内出張の宿泊費上限は1泊10,000円です。"
    sources = result["sources"]
    source = sources[0]
    assert source["source_name"] == "TravelPolicy_v1.pdf"
    assert source["page"] == 3
    assert source["image_url"] is None


def test_fixed_employee_and_forged_identity(client, monkeypatch):
    identities = []
    original = GetLeaveBalanceTool.execute

    def record(tool, user):
        identities.append(user)
        return original(tool, user)

    monkeypatch.setattr(GetLeaveBalanceTool, "execute", record)
    headers = {"X-User-Id": "U999", "X-Department-Id": "D-OTHER",
               "X-Role-Ids": "ADMIN", "Authorization": "Bearer fake-admin",
               "Cookie": "user_id=U999; roles=ADMIN"}
    balance = client.get("/api/me/leave-balance?user_id=U999", headers=headers)
    assert balance.json() == {"remaining_days": 8.0, "unit": "day"}
    response = client.post("/api/chat", headers=headers,
                           json={"message": "私の有給休暇はあと何日ありますか？"})
    assert response.status_code == 200
    result = response.json()
    assert result["answer"] == "有給休暇の残日数は8日です。"
    assert result["sources"] == []
    assert identities == [PUBLIC_USER]
    assert PUBLIC_USER == CurrentUser(user_id="U001", department_id="D-SALES",
                                      role_ids=frozenset({"EMPLOYEE"}))
    response = client.post("/api/chat", headers=headers,
                           json={"message": "国内出張の宿泊費上限はいくらですか？"})
    assert response.json()["evidence_found"] is True
    response = client.post("/api/chat", json={"message": "有給残日数", "user_id": "U999"})
    assert response.status_code == 422


METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"]
BLOCKED = ["/api/admin/documents", "/api/documents", "/api/admin/documents/X",
           "/api/me/leave-requests", "/api/me/leave-requests/prepare",
           "/api/documents/X/versions/Y/assets/Z", "/docs", "/redoc", "/openapi.json",
           "/docs/oauth2-redirect", "/api/chat/", "/static/../public_demo.py"]


def test_all_methods_block_unregistered_routes_and_writes(client, bundle):
    before = bundle_hashes(bundle)
    for path in BLOCKED:
        for method in METHODS:
            response = client.request(method, path, headers={"X-Role-Ids": "ADMIN"},
                                      content=b'{"confirmed":true,"remaining_days":999}')
            assert response.status_code == 404, (method, path, response.text)
    registered = {"/": "GET", "/static/styles.css": "GET", "/static/public.js": "GET", "/static/public.css": "GET",
                  "/api/chat": "POST", "/api/me/leave-balance": "GET"}
    for path in registered:
        for method in METHODS:
            if method == registered[path]:
                continue
            response = client.request(method, path, content=b'{}')
            assert response.status_code == 405, (method, path)
    assert bundle_hashes(bundle) == before


def test_messages_and_stream_body_are_bounded(client):
    for message in ("", " ", "あ" * 501):
        response = client.post("/api/chat", json={"message": message})
        assert response.status_code == 422
    response = client.post("/api/chat", content=b"x" * 8193)
    assert response.status_code == 413
    response = client.post("/api/chat", content=iter([b"x" * 4096, b"x" * 4097]))
    assert response.status_code == 413


def test_global_rate_limit_ignores_forwarded_ip(settings):
    application = create_public_app(settings.model_copy(update={"per_minute": 1}))
    with TestClient(application) as active:
        first = active.post("/api/chat", json={"message": "有給残日数"},
                            headers={"X-Forwarded-For": "1.2.3.4"})
        assert first.status_code == 200
        second = active.post("/api/chat", json={"message": "有給残日数"},
                             headers={"X-Forwarded-For": "5.6.7.8"})
        assert second.status_code == 429
        assert second.headers["retry-after"] == "60"


def test_daily_quota_survives_restart(settings):
    limited = settings.model_copy(update={"daily_requests": 1})
    with TestClient(create_public_app(limited)) as active:
        assert active.post("/api/chat", json={"message": "有給残日数"}).status_code == 200
    with TestClient(create_public_app(limited)) as active:
        assert active.post("/api/chat", json={"message": "有給残日数"}).status_code == 429


def test_timeout_does_not_release_busy_slot(settings):
    limited = settings.model_copy(update={"concurrency": 1, "timeout_seconds": 0.05})
    application = create_public_app(limited)
    finished = threading.Event()
    started = threading.Event()
    with TestClient(application) as active:
        runtime = application.state.runtime
        original = runtime.chat

        def slow(message):
            started.set()
            finished.wait(timeout=5)
            return original(message)

        runtime.chat = slow
        try:
            response = active.post("/api/chat", json={"message": "有給残日数"})
            assert started.is_set()
            assert response.status_code == 504
            response = active.post("/api/chat", json={"message": "有給残日数"})
            assert response.status_code == 429
        finally:
            finished.set()


def test_concurrency_has_no_wait_queue(settings):
    limited = settings.model_copy(update={"concurrency": 1})
    application = create_public_app(limited)
    started = threading.Event()
    release = threading.Event()
    with TestClient(application) as active:
        runtime = application.state.runtime
        original = runtime.chat

        def slow(message):
            started.set()
            release.wait(timeout=5)
            return original(message)

        runtime.chat = slow
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(active.post, "/api/chat", json={"message": "有給残日数"})
            try:
                assert started.wait(timeout=3)
                response = active.post("/api/chat", json={"message": "有給残日数"})
                assert response.status_code == 429
            finally:
                release.set()
            assert first.result(timeout=3).status_code == 200


def test_runtime_database_enforces_read_only_and_bundle_unchanged(client, bundle):
    before = bundle_hashes(bundle)
    runtime = client.app.state.runtime
    with runtime.engine.connect() as connection:
        with pytest.raises(RuntimeError, match="read-only"):
            connection.execute(text("UPDATE leave_balances SET remaining_days=999"))
        raw = connection.connection.driver_connection
        with pytest.raises(Exception, match="readonly"):
            raw.execute("UPDATE leave_balances SET remaining_days=999")
    client.post("/api/chat", json={"message": "有給休暇を申請してください。"})
    client.post("/api/chat", json={"message": "国内出張の宿泊費上限はいくらですか？"})
    assert client.get("/api/me/leave-balance").json()["remaining_days"] == 8
    assert bundle_hashes(bundle) == before


def test_fail_closed_without_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("PUBLIC_DEMO_DATA_DIR", raising=False)
    monkeypatch.delenv("PUBLIC_DEMO_STATE_DIR", raising=False)
    with pytest.raises(ValueError, match="required"):
        with TestClient(create_public_app()):
            pass
    settings = PublicSettings(data_dir=tmp_path / "absent", state_dir=tmp_path / "state")
    with pytest.raises(FileNotFoundError):
        with TestClient(create_public_app(settings)):
            pass
    assert not settings.data_dir.exists()
    active = TestClient(create_public_app(settings))
    assert active.get("/").status_code == 503


def test_no_private_provider_fallback(settings, monkeypatch):
    monkeypatch.setenv("RAG_EMBEDDING_MODE", "dashscope")
    monkeypatch.setenv("RAG_ANSWER_MODE", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "should-never-be-read")
    with TestClient(create_public_app(settings)) as active:
        result = active.post("/api/chat", json={"message": "国内出張の宿泊費上限はいくらですか？"})
        assert result.status_code == 200
    with pytest.raises(ValueError):
        PublicSettings(data_dir=settings.data_dir, state_dir=settings.state_dir, model_mode="qwen")


def test_bundle_cannot_be_overwritten_or_tampered(bundle, tmp_path):
    with pytest.raises(ValueError, match="overwrite"):
        prepare_bundle(bundle)
    import shutil
    copied = tmp_path / "tampered"
    shutil.copytree(bundle, copied)
    database = copied / "fictional.sqlite3"
    with database.open("ab") as output:
        output.write(b"tampered")
    settings = PublicSettings(data_dir=copied, state_dir=tmp_path / "state")
    with pytest.raises(ValueError, match="integrity"):
        with TestClient(create_public_app(settings)):
            pass


def test_overlapping_private_paths_and_second_worker_fail(settings, monkeypatch):
    monkeypatch.setenv("RAG_VECTOR_PATH", str(settings.data_dir))
    with pytest.raises(ValueError, match="overlap"):
        settings.check_paths()
    monkeypatch.delenv("RAG_VECTOR_PATH")
    with TestClient(create_public_app(settings)):
        with pytest.raises(Exception, match="locked"):
            with TestClient(create_public_app(settings)):
                pass


def test_startup_never_creates_schema_or_touches_private_data(settings, tmp_path, monkeypatch):
    from app.db.models import Base

    def forbidden(*args, **kwargs):
        raise AssertionError("Public startup must not create business tables")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden)
    monkeypatch.chdir(tmp_path)
    private_database = tmp_path / "business.db"
    private_database.write_bytes(b"private database sentinel")
    private_vector = tmp_path / "chroma_data"
    private_vector.mkdir()
    private_index = private_vector / "sentinel"
    private_index.write_bytes(b"private index sentinel")
    with TestClient(create_public_app(settings)) as active:
        assert active.get("/api/me/leave-balance").status_code == 200
    assert private_database.read_bytes() == b"private database sentinel"
    assert private_index.read_bytes() == b"private index sentinel"


def test_unapproved_employee_fails_startup_even_with_rehashed_manifest(bundle, tmp_path):
    import json
    import shutil
    import sqlite3

    copied = tmp_path / "unapproved"
    shutil.copytree(bundle, copied)
    with sqlite3.connect(copied / "fictional.sqlite3") as connection:
        connection.execute("INSERT INTO users VALUES ('U999')")
    manifest_path = copied / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = bundle_hashes(copied)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    settings = PublicSettings(data_dir=copied, state_dir=tmp_path / "state")
    with pytest.raises(ValueError, match="unapproved fictional rows: users"):
        with TestClient(create_public_app(settings)):
            pass


def test_private_development_fixture_cannot_change_public_data(tmp_path, monkeypatch):
    from app import demo_data
    from app.public_demo_fixtures import PUBLIC_DOCUMENT_CHUNKS

    monkeypatch.setattr(demo_data, "DEMO_DOCUMENT_CHUNKS", [])
    directory = tmp_path / "independent-public-data"
    prepare_bundle(directory)
    settings = PublicSettings(data_dir=directory, state_dir=tmp_path / "state")
    with TestClient(create_public_app(settings)) as active:
        response = active.post("/api/chat", json={"message": "国内出張の宿泊費上限はいくらですか？"})
        assert response.status_code == 200
        result = response.json()
        approved = PUBLIC_DOCUMENT_CHUNKS[0]
        assert result["answer"] == approved.content


@pytest.mark.parametrize("contamination", ["document", "balance", "collection", "extra_file"])
def test_rehashed_private_data_is_not_accepted(bundle, tmp_path, contamination):
    import json
    import shutil
    import sqlite3

    copied = tmp_path / "contaminated"
    shutil.copytree(bundle, copied)
    if contamination == "document":
        with sqlite3.connect(copied / "fictional.sqlite3") as connection:
            connection.execute("INSERT INTO documents VALUES ('PRIVATE', 'Not public')")
    elif contamination == "balance":
        with sqlite3.connect(copied / "fictional.sqlite3") as connection:
            connection.execute("UPDATE leave_balances SET remaining_days=999")
    elif contamination == "collection":
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(path=str(copied / "chroma"),
                                           settings=Settings(anonymized_telemetry=False))
        try:
            client.create_collection("unapproved_private_documents")
        finally:
            client.close()
    else:
        (copied / ".env").write_text("SENTINEL=not-public", encoding="utf-8")
    manifest_path = copied / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = bundle_hashes(copied)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    settings = PublicSettings(data_dir=copied, state_dir=tmp_path / "state")
    with pytest.raises(ValueError, match="[Uu]napproved|approved collection"):
        with TestClient(create_public_app(settings)):
            pass
