import json
import sys

import pytest

from app import public_demo_container, public_demo_health
from scripts.public_demo_docker_support import LocalDocker, stage_public_context
from scripts.verify_public_demo_docker import restrictions


@pytest.fixture
def public_environment(monkeypatch):
    for name in list(public_demo_container.os.environ):
        if name.startswith(("AWS_", "RAG_", "DASHSCOPE_", "GEMINI_", "GOOGLE_")) or "API_KEY" in name:
            monkeypatch.delenv(name)
    monkeypatch.setattr(public_demo_container.os, "geteuid", lambda: 10001, raising=False)
    monkeypatch.setenv("PUBLIC_DEMO_DATA_DIR", "/public-data/bundle")
    monkeypatch.setenv("PUBLIC_DEMO_STATE_DIR", "/public-state")
    monkeypatch.setenv("PUBLIC_DEMO_MODEL_MODE", "offline")


def test_container_always_launches_public_single_worker(public_environment, monkeypatch):
    import uvicorn

    calls = []

    def record(app, **options):
        calls.append((app, options))

    monkeypatch.setattr(uvicorn, "run", record)
    monkeypatch.setattr(sys, "argv", ["public_demo_container"])
    public_demo_container.main()
    call = calls[0]
    assert call[0] == "app.public_demo:app"
    options = call[1]
    assert options["workers"] == 1
    assert options["proxy_headers"] is False
    assert options["host"] == "127.0.0.1"
    assert options["port"] == 8001


def test_alternate_app_and_root_refused(public_environment, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["public_demo_container", "app.main:app"])
    with pytest.raises(RuntimeError, match="alternate application"):
        public_demo_container.main()
    monkeypatch.setattr(public_demo_container.os, "geteuid", lambda: 0)
    with pytest.raises(RuntimeError, match="UID 10001"):
        public_demo_container.validate_container_environment()


@pytest.mark.parametrize("name", ["AWS_ACCESS_KEY_ID", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
                                 "DASHSCOPE_API_KEY", "GEMINI_API_KEY", "RAG_VECTOR_PATH"])
def test_private_config_refused_without_printing_value(public_environment, monkeypatch, name):
    monkeypatch.setenv(name, "test-value-not-to-be-printed")
    with pytest.raises(RuntimeError) as caught:
        public_demo_container.validate_container_environment()
    assert "test-value-not-to-be-printed" not in str(caught.value)


@pytest.mark.parametrize("name,value", [("PUBLIC_DEMO_DATA_DIR", "/private-db"),
                                       ("PUBLIC_DEMO_STATE_DIR", "/private-state"),
                                       ("PUBLIC_DEMO_MODEL_MODE", "qwen")])
def test_container_paths_and_model_are_fixed(public_environment, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        public_demo_container.validate_container_environment()


def test_health_probes_do_not_spend_chat_quota(monkeypatch):
    paths = []

    def respond(path):
        paths.append(path)
        if path == "/":
            return 200, "架空データを使用した公開デモです".encode()
        if path == "/api/me/leave-balance":
            return 200, json.dumps({"remaining_days": 8.0, "unit": "day"}).encode()
        return 404, b""

    monkeypatch.setattr(public_demo_health, "fetch", respond)
    public_demo_health.check_health()
    assert "/api/chat" not in paths
    assert "/openapi.json" in paths
    assert "/api/admin/documents" in paths


def test_health_rejects_private_home_and_open_api(monkeypatch):
    monkeypatch.setattr(public_demo_health, "fetch", lambda path: (200, b"Mock Authentication"))
    with pytest.raises(RuntimeError, match="homepage"):
        public_demo_health.check_health()

    def private_docs(path):
        if path == "/":
            return 200, "架空データを使用した公開デモです".encode()
        if path == "/api/me/leave-balance":
            return 200, b'{"remaining_days":8.0,"unit":"day"}'
        return 200, b"private API"

    monkeypatch.setattr(public_demo_health, "fetch", private_docs)
    with pytest.raises(RuntimeError, match="boundary"):
        public_demo_health.check_health()


def test_build_context_contains_only_explicit_public_sources(tmp_path):
    context = tmp_path / "context"
    context.mkdir()
    names = stage_public_context(context)
    assert "app/main.py" not in names
    assert "app/dependencies.py" not in names
    assert "app/public_demo_container.py" in names
    assert "scripts/prepare_public_demo.py" in names
    for path in context.rglob("*"):
        assert path.name not in ("business.db", ".env", "aws-v2")
    dockerfile = (context / "Dockerfile.public").read_text()
    assert "COPY app/ /" not in dockerfile
    assert "COPY scripts/ /" not in dockerfile
    assert not (context / "app/api").exists()


def test_docker_client_never_uses_remote_engine_or_private_auth(tmp_path):
    with pytest.raises(ValueError, match="local"):
        LocalDocker("ssh://ec2-private", tmp_path / "rejected")
    docker = LocalDocker("unix:///var/run/docker.sock", tmp_path / "empty-auth")
    config = json.loads((tmp_path / "empty-auth/config.json").read_text())
    assert "auths" not in config
    assert "credsStore" not in config
    assert "DOCKER_CONTEXT" not in docker.environment
    assert "--host" in docker.prefix


def test_acceptance_resources_have_no_port_publication():
    flags = restrictions()
    assert "--read-only" in flags
    assert "--pids-limit" in flags
    assert "--memory-swap" in flags
    assert "--publish" not in flags
    assert "-p" not in flags
    assert "none" in flags


def test_compose_is_an_isolated_public_only_project():
    import yaml
    from scripts.public_demo_docker_support import ROOT

    content = (ROOT / "compose.public-demo.yaml").read_text(encoding="utf-8")
    configuration = yaml.safe_load(content)
    services = configuration["services"]
    service = services["public-demo"]
    assert service["container_name"] == "enterprise-ai-support-agent-public-demo"
    assert service["image"] == "enterprise-ai-support-agent-public:phase2a"
    assert service["user"] == "10001:10001"
    assert service["read_only"] is True
    assert service["network_mode"] == "none"
    assert "ports" not in service
    assert "env_file" not in service
    assert "build" not in service
    assert service["mem_limit"] == service["memswap_limit"] == "768m"
    assert service["cpus"] == 0.5
    assert service["pids_limit"] == 128
    mounts = service["volumes"]
    data_mount = mounts[0]
    state_mount = mounts[1]
    assert data_mount["read_only"] is True
    assert data_mount["source"] != state_mount["source"]
    for name in service["environment"]:
        assert name.startswith("PUBLIC_DEMO_")
    preparation = services["prepare-data"]
    assert preparation["profiles"] == ["prepare"]
    assert preparation["entrypoint"] == ["python"]
    assert "scripts.prepare_public_demo" in preparation["command"]
