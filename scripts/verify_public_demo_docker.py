"""Opt-in LOCAL Docker acceptance. Uses unique resources, no ports, no private mounts."""
import argparse
import json
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from scripts.public_demo_docker_support import IMAGE, ROOT, LocalDocker, default_host, stage_public_context


def restrictions() -> list[str]:
    return ["--network", "none", "--read-only", "--user", "10001:10001", "--init",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--cpus", "0.5", "--memory", "768m", "--memory-swap", "768m", "--pids-limit", "128",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777"]


def inspect_one(docker, kind, name):
    result = docker.run([kind, "inspect", name])
    items = json.loads(result.stdout)
    return items[0]


def wait_healthy(docker, container):
    deadline = time.monotonic() + 180
    while True:
        details = inspect_one(docker, "container", container)
        state = details["State"]
        if not state["Running"]:
            logs = docker.run(["logs", container])
            raise RuntimeError("Public container exited: " + logs.stdout + logs.stderr)
        health = state.get("Health", {})
        if health.get("Status") == "healthy":
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("Public container did not become healthy: " + json.dumps(health))
        time.sleep(2)


def run_probe(docker, container, phase):
    probe_path = ROOT / "tests/docker/public_demo_probe.py"
    code = probe_path.read_text(encoding="utf-8")
    result = docker.run(["exec", "-i", "--env", "PUBLIC_DOCKER_TEST_PHASE=" + phase,
                         container, "python", "-"], input_text=code)
    return json.loads(result.stdout)


def assert_runtime_configuration(details):
    host = details["HostConfig"]
    config = details["Config"]
    assert host["NetworkMode"] == "none"
    assert not host["PortBindings"]
    assert host["ReadonlyRootfs"] is True
    assert host["NanoCpus"] == 500000000
    assert host["Memory"] == 768 * 1024 * 1024
    assert host["MemorySwap"] == host["Memory"]
    assert host["PidsLimit"] == 128
    assert config["User"] == "10001:10001"
    assert config["Entrypoint"] == ["python", "-m", "app.public_demo_container"]
    mounts = {}
    for mount in details["Mounts"]:
        mounts[mount["Destination"]] = mount
    assert mounts["/public-data"]["RW"] is False
    assert mounts["/public-state"]["RW"] is True
    assert mounts["/public-data"]["Type"] == "volume"
    assert mounts["/public-state"]["Type"] == "volume"
    assert mounts["/public-data"]["Name"] != mounts["/public-state"]["Name"]
    for entry in config["Env"]:
        assert not entry.startswith(("AWS_", "DASHSCOPE_", "RAG_", "GEMINI_", "GOOGLE_"))


def verify(docker, build_context, build):
    if build:
        stage_public_context(build_context)
        docker.build(build_context)
    unique_id = uuid4()
    suffix = unique_id.hex[:12]
    container = "public-demo-local-test-" + suffix
    data_volume = container + "-fictional"
    state_volume = container + "-quota"
    created_volumes = []
    created_containers = []
    try:
        for name in (data_volume, state_volume):
            docker.run(["volume", "create", "--label", "purpose=public-demo-local-test", name])
            created_volumes.append(name)
        preparation = ["run", "--rm"] + restrictions()
        preparation += ["--mount", "type=volume,source=" + data_volume + ",target=/public-build",
                        "--entrypoint", "python", IMAGE, "-m", "scripts.prepare_public_demo",
                        "--output", "/public-build/bundle"]
        docker.run(preparation)
        print("PASS: new fictional data prepared inside an isolated non-root container.", flush=True)
        run_arguments = ["run", "-d", "--name", container] + restrictions()
        run_arguments += ["--mount", "type=volume,source=" + data_volume + ",target=/public-data,readonly",
                          "--mount", "type=volume,source=" + state_volume + ",target=/public-state",
                          "--env", "PUBLIC_DEMO_DAILY_REQUESTS=2", "--env", "PUBLIC_DEMO_PER_MINUTE=60", IMAGE]
        docker.run(run_arguments)
        created_containers.append(container)
        wait_healthy(docker, container)
        details = inspect_one(docker, "container", container)
        assert_runtime_configuration(details)
        before = run_probe(docker, container, "before")
        exercised = run_probe(docker, container, "exercise")
        assert before == exercised
        print("PASS: all HTTP methods, forged ADMIN/user, Japanese RAG/Citation, read-only data and quota.", flush=True)
        memory = docker.run(["exec", container, "cat", "/sys/fs/cgroup/memory.peak"])
        memory_peak = int(memory.stdout.strip())
        stats = docker.run(["stats", "--no-stream", "--format", "{{json .}}", container])
        print("RESOURCE: memory.peak=" + str(memory_peak) + " bytes; stats=" + stats.stdout.strip(), flush=True)
        docker.run(["restart", "--time", "30", container])
        wait_healthy(docker, container)
        restarted = run_probe(docker, container, "after")
        assert before == restarted
        docker.run(["stop", "--time", "30", container])
        docker.run(["rm", container])
        created_containers.remove(container)
        docker.run(run_arguments)
        created_containers.append(container)
        wait_healthy(docker, container)
        recreated = run_probe(docker, container, "after")
        assert before == recreated
        print("PASS: daily quota survives restart AND container replacement; bundle hashes unchanged.", flush=True)
        # No mounts are needed: these checks must fail before application startup.
        for extra in ([IMAGE, "app.main:app"], ["--env", "DASHSCOPE_API_KEY=test-sentinel", IMAGE]):
            refused = docker.run(["run", "--rm"] + restrictions() + extra, check=False)
            assert refused.returncode != 0
            assert "forbidden" in refused.stderr or "alternate application" in refused.stderr
        print("PASS: alternate private application arguments and provider credentials are rejected.", flush=True)
        image_details = inspect_one(docker, "image", IMAGE)
        print("IMAGE: " + image_details["Id"], flush=True)
    finally:
        # Delete ONLY this invocation's unique test objects, never production objects.
        for name in created_containers:
            docker.run(["rm", "--force", name], check=False)
        for name in created_volumes:
            docker.run(["volume", "rm", name], check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-host", default=default_host())
    parser.add_argument("--build", action="store_true")
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="public-demo-acceptance-") as temporary:
        directory = Path(temporary)
        context = directory / "context"
        context.mkdir()
        docker = LocalDocker(arguments.docker_host, directory / "docker-client")
        verify(docker, context, arguments.build)


if __name__ == "__main__":
    main()
