# Enterprise AI Support Agent

## 可选图片理解（Phase 6）

默认只解析原生文字。需要Excel图片理解时，在启动服务的终端设置 `DOCUMENT_IMAGE_MODE=vision`、`GEMINI_API_KEY` 和 `GEMINI_VISION_MODEL`，然后重新启动。密钥不要写入代码或提交到Git。模型名使用你的Gemini账户可用且支持图片和结构化输出的模型。

开启后，上传会把提取出的图片发送给Gemini，可能产生费用；请使用虚构或已获准的资料。已有索引不会自动更新，需要上传新版本。图片不足32像素宽/高会跳过，单图失败记录警告，其余可用内容仍正常索引；整份文档无可用内容则失败。图片 Citation URL、受权限保护的图片 API、前端原图展示以及身份切换清理均已实现并完成真实浏览器验收。

PDF扫描页OCR现在可通过 `DOCUMENT_OCR_MODE=google` 接入Google Cloud Vision；单独开启Gemini Vision不会识别扫描PDF。默认测试不调用云端，两个live测试均需显式开启。详见下方真实Provider配置。

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
- 查看文档版本状态、结构化 Citation 和受权限保护的原始图片。

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

### 真实OCR / Vision配置（2026-09-16）

仅配置环境变量，不把真实密钥放入代码或此文档。默认关闭云识别；`FakeOcrProvider/FakeVisionProvider`只在测试或隔离演示中显式注入，生产配置不会自动回退为Fake。

```powershell
python -m pip install -e '.[test,ocr]'
# GEMINI_API_KEY 请在当前终端安全设置；不要粘贴到聊天或Git。
$env:GEMINI_VISION_MODEL = 'gemini-3.5-flash'
$env:DOCUMENT_IMAGE_MODE = 'vision'
# 以下是占位路径，请替换为仓库外自己的凭据路径。
$env:GOOGLE_APPLICATION_CREDENTIALS = 'C:\secure\service-account.json'
$env:DOCUMENT_OCR_MODE = 'google'
```

- Gemini：必须配置GEMINI_API_KEY；模型默认gemini-3.5-flash，可用GEMINI_VISION_MODEL覆盖。
- OCR：安装可选ocr依赖，官方SDK通过ADC加载凭据。本地使用GOOGLE_APPLICATION_CREDENTIALS；程序不手动读取JSON。Google Cloud项目必须启用Vision API和Billing。
- DOCUMENT_OCR_MODE=google只启用PDF文字不足页的OCR。Excel图片使用DOCUMENT_IMAGE_MODE=vision；若只想提取Excel图片文字，设置DOCUMENT_IMAGE_MODE=ocr并同时开启Google OCR。
- off为默认；未知模式记录警告并关闭对应功能。缺密钥、SDK或ADC时返回安全失败分类，保留其他可解析内容；全部无有效内容仍将文档标记failed，不假装成功。
- 单次OCR请求30秒超时，禁用SDK自动重试；confidence暂为null，不捏造准确率。
- Gemini发送手写简化responseJsonSchema，输出仍由VisionDescription校验。400/403/404/429分别返回vision_http_对应状态；日志保留状态和脱敏Google message，不记录请求图像、密钥或凭据。
- Service Account JSON不得提交Git，建议始终放仓库外；.gitignore覆盖常见凭据文件名但不能识别所有任意命名的JSON。不要开启SDK/HTTP底层调试日志共享凭据。

显式live测试（可能产生费用，仅上传测试生成的虚构图片）：

```powershell
$env:RUN_GEMINI_VISION_LIVE = '1'
python -m pytest tests/integration/test_gemini_vision_live.py -q
Remove-Item Env:RUN_GEMINI_VISION_LIVE

$env:RUN_GOOGLE_OCR_LIVE = '1'
python -m pytest tests/integration/test_google_ocr_live.py -q
Remove-Item Env:RUN_GOOGLE_OCR_LIVE
```

回归测试前确保两个RUN开关未设置或为0。API Key/模型/SDK在不同虚拟环境或终端里不一定相同。首次 live 失败请查看安全错误码和脱敏日志，不分享密钥或 JSON。旧实现只返回 `vision_http_error`，因此无法反推旧故障的唯一根因；2026-09-16 使用简化 Schema 后，Gemini Vision 和 Google OCR 的真实云调用均已验收通过。

