"""Runs inside an isolated test container via stdin; no third-party test dependencies."""
import importlib.util
import json
import os
import socket
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.public_demo_data import bundle_hashes
from app.public_demo_health import check_health

BASE = "http://127.0.0.1:8001"


def request(method, path, body=None, headers=None):
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    active_headers = {"Content-Type": "application/json"}
    if headers is not None:
        active_headers.update(headers)
    query = Request(BASE + path, data=data, method=method, headers=active_headers)
    try:
        with urlopen(query, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def before():
    assert os.geteuid() == 10001
    assert importlib.util.find_spec("app.main") is None
    assert not Path("/app/app/api").exists()
    assert not Path("/app/app/db/session.py").exists()
    status = Path("/proc/self/status").read_text()
    assert "NoNewPrivs:\t1" in status
    assert "CapEff:\t0000000000000000" in status
    for path in ("/app/write-probe", "/public-data/write-probe"):
        try:
            Path(path).write_text("must not be written")
        except OSError:
            continue
        raise AssertionError("Unexpected writable protected filesystem")
    with socket.socket() as client:
        client.settimeout(1)
        try:
            client.connect(("169.254.169.254", 80))
        except OSError:
            pass
        else:
            raise AssertionError("EC2 metadata must not be reachable")
    check_health()
    return bundle_hashes(Path("/public-data/bundle"))


def exercise():
    methods = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"]
    blocked = ["/api/admin/documents", "/api/documents", "/api/me/leave-requests",
               "/api/me/leave-requests/prepare", "/api/documents/X/versions/Y/assets/Z",
               "/docs", "/redoc", "/openapi.json", "/static/app.js"]
    forged = {"X-User-Id": "U999", "X-Department-Id": "D-OTHER", "X-Role-Ids": "ADMIN"}
    for path in blocked:
        for method in methods:
            result = request(method, path, {"confirmed": True}, forged)
            assert result[0] == 404, (method, path, result)
    allowed = {"/": "GET", "/static/styles.css": "GET", "/static/public.css": "GET",
               "/static/public.js": "GET", "/api/chat": "POST", "/api/me/leave-balance": "GET"}
    for path in allowed:
        for method in methods:
            if method != allowed[path]:
                result = request(method, path, {})
                assert result[0] == 405, (method, path, result)
    result = request("POST", "/api/chat", {"message": "国内出張の宿泊費上限はいくらですか？"}, forged)
    assert result[0] == 200, result
    answer = json.loads(result[1])
    assert answer["answer"] == "国内出張の宿泊費上限は1泊10,000円です。"
    sources = answer["sources"]
    citation = sources[0]
    assert citation["location"] == "TravelPolicy_v1.pdf / Page 3"
    result = request("POST", "/api/chat", {"message": "私の有給休暇はあと何日ありますか？"}, forged)
    assert result[0] == 200
    answer = json.loads(result[1])
    assert answer["answer"] == "有給休暇の残日数は8日です。"
    result = request("POST", "/api/chat", {"message": "有給残日数"})
    assert result[0] == 429
    result = request("GET", "/api/me/leave-balance", headers=forged)
    assert result[0] == 200
    assert json.loads(result[1]) == {"remaining_days": 8.0, "unit": "day"}
    result = request("POST", "/api/chat", {"message": "あ" * 501})
    assert result[0] == 422
    return bundle_hashes(Path("/public-data/bundle"))


def after():
    check_health()
    result = request("POST", "/api/chat", {"message": "有給残日数"})
    assert result[0] == 429, "Daily quota was lost after restart/recreation"
    result = request("GET", "/api/me/leave-balance")
    assert json.loads(result[1])["remaining_days"] == 8
    return bundle_hashes(Path("/public-data/bundle"))


phase = os.environ["PUBLIC_DOCKER_TEST_PHASE"]
if phase == "before":
    hashes = before()
elif phase == "exercise":
    hashes = exercise()
elif phase == "after":
    hashes = after()
else:
    raise ValueError("Unknown test phase")
print(json.dumps(hashes, sort_keys=True))
