# Phase 4 Progress

Last updated: 2026-09-01

## Current Scope

Vertical slice 3: local Chat Agent / Tool integration.

## Completed

- Confirmed the workspace and current Git branch.
- Created the minimal Python project skeleton.
- Added the FastAPI application and leave-balance route boundary.
- Added mock authentication conversion from `X-User-Id` to `CurrentUser`.
- Added SQLAlchemy session setup for SQLite.
- Added `User` and `LeaveBalance` models with a one-to-one mapping.
- Corrected `LeaveBalance` to use `balance_id` as its primary key and `user_id`
  as a unique foreign key; added `updated_at`.
- Added the leave repository protocol and SQLAlchemy implementation.
- Corrected repository lookup to query by `user_id` instead of treating it as
  the entity primary key.
- Confirmed `unit` as fixed response metadata with the value `"day"`.
- Removed `unit` from the database model and constrained the response schema to
  `Literal["day"]` with the default value `"day"`.
- Removed the superseded `docs/phase4-detailed-design.md` working draft; the
  maintained design document is `docs/03_detailed_design.md`.
- Added dependency wiring from API to service and repository.
- Added the initial detailed-design record.
- Governed `docs/03_detailed_design.md` as version `v0.3-draft` with status
  `Draft`, while keeping review and approval pending.
- Merged the verified source references, design-decision log, repository
  boundary, missing-record distinction, and traceability into the maintained
  detailed design without removing previously confirmed decisions.
- Marked its revision history as reconstructed from current project records.
- Kept implementation, test, and Git status exclusively in this progress
  document rather than the detailed design.
- Recorded Chroma only as the preferred direction for a future RAG phase; the
  final vector database selection remains pending.
- Confirmed the transport-independent `LeaveBalanceNotFoundError` design, with
  its planned location at `app/services/errors.py` and no FastAPI dependency or
  HTTP status code.
- Confirmed the planned API mapping in `app/api/error_handlers.py`: convert the
  business error to HTTP 404 with a safe, concise response.
- Confirmed that a future Agent Tool will map the same business error
  independently to a Tool / Agent result.
- Recorded the `v0.4-draft` business-exception milestone; review and approval
  remained pending at that point.
- Installed and verified the project virtual environment with Python 3.12.9 and
  the required FastAPI, Pydantic, SQLAlchemy, and pytest dependencies.
- Added `LeaveBalanceNotFoundError` as a transport-independent business
  exception.
- Implemented `LeaveService.get_my_leave_balance`: query by the trusted
  `CurrentUser.user_id`, distinguish a missing record from a zero balance, and
  return `LeaveBalanceResponse` on success.
- Added Service unit tests covering normal balance, zero balance, and the
  missing-record business exception.
- Added API tests covering HTTP 200, business-error-to-404 mapping, and the
  required authentication header.
- Added automatic cleanup of FastAPI dependency overrides between API tests.
- Added Repository integration tests against isolated in-memory SQLite for
  matching and missing records.
- Updated the maintained detailed design to `v0.5-draft` with formal test case
  IDs and traceability.
- Added `README.md` and `docs/interview_notes.md` for local execution and
  interview-oriented explanation.
- Saved vertical slice 1 in local commit `9acf307` on
  `feature/phase4-core-backend`.
- Audited `REQ-F-001` through `REQ-F-004`, `NFR-SEC-001`, `FN-RAG-001`, the
  document permission matrix, and Basic Design sections 4.2, 6, 8, and 9.
- Added Business DB models for Document, DocumentVersion, and deterministic
  user/department/role document permissions.
- Added a SQLAlchemy repository that returns only readable, active, and
  effective document-version IDs.
- Added the Authorized RAG core: AuthorizationService, retrieval-time version
  filtering, evidence threshold, no-evidence refusal, and metadata citations.
- Added replaceable VectorRepository and AnswerGenerator boundaries plus a
  deterministic in-memory retrieval implementation for local development.
- Added 8 formal tests for RAG service behavior, Business DB access scope, and
  protection against returning a more-similar unauthorized chunk.
