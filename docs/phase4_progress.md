# Phase 4 Progress

Last updated: 2026-09-15

## 2026-09-15 OCR/Vision Phase 8

- 分支feature/ocr-vision-phase8-image-ui；起点0eeba85。
- 来源卡片按需查看图片；fetch携带当前身份，禁止外部URL与重定向；Blob预览不泄露本地路径。
- 403/404/网络/非图片响应显示提示；重新加载重新授权。身份切换清理旧结果、取消图片请求并释放Blob URL。
- 前端4组Node测试通过；后端122 passed、1 skipped，保留1条原有警告。未进行真实浏览器视觉验收、真实Gemini/OCR效果验收。
- 修改static页面/脚本/样式、前端测试及文档。下一步：浏览器端到端验收，使用虚构资料验证图片显示与权限拒绝，再评估真实识别效果。
- 无push/merge；AGENTS.md不纳入提交。浏览器已接收的图片无法通过后端撤权追回；重新请求会检查权限。

## 2026-09-15 OCR/Vision Phase 7

- 分支feature/ocr-vision-phase7-image-api；起点38823c4。
- 完成授权图片API、版本归属校验、路径保护和Citation链接；未修改UI。
- 全量122 passed、1 skipped、1条原有Starlette警告；覆盖权限拒绝、失效、缺图及引用生成后撤权。
- 下一步Phase 8前端展示。真实Gemini和OCR效果仍未验收。
- 仅保存本地提交，不push/merge；未跟踪AGENTS.md不纳入提交。

## 2026-09-15 OCR/Vision Phase 6

- 分支 feature/ocr-vision-phase6-pipeline；DocumentService已接入统一parse_document入口。
- Excel可选off/vision/ocr；单图失败后其他内容正常索引，记录Excel图片统计。
- PDF可注入OCR并传递文档版本；异常隔离到单页。真实OCR仍待选择。
- 实际Excel混合内容、单张Vision失败、OCR模式、默认关闭、跨Sheet失败序号和PDF单页异常已验证。
- 全量113 passed、1 skipped、1条原有警告。真实Gemini测试默认跳过。
- 下一步Phase7：按文档权限提供图片访问API与图片Citation URL。

## 2026-09-15 OCR/Vision Phase 5

- 分支 feature/ocr-vision-phase5-vision；起点 8e4f03e。
- 新增 VisionProvider、FakeVisionProvider、VisionContext/Description/Result 及 VisionBlockService。
- Gemini REST 适配支持超时、配置缺失、安全失败和结构化输出校验。
- 定向12 passed；全量108 passed、1 skipped、1条原有第三方警告。跳过项为真实云调用，未上传真实文档。
- 未接入默认上传；下一步 Phase 6 组装文档解析、图片策略与单图失败隔离。

## 2026-09-14 Excel 边界修正

修正单行闭合表格、两行表头的关联距离、无关前置段落误关联。附加说明正文标明自身来源。新增4项回归，全量96 passed，保留1条原有第三方警告。下一步为 OCR/Vision Phase 5；空白边缘及同组相邻表格仍有已知限制。

## Current Scope

OCR / Vision Phase 6 已接入上传并通过离线测试，等待 Phase 7 实现授权图片访问。真实 OCR 和真实 Gemini 效果尚未验收。

## 2026-09-13 Excel 表格识别改进

- 当前分支：`feature/excel-bordered-table-context`，从 OCR Phase 4 提交 `342fd07` 创建。
- 废止“连续多行且不是 Key-Value 就默认为 Table”的宽松规则。
- 键值对仍优先识别；其余候选区域必须超过两个单元格且外边框形成闭合矩形，才分类为 `table`。
- 无边框或边框不闭合的连续多行保留换行并分类为 `paragraph`。
- 同一 Sheet 中距离最多一行空白的前置标题/说明和后置备注，会加入表格检索正文。
- 无边框说明紧贴有边框表格时，会先按边框状态变化拆分，再进行关联。
- 独立标题与备注 Block 仍保留；表格 `cell_range` 不扩大，继续表示真实表格位置。
- 新增无边框多行、闭合边框、开放边框和表格上下文测试。
- 原有 `app/services/document_service.py` 学习注释属于项目所有者修改，本轮不覆盖、不纳入功能范围。
- Excel 定向测试：`9 passed`。
- 全量测试：`92 passed`，保留 1 条与本功能无关的第三方 Starlette 弃用警告。

## 2026-09-13 OCR / Vision Phase 4 已完成

