"""PDF の分块結果を確認用ページに書き出す(導入はしない)。 / Writes chunk preview pages without importing anything.

Usage (repo root, venv active):
    python -m scripts.inspect_chunks --only COROLLA
Open .chunk_preview/index.html in a browser.
"""
import argparse
from pathlib import Path

from app.document_processing.toyota_manual_parser import ToyotaManualParser
from scripts.chunk_preview import DEFAULT_OUT, write_preview


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path(__file__).resolve().parents[2] / "toyota-manuals")
    ap.add_argument("--only", default="", help="file-name substring, e.g. COROLLA (default: all)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    for path in sorted(p for p in args.dir.glob("*.pdf") if args.only.casefold() in p.name.casefold()):
        print(write_preview(path, ToyotaManualParser().parse(path), args.out))
    print(f"index: {(args.out / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
