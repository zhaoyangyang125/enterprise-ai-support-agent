# Enterprise AI Support Agent

## 可选图片理解（Phase 6）

默认只解析原生文字。需要Excel图片理解时，在启动服务的终端设置 `DOCUMENT_IMAGE_MODE=vision`、`GEMINI_API_KEY` 和 `GEMINI_VISION_MODEL`，然后重新启动。密钥不要写入代码或提交到Git。模型名使用你的Gemini账户可用且支持图片和结构化输出的模型。

开启后，上传会把提取出的图片发送给Gemini，可能产生费用；请使用虚构或已获准的资料。已有索引不会自动更新，需要上传新版本。图片不足32像素宽/高会跳过，单图失败记录警告，其余可用内容仍正常索引；整份文档无可用内容则失败。图片引用URL和网页原图展示尚待Phase7/8。

PDF扫描页OCR支持依赖注入，真实OCR厂商尚未配置，单独开启Vision不会自动识别扫描PDF。默认测试不调用云端；当前全量113项通过、1项真实调用测试跳过。

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

### 图片证据前端（Phase 8）

带image_url的来源卡片新增“查看图片”。点击后携带身份Header请求图片，不会自动调用Vision模型。重新加载会重新授权；切换身份清除旧聊天和图片。已下载内容无法靠撤权追回，生产系统仍需要真正的认证。

前端测试：`node --test tests/image_evidence.test.cjs`（4组通过）；后端122项通过、1项跳过。真实浏览器视觉与云识别效果仍待验收。

### 图片访问（Phase 7）

Citation的image_url指向`GET /api/documents/{document_id}/versions/{version_id}/assets/{image_id}`。每次请求重新验证有效版本权限；无权限403，授权后归属不符或缺图404，非法编号或缺少身份参数422。响应设置no-store及nosniff；不公开存储目录，不返回本地路径。

调用须携带开发用身份Header（例如X-User-Id），Mock身份不是生产认证。直接点击链接不会自动添加Header；前端预览留待Phase 8。当前122项测试通过，1项真实Gemini测试跳过。

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