- Saved the Authorized RAG core in local commit `8b6d8fc`.
- Added `POST /api/chat`, a deterministic AgentRouter, GetLeaveBalanceTool, and
  SearchDocumentTool.
- Added local demo document metadata, an indexed Chunk, and explicit U001 read
  permission through the seed command.
- Added Agent and Chat API tests and completed a real local smoke test through
  the fully assembled dependency chain.

## Modified Files

- `.gitignore`
- `pyproject.toml`
- `app/main.py`
- `app/api/leave_balance.py`
- `app/auth/context.py`
- `app/db/models.py`
- `app/db/session.py`
- `app/dependencies.py`
- `app/repositories/leave_repository.py`
- `app/schemas/leave_balance.py`
- `app/services/leave_service.py`
- `app/services/errors.py`
- Package marker files under `app/`
- `tests/services/test_leave_service.py`
- `tests/api/test_leave_balance_api.py`
- `tests/repositories/test_leave_repository.py`
- `README.md`
- `docs/interview_notes.md`
- `docs/03_detailed_design.md`
- `docs/phase4_progress.md`
- `app/repositories/document_access_repository.py`
- `app/repositories/vector_repository.py`
- `app/schemas/rag.py`
- `app/services/authorization_service.py`
- `app/services/rag_service.py`
- `tests/services/test_rag_service.py`
- `tests/repositories/test_document_access_repository.py`
- `tests/repositories/test_vector_repository.py`

## Verification Results

- Compared the expanded design source with the existing detailed design and
  confirmed that all previously recorded decisions remain represented.
- Confirmed the detailed design contains no implementation, test, or Git status
  section; those dynamic states remain in this document.
- Skeleton consistency review found and corrected the mismatch between the
  locked `LeaveBalance` key structure and the initial model.
- Confirmed through source inspection that `unit` is no longer persisted and
  the response contract permits only `"day"`.
- Python 3.12.9 is active in `.venv`, and application imports were verified.
- Read-only syntax verification passed for the implemented service and test
  modules.
- Formal vertical slice: 8 tests passed.
- Entire current test suite, including learning exercises: 11 tests passed.
- Service tests verify normal balance, zero balance, trusted user propagation,
  and the missing-record business exception.
- API tests verify HTTP 200, HTTP 404 with a safe response, and rejection when
  the authentication header is missing.
- Repository tests verify real SQLAlchemy queries against isolated in-memory
  SQLite without reading or modifying `business.db`.
- A third-party Starlette TestClient deprecation warning remains; it does not
  affect the passing behavior and no speculative dependency change was made.
- Authorized RAG core and the existing project suite: 19 tests passed.
- Verified that no readable versions skips vector retrieval and answer
  generation.
- Verified that empty or below-threshold evidence skips answer generation.
- Verified that source citations are constructed from retrieved metadata.
- Verified that an unauthorized chunk is excluded even when it is more similar
  to the query than the authorized chunk.
- Chat/Agent/Tool integration and the entire suite: 24 tests passed.
- Real local `/api/chat` smoke tests returned HTTP 200 for both leave balance
  and authorized policy search.

## Git Status

- Current branch: `feature/phase4-core-backend`
- Vertical slice 1 is stored in local commit `9acf307`.
- Authorized RAG core is stored in local commit `8b6d8fc`.
- Current Chat/Agent/Tool changes are modified/untracked and not yet committed.
- No `git push` has been executed.
- `practice/` and `tests/services/test_leave_availability_service.py` are
  learning-only and must remain outside the first formal feature commit.

## Next Step

Selectively commit the formal Chat/Agent/Tool integration, then begin document
ingestion and the replaceable production vector adapter.

## Handoff Summary

Vertical slice 1 and the Authorized RAG core are saved in local commits. The
local `POST /api/chat` path now routes leave-balance and company-policy questions
through controlled Tools to their existing Services. The full suite passes 24
tests and both real local smoke requests return HTTP 200. Document ingestion,
Chroma, real embeddings, and an LLM provider are not yet complete. No push has
been performed, and learning-only files remain outside formal work.
