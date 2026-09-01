# Enterprise AI Support Agent

Enterprise AI Support Agent is a Python/FastAPI project that demonstrates secure business-data access, authorized RAG, Agent Tool Calling, and safe business workflows.

The project currently contains a completed authenticated leave-balance slice and a tested Authorized RAG core.

## Current Feature

```text
X-User-Id
-> CurrentUser
-> GET /api/me/leave-balance
-> LeaveService
-> LeaveRepository
-> SQLAlchemy
-> SQLite
```

Successful response:

```json
{
  "remaining_days": 8.0,
  "unit": "day"
}
```

The API does not accept a target `user_id`. The query target always comes from the authenticated `CurrentUser`. A missing balance record is different from a real zero balance and is returned as HTTP 404.

## Technology

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- SQLite for local development
- pytest

## Authorized RAG Core

```text
CurrentUser + Query
-> AuthorizationService
-> Business DB permission + active-version lookup
-> allowed document-version IDs
-> RagService
-> retrieval-time Vector Repository filter
-> evidence threshold
-> Answer Generator
-> metadata-based Source Citation
```

The local implementation does not require a paid LLM or embedding API. Chroma, the production embedding model, and the LLM provider remain replaceable pending decisions. Chat/Agent/Tool integration is the next milestone.

## Local Setup (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m app.db.seed
python -m uvicorn app.main:app --reload
```

Open Swagger UI at `http://127.0.0.1:8000/docs`, call `GET /api/me/leave-balance`, and provide `X-User-Id: U001`.

## Tests

```powershell
python -m pytest -q
```

- Service unit tests cover normal, zero, and missing balances.
- API tests cover HTTP 200, HTTP 404, and missing authentication context.
- Repository integration tests run against isolated in-memory SQLite.

## Documents

- `docs/03_detailed_design.md`: maintained detailed design and traceability.
- `docs/development_journal.md`: implementation decisions, verification, and Git milestones.
- `docs/phase4_progress.md`: current implementation, verification, and Git status.
- `docs/interview_notes.md`: concise explanation and interview follow-up questions.

## Roadmap

1. Connect the tested Authorized RAG core to Chat, Agent Router, and SearchDocumentTool.
2. Add real document ingestion and a replaceable Chroma/embedding adapter.
3. Agent Tool Calling across business DB and document search tools.
4. Safe leave-request workflow with confirmation, final revalidation, transaction, and idempotency.
5. Docker and cloud deployment.