- 当前分支：`feature/ocr-vision-phase4-pdf-ocr`，从 Phase 3 提交 `f4301f6` 创建。
- 新增 `OcrProvider`、`OcrResult` 和不联网的 `FakeOcrProvider`。
- 新增 `PdfPageRenderer` 与本地 `PyMuPdfPageRenderer`，当前验证版本为 PyMuPDF `1.28.2`。
- `PdfDocumentParser` 优先使用原生文字层；只有已配置 OCR 且非空白文字少于默认 20 字符时才 fallback。
- 扫描页渲染后先保存到版本 assets，再交给 OCR；成功结果生成统一 ParsedBlock。
- 原生文字 Block 明确记录 `extraction_method=text_layer`；OCR Block 记录 `modality=image` 和 `extraction_method=ocr`。
- OCR 结构化失败只记录 warning 并跳过该页，不把错误信息写进正文。
- 真实图片型 PDF、真实 PyMuPDF Renderer 与 Fake OCR 的集成路径已验证。
- Phase 4 定向测试：`14 passed`。
- 全量测试：`87 passed`，保留 1 条第三方 Starlette 弃用警告。
- 默认 DocumentParserRegistry 尚未配置 OCR，当前上传 API 尚不会自动 OCR；正式组装留到 Phase 6。
- 尚未实现真实云 OCR、Vision Provider、授权图片 API 或前端图片展示。
- 安全停止点：Phase 4 完成后停止，下一步须等待项目所有者指令。

## 2026-09-13 OCR / Vision Phase 3 已完成

- 当前分支：`feature/ocr-vision-phase3-excel-images`，从 Phase 2 提交 `91c4220` 创建。
- 新增 `ExcelImageExtractor`，遍历 Workbook/Worksheet 中 openpyxl 可读取的普通嵌入图片。
- 新增内部结果 `ExtractedExcelImage`，保留 image_id、内部路径、全 Workbook 序号、MIME、Sheet 和可靠锚点。
- 图片 bytes 交给 Phase 2 的 `LocalImageAssetStorage`，没有重复实现目录或 image_id 规则。
- 图片序号跨 Sheet 连续递增；无法可靠取得锚点时允许 `None`。
- `ExcelDocumentParser` 的现有文字解析代码没有修改。
- `pyproject.toml` 新增 Pillow 直接依赖；当前验证版本为 `12.3.0`。
- Phase 3 定向测试：`12 passed`。
- 全量测试：`79 passed`，保留 1 条第三方 Starlette 弃用警告。
- 尚未接入 OCR、Vision、DocumentService、Chroma、Citation 或前端。
- 安全停止点：Phase 3 完成后停止，下一步须等待项目所有者指令。

## 2026-09-13 OCR / Vision Phase 2 已完成

- 当前分支：`feature/ocr-vision-phase2-image-storage`，从 Phase 1 提交 `11bd113` 创建。
- 新增 `StoredImageAsset`，只用于服务器内部表示已保存的派生图片。
- 新增 `LocalImageAssetStorage`，提供 `store/find/read/delete`。
- 图片保存到 `document_storage/{document_id}/{document_version_id}/assets/`。
- image_id 根据文档、版本、图片序号、MIME 和内容哈希稳定生成。
- 支持 PNG、JPEG、GIF、BMP、WebP MIME 白名单。
- 拒绝空内容、不合法序号、非法 image_id、非白名单 MIME 和路径跳转标识。
- Phase 2 定向测试：`12 passed`。
- 第一次全量测试因沙箱不能写现有 `chroma_data`，结果为 `73 passed, 2 failed`；获得本地写权限后未修改代码直接重跑。
- 最终全量测试：`75 passed`，保留 1 条第三方 Starlette 弃用警告。
- 尚未修改 Excel/PDF Parser，尚未接入 OCR、Vision、图片读取 API 或前端展示。
- 安全停止点：Phase 2 完成后停止，下一步须等待项目所有者指令。

## 2026-09-10 OCR / Vision Phase 1 已完成

- 当前分支：`feature/ocr-vision-phase1-metadata`，从提交 `e591e20` 创建。
- 复用现有 `ParsedBlock -> IndexedChunk -> Chroma -> RetrievedChunk -> SourceCitation`，没有建立平行模型。
- `ParsedBlock` 新增 `modality`、`extraction_method`、`image_id`、`image_path`、`image_index`、`mime_type`、`confidence`。
- `IndexedChunk`、`RetrievedChunk` 和 `SourceCitation` 传递安全的图片证据 metadata。
- `image_path` 只保留在解析层内部，不进入 Chunk、Chroma 或 API。
- Chroma metadata 白名单已增加图片证据字段，不保存二进制、Base64、路径或 URL。
- Phase 1 的 `SourceCitation.image_url` 保持 `None`，等待后续安全图片访问接口。
- 旧文本 Chunk ID 仍按原字段与原顺序计算，避免已有索引 ID 无故变化。
- 定向测试：`20 passed`。
- 全量测试：`71 passed`，保留 1 条第三方 Starlette 弃用警告。
- 尚未实现图片存储、图片提取、OCR、Vision、图片访问 API 或前端图片展示。
- 安全停止点：Phase 1 完成后停止，下一步须等待项目所有者指令。

## 2026-09-04 隔离开发说明

