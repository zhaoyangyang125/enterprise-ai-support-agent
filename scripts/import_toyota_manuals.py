"""toyota-manuals フォルダの PDF を一括取り込みする。 / Batch-imports Toyota manuals.

Usage (repo root, venv active):
    python -m scripts.import_toyota_manuals [--dir ..\\toyota-manuals] [--only PRIUS] [--dry-run]
--dry-run parses only and prints chunk statistics (no embedding API calls, no cost).
"""
import argparse
import hashlib
import sys
from pathlib import Path

from app.document_processing.toyota_manual_parser import ToyotaManualParser, model_name_from_file, version_from_file


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path(__file__).resolve().parents[2] / "toyota-manuals")
    ap.add_argument("--only", default="", help="file-name substring filter, e.g. PRIUS")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--user", default="U001", help="user id granted read access")
    args = ap.parse_args()
    files = sorted(p for p in args.dir.glob("*.pdf") if args.only.casefold() in p.name.casefold())
    if not files:
        raise SystemExit(f"no PDFs found in {args.dir}")
    if args.dry_run:
        parser = ToyotaManualParser()
        for path in files:
            blocks = parser.parse(path)
            sizes = sorted(len(b.content) for b in blocks)
            print(f"{path.name}: {len(blocks)} chunks, median {sizes[len(sizes)//2]} chars, "
                  f"tables {sum(b.content_type == 'table' for b in blocks)}, "
                  f"no-section {sum(not b.section for b in blocks)}")
        return
    from app.db.session import SessionFactory
    from app.dependencies import get_document_service, get_vector_repository
    with SessionFactory() as session:
        _ingest_all(files, get_document_service(session, get_vector_repository()), args.user)


def _ingest_all(files: list[Path], service, user_id: str) -> None:
    for path in files:
        tag = hashlib.sha1(path.name.encode()).hexdigest()[:8]
        result = service.ingest(
            source_path=path, document_id=f"TOYOTA-{tag}", title=f"{model_name_from_file(path)} 取扱書(MM)",
            document_version_id=f"TOYOTA-{tag}-v1", version_label=version_from_file(path),
            grant_read_to_user_id=user_id)
        print(f"{path.name}: {result.chunk_count} chunks indexed")


if __name__ == "__main__":
    main()
