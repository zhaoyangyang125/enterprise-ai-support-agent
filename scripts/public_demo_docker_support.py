"""Public-only Docker build context and explicitly local Docker client."""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "enterprise-ai-support-agent-public:phase2a"
LOCAL_HOSTS = ("unix:///var/run/docker.sock", "npipe:////./pipe/dockerDesktopLinuxEngine")


def default_host() -> str:
    if os.name == "nt":
        return LOCAL_HOSTS[1]
    return LOCAL_HOSTS[0]


def stage_public_context(destination: Path) -> list[str]:
    manifest_path = ROOT / "deploy/public-demo/source-files.txt"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    lines = manifest_text.splitlines()
    names = []
    for line in lines:
        name = line.strip()
        if not name:
            continue
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Build context path must stay within the repository")
        if relative.suffix not in (".py", ".css", ".js", ".html", ".txt") and name != "Dockerfile.public":
            raise ValueError("Unapproved public build source type")
        source = ROOT / relative
        resolved_source = source.resolve()
        if ROOT not in resolved_source.parents or source.is_symlink():
            raise ValueError("Build source cannot be a link or outside the repository")
        if name.startswith(("app/api/", "app/main.", "app/dependencies.", "app/db/session.", "app/db/seed.")):
            raise ValueError("Private application source is forbidden")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        names.append(name)
    return names


class LocalDocker:
    def __init__(self, host: str, config_directory: Path):
        if host not in LOCAL_HOSTS:
            raise ValueError("Only the explicitly local Docker engine is allowed")
        config_directory.mkdir(parents=True, exist_ok=True)
        configuration = {}
        if os.name == "nt":
            local_app_data = os.environ["LOCALAPPDATA"]
            plugin_directory = Path(local_app_data) / "Programs/DockerDesktop/resources/cli-plugins"
            configuration["cliPluginsExtraDirs"] = [str(plugin_directory)]
        config_path = config_directory / "config.json"
        config_path.write_text(json.dumps(configuration), encoding="utf-8")
        self.prefix = ["docker", "--config", str(config_directory), "--host", host]
        self.environment = dict(os.environ)
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            self.environment.pop(name, None)

    def run(self, arguments: list[str], input_text: str | None = None,
            check: bool = True, timeout: int = 240) -> subprocess.CompletedProcess:
        command = self.prefix + arguments
        result = subprocess.run(command, input=input_text, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", env=self.environment,
                                timeout=timeout, cwd=ROOT)
        if check and result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        return result

    def build(self, context: Path) -> None:
        command = self.prefix + ["build", "--progress", "plain", "-f", "Dockerfile.public", "-t", IMAGE, str(context)]
        subprocess.run(command, cwd=ROOT, env=self.environment, check=True, timeout=900)
