"""Read-only, quota-free checks that fail if a private app is accidentally running."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8001"


def fetch(path: str) -> tuple[int, bytes]:
    request = Request(BASE_URL + path)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, response.read(65536)
    except HTTPError as error:
        return error.code, b""


def check_health() -> None:
    home = fetch("/")
    if home[0] != 200 or "架空データを使用した公開デモです".encode() not in home[1]:
        raise RuntimeError("Public homepage is not ready")
    balance = fetch("/api/me/leave-balance")
    if balance[0] != 200:
        raise RuntimeError("Fictional leave balance is unavailable")
    payload = json.loads(balance[1])
    if payload != {"remaining_days": 8.0, "unit": "day"}:
        raise RuntimeError("Unexpected fictional identity or balance")
    for path in ("/docs", "/openapi.json", "/api/admin/documents", "/api/me/leave-requests"):
        response = fetch(path)
        if response[0] != 404:
            raise RuntimeError("Private API boundary check failed")


if __name__ == "__main__":
    check_health()
