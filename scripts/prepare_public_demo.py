"""Prepare a new, exclusively fictional public demo bundle (never private seed)."""
import argparse
from pathlib import Path

from app.public_demo_data import prepare_bundle

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    prepare_bundle(arguments.output.resolve())
    print("Created isolated fictional public demo data.")
