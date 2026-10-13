"""Explicit preparation and verification of an isolated fictional demo bundle."""
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Document, DocumentPermission, DocumentVersion, LeaveBalance, User
from app.public_demo_fixtures import PUBLIC_DATABASE_ROWS, PUBLIC_DOCUMENT_CHUNKS
from app.repositories.vector_repository import ChromaVectorRepository
from app.services.embedding_service import HashEmbeddingProvider

COLLECTION = "public_demo_documents"


def bundle_hashes(directory: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Demo bundle must not contain symbolic links")
        relative = path.relative_to(directory)
        if path.is_file() and relative.as_posix() != "manifest.json":
            content = path.read_bytes()
            hashes[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    return hashes


def prepare_bundle(directory: Path) -> None:
    """Create NEW data only; never copy or seed a private database."""
    if directory.exists():
        raise ValueError("Output directory already exists; refusing to overwrite")
    directory.mkdir(parents=True)
    database = directory / "fictional.sqlite3"
    engine = create_engine("sqlite:///" + database.as_posix())
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(User(user_id="U001"))
            session.flush()
            session.add(LeaveBalance(user_id="U001", remaining_days=8.0,
                                     updated_at=datetime(2026, 1, 1, tzinfo=UTC)))
            session.add(Document(document_id="TRAVEL_POLICY", title="架空の国内出張規定"))
            session.flush()
            session.add(DocumentVersion(document_version_id="TRAVEL_POLICY-V1",
                                        document_id="TRAVEL_POLICY", version_label="v1",
                                        status="active"))
            session.add(DocumentPermission(document_id="TRAVEL_POLICY", subject_type="role",
                                           subject_id="EMPLOYEE", action="read"))
            session.commit()
    finally:
        engine.dispose()
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(directory / "chroma"),
                                      settings=Settings(anonymized_telemetry=False))
    try:
        collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
        vector = ChromaVectorRepository(collection, HashEmbeddingProvider())
        vector.upsert_chunks(PUBLIC_DOCUMENT_CHUNKS)
    finally:
        client.close()
    manifest = {"format": 1, "fictional_only": True, "collection": COLLECTION,
                "files": bundle_hashes(directory)}
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def verify_bundle(directory: Path) -> None:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or manifest.get("fictional_only") is not True:
        raise ValueError("An explicitly prepared fictional demo bundle is required")
    if manifest.get("collection") != COLLECTION:
        raise ValueError("Unexpected public collection")
    files = bundle_hashes(directory)
    if manifest.get("files") != files:
        raise ValueError("Demo bundle integrity check failed")
    for filename in files:
        if filename in ("fictional.sqlite3", "chroma/chroma.sqlite3"):
            continue
        parts = Path(filename).parts
        if len(parts) != 3 or parts[0] != "chroma":
            raise ValueError("Unapproved file in public bundle")
        UUID(parts[1])
        if parts[2] not in ("header.bin", "data_level0.bin", "length.bin", "link_lists.bin"):
            raise ValueError("Unapproved Chroma file in public bundle")
    if not (directory / "fictional.sqlite3").is_file():
        raise ValueError("Public database is missing")
    if not (directory / "chroma" / "chroma.sqlite3").is_file():
        raise ValueError("Public Chroma index is missing")


def verify_public_database(database: Path) -> None:
    """Reject non-allowlisted rows/tables even when a manifest was rehashed."""
    resolved_database = database.resolve()
    database_uri = resolved_database.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(database_uri, uri=True)
    try:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute("SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
        tables = set()
        for row in cursor:
            if row["type"] == "table":
                tables.add(row["name"])
            elif row["type"] != "index":
                raise ValueError("Public database must not contain views or triggers")
        if tables != set(PUBLIC_DATABASE_ROWS):
            raise ValueError("Public database contains unapproved tables")
        for table in PUBLIC_DATABASE_ROWS:
            # Table names come exclusively from the checked-in allowlist, never a request.
            cursor = connection.execute('SELECT * FROM "' + table + '"')
            actual = []
            for row in cursor:
                actual.append(dict(row))
            if actual != PUBLIC_DATABASE_ROWS[table]:
                raise ValueError("Public database contains unapproved fictional rows: " + table)
    finally:
        connection.close()