- 原复习目录：`D:\AI\enterprise-ai-support-agent`，保持在 `feature/phase4-core-backend`，未修改。
- 独立开发目录：`D:\AI\enterprise-ai-support-agent-complex-doc`。
- 当前开发分支：`feature/complex-doc-day5-demo-ui`。
- 开发起点：提交 `8a1256a`。
- 原目录的未跟踪学习文件没有复制到开发工作树。
- Day 1～Day 5 均只在独立工作树开发，原复习目录没有被本轮代码覆盖。

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

## Day 3 已完成

- 当前开发分支：`feature/complex-doc-day3-pdf-metadata`，从 Day 2 提交 `2aa45b5` 创建。
- 将 PDF Parser 从通用 Registry 文件分离到 `app/document_processing/pdf_parser.py`。
- 只处理存在文本层的 PDF，不添加 OCR 或图片理解。
- 对每页顶部和底部候选行进行跨页重复检测，规范化页码后清理重复页眉页脚。
- 按标题与正文生成 `title` / `paragraph` Block，保留 `page` 和 `section`。
- Chunk 不跨页；单行超长时只在当前页内切分。
- `content_type` 和 `cell_range` 已从 ParsedBlock 贯通 IndexedChunk、Chroma 检索结果和 SourceCitation。
- 使用完全虚构的三页日语 HMI PDF 进行真实文件解析测试，并逐页渲染检查。
- Day 3 定向测试：`16 passed`；项目全量：`50 passed`，保留 1 条第三方 Starlette 弃用警告。
- Day 3 已保存到当前本地分支的独立提交。

## Day 4 已完成

- 当前开发分支：`feature/complex-doc-day4-citation-evaluation`，从 Day 3 提交 `e1bddee` 创建。
- 新增 `RetrievalFilter`，支持按 document、文件名、结构类型和 Sheet 缩小检索范围。
- Authentication/Authorization 的版本条件与 metadata 条件在 Chroma `where` 中使用 AND 合并；过滤条件不能扩大权限。
- Chat API、AgentRouter、SearchDocumentTool 和 RagService 已贯通可选过滤条件。
- Citation 新增程序生成的 `location` 与检索 `score`，支持 PDF Page 和 Excel Sheet/Cell Range 显示。
- 相同原文定位的 Citation 去重，保留检索顺序中最高分结果。
- 新增通用检索评测模块与六题虚构 HMI 回归用例。
- 评测结果：Retrieval Hit Rate、Source Hit Rate、No Evidence Accuracy 均为 `1.0`；只代表固定小样本回归通过。
- Day 4 定向测试：`21 passed`；项目全量：`58 passed`，保留 1 条第三方 Starlette 弃用警告。
- Day 4 已保存到当前本地分支的独立提交；未执行 push。

## Day 5 已完成

- 当前开发分支：`feature/complex-doc-day5-demo-ui`，从 Day 4 提交 `c65321b` 创建。
- 使用 FastAPI + 原生 HTML/CSS/JavaScript 建立本地工作界面，没有引入独立前端框架。
- 界面包含 Mock 身份、聊天、metadata 筛选、PDF/Excel 上传、文档状态和 Citation 展示。
- 新增 ADMIN 文档上传和版本状态 API；上传仅允许 PDF/XLSX、非空且最大 10 MB。
- 上传成功后给上传用户授予 read permission；非 ADMIN 请求返回 403。
- API 响应不返回服务器存储路径。
- 真实 E2E 首次发现 Citation 使用随机临时文件名，已将原始文件名从临时路径中独立传递并增加回归测试。
- 修正后真实上传虚构 PDF 生成 12 个 Chunk，Chat 返回 Page 2 正确证据和原始文件名 Citation。
- Day 5 相关测试 9 项通过；项目全量 65 项通过，保留 1 条第三方 Starlette 弃用警告。
- Python compileall、JavaScript `node --check` 和 Git diff check 通过。
- Day 5 已保存到当前本地分支的独立提交；未执行 push。

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
  are included in the current full-suite result: 50 tests passed.

## Git Status

- Current development branch: `feature/complex-doc-day5-demo-ui`
- Original review branch remains: `feature/phase4-core-backend`
- Day 1 is stored in local commit `ab09e45`.
- Day 2 is stored in local commit `2aa45b5`.
- Day 3 is stored in the current branch's dedicated local commit.
- Day 4 is stored in the current branch's dedicated local commit.
- Day 5 is stored in the current branch's dedicated local commit.
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

Day 5 已安全保存。Day 6 进行 Docker、本地交付验证、README/架构图/面试资料一致性审计，并准备 PR；不自动 push 或 merge。

## Handoff Summary

三条业务主链、Document Ingestion 和本地 Chroma 已保存于本地提交。复杂文档 Day 1～Day 5 已分别提交；Day 5 的本地 UI、上传、状态和 Citation 展示已通过 65 项全量测试。尚未执行 push 或 merge，原复习目录和其中的学习文件未被本轮开发覆盖。
