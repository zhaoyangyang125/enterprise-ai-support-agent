"""Fixed public-only container entrypoint. Docker arguments cannot select a private app."""
import os
import sys


def validate_container_environment() -> None:
    if os.geteuid() != 10001:
        raise RuntimeError("Public container must run as UID 10001")
    for name in os.environ:
        if name.startswith(("AWS_", "RAG_", "DASHSCOPE_", "GEMINI_", "GOOGLE_")):
            raise RuntimeError("Private provider configuration is forbidden in public containers")
        if "API_KEY" in name or "SECRET_ACCESS_KEY" in name:
            raise RuntimeError("Cloud credentials are forbidden in public containers")
    if os.environ.get("PUBLIC_DEMO_DATA_DIR") != "/public-data/bundle":
        raise RuntimeError("Public data mount path must be explicit and isolated")
    if os.environ.get("PUBLIC_DEMO_STATE_DIR") != "/public-state":
        raise RuntimeError("Public quota state mount path must be explicit and isolated")
    if os.environ.get("PUBLIC_DEMO_MODEL_MODE") != "offline":
        raise RuntimeError("Only offline public model mode is allowed")


def main() -> None:
    if len(sys.argv) != 1:
        raise RuntimeError("This entrypoint does not accept an alternate application or command")
    validate_container_environment()
    import uvicorn

    uvicorn.run("app.public_demo:app", host="127.0.0.1", port=8001,
                workers=1, proxy_headers=False, forwarded_allow_ips="",
                limit_concurrency=32, timeout_keep_alive=5,
                timeout_graceful_shutdown=20, access_log=False, server_header=False)


if __name__ == "__main__":
    main()
