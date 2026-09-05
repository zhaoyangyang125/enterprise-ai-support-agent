# Enterprise AI Support Agent

Enterprise AI Support Agent is a Python/FastAPI project that demonstrates secure business-data access, authorized RAG, Agent Tool Calling, and safe business workflows.

这是一个使用 Python/FastAPI 开发的企业 AI 支持系统练习项目，包含受控业务数据访问、权限过滤 RAG、Agent Tool Calling、安全写入流程和复杂文档解析。

The project currently contains an authenticated leave-balance slice, Authorized RAG, and a local Chat/Agent/Tool path.

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
- Chroma 1.5 local persistent vector database
- pypdf and openpyxl for local document parsing

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

The local implementation does not require a paid LLM or embedding API. The runtime uses local persistent Chroma with deterministic Hash Embedding. The Hash implementation is intentionally offline and replaceable; it is not presented as a production-quality semantic model.

## Local Setup (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m app.db.seed
python -m uvicorn app.main:app --reload
```

Open Swagger UI at `http://127.0.0.1:8000/docs`, call `GET /api/me/leave-balance`, and provide `X-User-Id: U001`.

## 本地演示界面 / Local Demo UI

启动应用后打开 `http://127.0.0.1:8000/`。页面可以：

- 设置开发阶段的 User ID、Department 和 Roles。
- 查询年假余额或公司文档。
- 按内容类型或 Excel Sheet 缩小检索范围。
- 以 ADMIN 身份上传不超过 10 MB 的 PDF/XLSX。
- 查看文档版本状态和结构化 Citation。

上传测试时可使用 `X-Role-Ids: EMPLOYEE,ADMIN`。当前认证仍是本地 Mock，不能作为生产登录方案。

You can also call `POST /api/chat` with `X-User-Id: U001`:

```json
{
  "message": "国内出差住宿费上限是多少？"
}
```

The local seed grants `U001` explicit read access to the active travel-policy version. A leave-balance message such as `我的剩余年假是多少？` is routed to the business-data tool instead.

## Safe Leave Request

First prepare a request; the server calculates working days and current/remaining balance:

```text
POST /api/me/leave-requests/prepare
X-User-Id: U001
```

```json
{
  "start_date": "2026-09-07",
  "end_date": "2026-09-09"
}
```

After showing the returned preview to the user, submit explicit confirmation with a caller-generated idempotency key:

```text
POST /api/me/leave-requests
X-User-Id: U001
Idempotency-Key: request-20260907-U001-001
```

```json
{
  "confirmation_token": "value returned by prepare",
  "confirmed": true
}
```

Confirmation performs final revalidation, atomic balance reservation, request creation, and token consumption in one transaction. Retrying the same operation returns the same request without a second deduction.

## Tests

```powershell
python -m pytest -q
```

- Service unit tests cover normal, zero, and missing balances.
- API tests cover HTTP 200, HTTP 404, and missing authentication context.
- Repository integration tests run against isolated in-memory SQLite.
- Safe-write tests include forced transaction rollback and an end-to-end idempotent retry.

## Documents

- `docs/03_detailed_design.md`: maintained detailed design and traceability.
- `docs/development_journal.md`: implementation decisions, verification, and Git milestones.
- `docs/phase4_progress.md`: current implementation, verification, and Git status.
- `docs/interview_notes.md`: concise explanation and interview follow-up questions.

## Roadmap

1. Add Docker and perform the final local delivery audit.
2. Add Admin Upload API and background processing state.
3. Replace Hash Embedding and the evidence-only answer generator with production provider adapters.
4. Add structured conversation state so Chat can invoke the existing safe write Tool without accidental execution.
4. Safe leave-request workflow with confirmation, final revalidation, transaction, and idempotency.
5. Docker and cloud deployment.