官方依据：[Gemini请求与Schema](https://ai.google.dev/api/generate-content)、[Google文档OCR](https://cloud.google.com/vision/docs/handwriting)。

### 不需要API Key的隔离图片演示

在项目根目录执行 `python -m scripts.image_acceptance_demo`，打开 `http://127.0.0.1:8768`。

1. 用户保持U001，输入“虚构导航画面保持显示”，点击发送。
2. 来源应显示 `fictional.xlsx / Sheet Demo / B3`，点击“查看图片”显示虚构导航图。
3. 将用户改为U002，旧结果应清空；再次提问应无可用证据。

每次启动使用新的临时目录，不读取原业务数据库、原索引或原文档。Vision只返回固定测试描述，不代表真实识别效果；没有云调用费用。终端Ctrl+C停止服务。临时文件保留供检查，路径打印在终端；不要在进程运行时删除Chroma文件。此入口仅供本机验收，不用于生产部署。

### 图片证据前端（Phase 8）

带image_url的来源卡片新增“查看图片”。点击后携带身份Header请求图片，不会自动调用Vision模型。重新加载会重新授权；切换身份清除旧聊天和图片。已下载内容无法靠撤权追回，生产系统仍需要真正的认证。

前端测试：`node --test tests/image_evidence.test.cjs`（4 passed、0 failed）；后端离线回归为 146 passed、2 skipped。真实浏览器中的图片展示、身份切换清理、无权限检索隔离和旧图片 URL 403 均已验收通过。

### 图片访问（Phase 7）

Citation的image_url指向`GET /api/documents/{document_id}/versions/{version_id}/assets/{image_id}`。每次请求重新验证有效版本权限；无权限403，授权后归属不符或缺图404，非法编号或缺少身份参数422。响应设置no-store及nosniff；不公开存储目录，不返回本地路径。

调用须携带开发用身份 Header（例如 `X-User-Id`），Mock 身份不是生产认证。Phase 8 前端会通过 `fetch` 携带当前身份 Header，再以 Blob URL 展示图片；切换身份会清除旧聊天、Citation 和图片。真实验收已确认无权限用户无法检索证据，并且请求旧图片 URL 返回 403。

### 最终真实环境验收（2026-09-16）

所有验收文件和图片均为完全虚构数据，没有使用真实公司的式样书、图片或机密信息。

- 自动测试：Backend 146 passed、2 skipped；Frontend 4 passed、0 failed。
- 真实云调用：Gemini Vision live 1 passed（`gemini-3.5-flash`）；Google Cloud Vision document OCR live 1 passed。
- Excel：使用合法 ID 上传后状态为 active；两张图片均成功提取，一张遇到 Gemini 503 high demand 并被单图片故障隔离，另一张产生 Vision image Chunk。Chroma 中该版本共 7 条（6 text、1 image）。查询现代跨海桥梁成功命中 `Sheet1 / C67:N88`，页面成功显示原图。
- Excel 权限：切换为 `U999 / D-OTHER / EMPLOYEE` 后，旧聊天、Citation 和图片被清除；再次查询无证据；使用旧图片 URL 请求返回 403。
- 扫描 PDF：虚构 2 页 PDF 上传后状态为 active，产生 2 个 OCR image Chunk。查询安全代码成功命中 `Page 1`，页面成功显示该扫描页。
- PDF 权限：切换为无权限用户后旧结果被清除，再次查询无证据，旧 Page 1 图片 URL 返回 403。
- 完整链路已验证：上传 → Gemini Vision / Google OCR → Chroma → Citation → 图片展示 → 身份切换 → 无权限隔离 → 旧 URL 403。

### 当前已知限制

1. **自动 ID 生成不一致**：某些文件名会生成以 `-` 开头的 Document ID / Version ID，但 `LocalImageAssetStorage` 的安全路径规则要求首字符为字母或数字，因而可能出现 `image_extraction_failed`。当前可手工使用如 `TEST-EXCEL-001`、`TEST-EXCEL-001-V1` 的合法 ID；本轮只记录，不修改代码。
2. **Gemini 临时 503**：真实请求可能因 high demand 返回 503。当前单图片故障隔离会跳过失败图片，其余文字和图片继续处理；没有自动重试。
3. **Hash Embedding**：当前 deterministic Hash Embedding 用于离线架构、权限和 RAG 链路验证，不是生产级语义 Embedding，可能出现不相关 Citation。
4. **EvidenceOnly Answer Generator**：当前直接返回最高相关 Evidence Chunk，不会进一步生成精炼答案。例如询问最大速度时可能返回整段 OCR 文本，这不是 OCR 识别失败。
5. **Windows pytest 临时目录权限**：本机默认目录 `C:\Users\zyy\AppData\Local\Temp\pytest-of-zyy` 和 `.pytest_cache` 出现 WinError 5。使用此前不存在的新目录，例如 `--basetemp=.\.pytest_tmp_run1`，可完成 146 passed、2 skipped；这是当前开发机环境问题，不是业务代码失败。
6. **Mock 身份**：`X-User-Id`、`X-Department-Id`、`X-Role-Ids` 仍是开发用身份上下文，不是生产认证。浏览器已经取得的图片不能通过后端撤回，但后续请求会重新检查权限。

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
