# Phase 4 Progress

Last updated: 2026-09-01

## Current Scope

Vertical slice 1: query the authenticated user's leave balance.

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

## Git Status

- Current branch: `feature/phase4-core-backend`
- The branch has no commits yet.
- Project files are untracked.
- No `git add`, `git commit`, or `git push` has been executed.
- `practice/` and `tests/services/test_leave_availability_service.py` are
  learning-only and must remain outside the first formal feature commit.

## Next Step

Review the completed formal slice from an interview perspective, then use a
selective `git add` to stage only formal source, tests, and documents. After the
project owner understands what will be saved, create the first local commit and
begin vertical slice 2: Authorized RAG Read with retrieval-time permission
filtering and metadata-based source citation.

## Handoff Summary

Vertical slice 1 is complete and verified on `feature/phase4-core-backend`.
The request flows from the development authentication header through
`CurrentUser`, FastAPI, `LeaveService`, `LeaveRepository`, SQLAlchemy, and
SQLite. Missing records become a transport-independent business exception and
are mapped to HTTP 404 only at the API boundary. Formal tests pass at Service,
API, and Repository integration levels. The maintained detailed design is
`v0.5-draft`; review and approval remain pending. No Git staging, commit, or push
has been performed. Learning-only code must remain outside the first formal
commit.
