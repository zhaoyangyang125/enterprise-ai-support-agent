# Phase 4 Progress

Last updated: 2026-09-04

## Current Scope

Milestone 6 / Day 2: Excel Region Detection and structured ParsedBlock metadata.

## 2026-09-04 隔离开发说明

- 原复习目录：`D:\AI\enterprise-ai-support-agent`，保持在 `feature/phase4-core-backend`，未修改。
- 独立开发目录：`D:\AI\enterprise-ai-support-agent-complex-doc`。
- 当前开发分支：`feature/complex-doc-day1-spec`。
- 开发起点：提交 `8a1256a`。
- 原目录的未跟踪学习文件没有复制到开发工作树。
- 本日只完成式样、测试样本和预期结果，没有修改 Parser 业务代码。

## Day 1 已完成

- 确定本轮包含 Level 2 文字型复杂文档解析，不包含 OCR 和视觉理解。
- 新增中文为主的 `docs/complex_document_upgrade_plan.md`。
- 将正式详细设计更新为 `v0.10-draft`，新增范围、目标 Schema、解析规则、测试矩阵和 `DD-027`～`DD-030`。
- 生成完全虚构的日语 HMI 样本 `samples/fictional_hmi_test_spec.xlsx`。
- 样本包含多 Sheet、Key-Value、多行表头、合并单元格、同 Sheet 多表和 Note。
- 新增 `tests/fixtures/complex_documents/fictional_hmi_expected_regions.json`，固定目标区域和必须保留的内容。
- 新增样本自检，验证四个 Sheet、关键单元格、合并区域和预期 Region 均存在。
- 已检查四个 Sheet 的渲染结果；无公式错误，CAN 十六进制表记按文本保留。
- 隔离工作树全量测试：`45 passed`（提交基线 44 项 + Day 1 新增 1 项）。
- 第一次全量测试的 6 个 setup error 来自系统临时目录权限；改用工作树内 `.pytest_tmp` 后全部通过，不是代码缺陷。

## Day 2 已完成

- 当前开发分支：`feature/complex-doc-day2-excel-parser`，从 Day 1 提交 `ab09e45` 创建。
- 将复杂 Excel 实现从通用 `parsers.py` 分离到 `app/document_processing/excel_parser.py`。
- `ParsedBlock` 新增 `content_type` 和 `cell_range`，并通过默认值保持 PDF 兼容。
- 增加非破坏式 `_WorksheetLayout`，读取 merged cell 的逻辑值但不修改原 Workbook。
- 实现 Title、Key-Value、Table、Note 和 Paragraph Region 转换。
- 实现多行表头路径，例如 `CAN信号 / 信号名`。
- 实现纵向合并数据继承；同 Sheet 多张表分别使用各自 Header。
- 全量测试第一次发现两列两行被误判为 Key-Value，修正规则后重新验证。
- 定向测试：`7 passed`；项目全量：`47 passed`，保留 1 条第三方 Starlette 弃用警告。

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
- Added Prepare and Confirm APIs for self-only leave-request creation.
- Added PendingLeaveAction and LeaveRequest models, including user-scoped
  idempotency uniqueness.
- Added final revalidation, atomic balance reservation, overlap validation,
  explicit confirmation, transaction rollback, and idempotent retry behavior.
- Added CreateLeaveRequestTool as a thin bridge to the same safe write service.
- Kept ordinary natural-language Chat from triggering writes until structured
  conversation state is implemented.
- Saved safe leave requests in local commit `ea1dbb7`.
- Added text-PDF and structure-aware Excel parsers, local original-document
  storage, stable Chunk IDs, and citation metadata.
- Added DocumentVersion processing/active/failed state around cross-store work.
- Added deterministic local Hash Embedding and Chroma 1.5 PersistentClient.
- Switched the assembled RAG runtime from in-memory demo retrieval to local
  persistent Chroma; seed now upserts the demo Chunk.

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
- `app/api/leave_requests.py`
- `app/repositories/leave_request_repository.py`
- `app/schemas/leave_request.py`
- `app/services/leave_request_service.py`
- `app/tools/create_leave_request_tool.py`
- `tests/services/test_leave_request_service.py`
- `tests/repositories/test_leave_request_repository.py`
- `tests/api/test_leave_request_api.py`
- `tests/e2e/test_leave_request_flow.py`
- `tests/tools/test_create_leave_request_tool.py`
- `app/document_processing/parsers.py`
- `app/document_processing/storage.py`
- `app/repositories/document_repository.py`
- `app/schemas/document.py`
- `app/services/document_service.py`
- `app/services/embedding_service.py`
- `tests/document_processing/test_excel_parser.py`
- `tests/repositories/test_chroma_vector_repository.py`
- `tests/services/test_document_service.py`

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
- Safe leave-request Service, API, Repository, Tool, and E2E coverage brought
  the full suite to 41 passed.
- A forced failure after request INSERT proved that balance, request, and token
  state all roll back.
- A real HTTP Prepare/Confirm/retry flow proved one request row and one balance
  deduction.
- Document parser, Chroma persistence/filtering, and cross-store status tests
  are included in the final full-suite result: 47 tests passed.

## Git Status

- Current development branch: `feature/complex-doc-day2-excel-parser`
- Original review branch remains: `feature/phase4-core-backend`
- Day 1 is stored in local commit `ab09e45`.
- Day 2 changes are verified but not staged or committed yet.
- Vertical slice 1 is stored in local commit `9acf307`.
- Authorized RAG core is stored in local commit `8b6d8fc`.
- Chat/Agent/Tool integration is stored in local commit `9e1a513`.
- Safe leave requests are stored in local commit `ea1dbb7`.
- Document Ingestion/Chroma changes are verified and stored in this local
  milestone commit.
- No `git push` has been executed.
- `practice/` and `tests/services/test_leave_availability_service.py` are
  learning-only and must remain outside the first formal feature commit.

## Next Step

Day 2 已达到安全提交条件。保存 Day 2 后，Day 3 再增强有文本层 PDF 的页眉页脚、标题和自然段处理，并规划 metadata 向 IndexedChunk/Citation 的统一传递；不开发 OCR 或视觉理解。

## Handoff Summary

The two read chains, Chat/Agent/Tool, and safe write chain are saved in four
local commits. Document Ingestion and persistent local Chroma are implemented
and awaiting one final full-suite verification and local commit. Docker, Admin
Upload API, production Embedding/LLM, OCR, and final delivery validation remain.
No push has been performed, and learning-only files remain outside formal work.
