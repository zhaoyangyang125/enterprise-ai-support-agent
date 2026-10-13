"""Build the independent public image from a private-data-free temporary context."""
import argparse
import tempfile
from pathlib import Path

from scripts.public_demo_docker_support import LocalDocker, default_host, stage_public_context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-host", default=default_host())
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="public-demo-build-") as temporary:
        directory = Path(temporary)
        context = directory / "context"
        context.mkdir()
        names = stage_public_context(context)
        print(f"Building from {len(names)} explicitly approved source files.", flush=True)
        docker = LocalDocker(arguments.docker_host, directory / "docker-client")
        docker.build(context)


if __name__ == "__main__":
    main()
