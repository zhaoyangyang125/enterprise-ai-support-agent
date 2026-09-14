# Project 3 Development Journal / 开发日志

## 2026-09-14 表格边界复核

发现并修正单行提前返回、使用数据行而非表头位置计算距离、相邻段落无条件关联三个问题。附加上下文增加自身来源标记。新增4项回归，全量96项通过；空白边缘及复杂相邻表格仍属于已知限制。

| 项目 | 内容 |
|---|---|
| Purpose | 记录 Codex 自主开发过程、关键决定、验证结果、Git 保存位置和面试要点 |
| Last Updated | 2026-09-01 |
| Update Policy | 每完成一个正式纵向切片或重要技术决定后更新 |

## 工作规则

- 正式功能必须从式样与验收条件开始，不把练习功能写成正式需求。
- 每个里程碑记录调用链、设计决定、修改文件、测试结果和已知限制。
- `practice/` 与正式提交隔离。
- Git commit 保存到当前本地 feature branch；未经授权不 push、不建 PR、不部署。
- 未完成的 Roadmap 不在面试材料中描述为已完成。

---

## 2026-09-01 — Milestone 1: Authorized DB Read

### 功能

员工查询自己的年假余额：`GET /api/me/leave-balance`。

### 关联式样

- `REQ-F-005`：员工可以查询自己的年假余额。
- `REQ-F-016`：员工不能查询其他员工的个人业务数据。
- `FN-LEAVE-001`：年假余额查询。
- `API-002`：Self-only leave balance API。

### 调用链

```text
X-User-Id
-> CurrentUser
-> FastAPI API
-> LeaveService
-> LeaveRepository
-> SQLAlchemy
-> SQLite
-> LeaveBalanceResponse
```

### 关键决定

- API 不接受目标 `user_id`，Service 只使用 `current_user.user_id`。
- `X-User-Id` 仅用于本地 Mock Authentication，生产认证尚待替换。
- `balance_id` 是余额实体主键；`user_id` 是 FK + UNIQUE。
- 余额为 0 是正常业务数据，Repository 返回 `None` 表示记录不存在。
- Service 抛出不依赖 HTTP 的 `LeaveBalanceNotFoundError`。
- API Error Handler 将业务异常映射为 HTTP 404。
- `unit = "day"` 只属于 Response Schema，不存入数据库。

### 验证

- Service unit tests：正常余额、零余额、记录不存在。
- API tests：HTTP 200、HTTP 404、缺少认证 Header。
- Repository integration tests：内存 SQLite 中记录存在与不存在。
- 正式纵向切片：8 tests passed。
- 当前全量测试（包括本地练习）：11 tests passed。
- 已知第三方警告：Starlette TestClient 的 HTTP 客户端弃用提示；不影响当前测试结果。

### 面试要点

- Self-only API 通过不接受目标 ID 和使用认证上下文限制查询对象。
- Service、API、Repository 分层测试分别隔离业务规则、HTTP 边界和 SQL 查询。
- 业务异常与 HTTP 解耦，为未来 Agent Tool 复用 Service 做准备。

### Git

- Branch：`feature/phase4-core-backend`
- Formal files 已选择性暂存。
- Learning-only `practice/` 未暂存。
- Local commit：`9acf307 feat: implement authenticated leave balance vertical slice`

---

## 2026-09-01 — Milestone 2: Authorized RAG Core

### 功能

在接入 Chat API、Agent 和真实 LLM 前，先实现并验证 RAG 最关键的安全核心：检索前权限过滤、有效版本过滤、证据阈值和 metadata citation。

### 关联式样

- `REQ-F-001`～`REQ-F-004`：权限内文档问答、有效文档、引用、无证据拒答。
- `NFR-SEC-001`：Authorization 必须发生在 Retrieval 前。
- `FN-RAG-001`：权限与版本过滤后的 Semantic Retrieval。
- Permission Matrix：`company_document / read` 为 role、department、explicit permission + active version。

### 当前调用链

```text
CurrentUser + Query
-> AuthorizationService
-> DocumentAccessRepository / Business DB
-> allowed_document_version_ids
-> RagService
-> VectorRepository.search(...allowed ids...)
-> evidence threshold
-> AnswerGenerator
-> metadata-based SourceCitation
```

完整上位调用链中的 `ChatController -> AgentRouter -> SearchDocumentTool` 将在后续里程碑接入。

### 关键决定

- Business DB 决定用户可读的有效 DocumentVersion；LLM 不参与 ALLOW/DENY。
- Vector Repository 在 Retrieval 查询阶段应用允许版本集合，不能先取回越权内容再过滤。
- citation 由 Chunk metadata 组装，Answer Generator 不能生成来源字段。
- 无权限、无结果或低于阈值均返回 No Evidence，并跳过 Answer Generator。
- 先用接口和本地确定性实现验证边界；Chroma、Embedding 和真实 LLM 仍未锁定。

### 修改范围

- 扩展 Mock `CurrentUser`，支持可选 department 和 role context。
- 增加 `Document`、`DocumentVersion`、`DocumentPermission` Business DB 模型。
- 增加 SQLAlchemy 文档访问权限 Repository。
- 增加 Vector Repository Protocol 与本地字符 n-gram 检索实现。
- 增加 `AuthorizationService`、`RagService`、Answer Generator Protocol。
- 增加 RAG response、retrieved chunk 和 source citation schemas。

### 验证

- 4 个 RAG Service unit tests：有证据、无权限、无结果、低分。
- 3 个 Document Access Repository integration tests：user、department/role、无权限/无效版本。
- 1 个本地 Vector Repository test：越权内容即使更相似也不能返回。
- 全量测试：19 passed（包含 3 个 learning-only practice tests）。
- 已知第三方警告仍为 Starlette TestClient 弃用提示。

### 面试要点

- “先检索再过滤”已经太晚，因为越权内容可能已经进入应用内存或 LLM Context。
- 权限与有效版本来自结构化 Business DB；向量库只负责允许范围内的相似度检索。
- No Evidence 是正常 AI 质量结果，不等于系统异常。

### Git

- Local commit：`8b6d8fc feat: add authorized RAG core`

---

## 2026-09-01 — Milestone 3: Chat Agent / Tool Integration

### 功能

将两个已经验证的只读业务能力接入统一 `POST /api/chat`：余额问题调用 `GetLeaveBalanceTool`，公司规则问题调用 `SearchDocumentTool`。

### 调用链

```text
POST /api/chat + CurrentUser
-> AgentRouter
   -> GetLeaveBalanceTool -> LeaveService -> Business DB
   -> SearchDocumentTool -> RagService -> Authorized Retrieval
-> ChatResponse
```

### 关键决定

- Agent 负责意图分类和 Tool 选择，不写业务规则、不访问数据库。
- Tool 是 Agent 到 Service 的受控桥梁，不重复实现 Service 逻辑。
- 当前使用普通关键词路由，目的是让完整架构本地可运行、可测试。
- 真实 LLM Intent Classifier 仍是可替换组件；面试时必须如实说明当前边界。
- Mock Authentication 新增可选 department/role headers，用于本地验证文档权限；生产仍需 JWT/企业 IdP。

### 验证

- 2 个 Agent tests：余额意图和知识意图只选择对应 Tool。
- 3 个 Chat API tests：认证上下文传递、缺少认证、空消息。
- 全量测试：24 passed。
- 真实本地 smoke test：余额问题和公司规则问题均通过 `/api/chat` 返回 HTTP 200。
- RAG smoke response 包含真实 metadata citation：文件名、文档版本、第 3 页和 Section。

### 本地演示数据

- 用户：`U001`
- 年假余额：`8.0 day`
- 文档：`TRAVEL_POLICY / TRAVEL_POLICY-V1`
- 权限：`U001` explicit read
- 本地 Chunk：国内出差住宿费上限，第 3 页。

### Git

- Local commit：`9e1a513 feat: connect chat agent to read tools`

---

## 2026-09-01 — Milestone 4: Safe Leave Request

### 功能

实现 `REQ-F-007～015` 的两阶段年假申请：Prepare 显示确认信息，Confirm 后再验证并在单一事务中预留余额、创建申请、消费 token，同时支持幂等重试。

### 调用链

```text
Prepare API
-> CurrentUser + dates
-> LeaveRequestService.prepare
-> balance / overlap validation
-> PendingLeaveAction(WAITING_CONFIRMATION)

Confirm API + Idempotency-Key
-> explicit confirmed=true
-> transaction
-> idempotency lookup
-> token/user/expiry validation
-> final balance/rule/overlap revalidation
-> conditional balance reservation
-> LeaveRequest INSERT
-> token EXECUTED
-> COMMIT
```

### v1 实现决定

- 只支持整天；计算周一至周五，暂不处理法定节假日。
- 超过 3 个工作日需要审批。
- 申请创建时立即预留余额，避免并发未审批申请超额。
- `Idempotency-Key` 在用户范围内唯一。
- 同 key + 同 token 重试返回同一结果；同 key + 不同 token 返回冲突。
- 普通自然语言 Chat 暂不直接执行写操作；`CreateLeaveRequestTool` 已实现，但要等结构化会话状态接入。

### 验证

- 9 个 Service tests：Prepare、日期/余额错误、Final Revalidation、成功、幂等、冲突和并发 UNIQUE 恢复。
- 2 个 Repository integration tests：真实事务提交与 INSERT 后故障回滚。
- 4 个 API tests：预览、HTTP 201、未确认、缺少幂等键。
- 1 个 End-to-End test：真实 HTTP Prepare/Confirm/Retry，数据库一条申请、余额只扣一次。
- 1 个 Tool test：两个阶段均转发到同一个安全 Service。
- 项目全量：41 passed。

### 故障注入结果

测试在余额 UPDATE 和 LeaveRequest INSERT 后主动抛出异常。事务回滚后：余额仍为 8.0、申请记录不存在、PendingLeaveAction 仍为 `WAITING_CONFIRMATION`。这证明不会出现部分成功。

### 面试要点

- Confirmation 证明用户意愿，Final Revalidation 证明当前状态仍允许，两者不能互相替代。
- Transaction 防止部分成功，Idempotency 防止重复成功，解决的是不同问题。
- 原子条件 UPDATE 是余额并发安全的最终检查，不能只依赖 Prepare 时看到的余额。

---

## Next Milestone

Docker 和最终验收材料。

---

## 2026-09-01 — Milestone 5: Document Ingestion / Chroma

### 完成内容

- PDF：保留 page，按自然段组合 Chunk；v1 不含 OCR。
- Excel：展开 merged cell，按 Sheet、Header、Row 生成语义记录。
- 原文件复制到按 document/version 分层的 Document Storage。
- Business DB 使用 `processing -> active/failed` 记录跨存储处理结果。
- Chunk 使用稳定 SHA-256 ID，并保留 citation metadata。
- 本地 Hash Embedding 完全离线且可重复。
- Chroma 1.5.x `PersistentClient` 保存本地索引，并在 query where 中应用 allowed version IDs。
- 运行时 RAG 已从 InMemory Repository 切换到持久化 Chroma；seed 同时写入演示 Chunk。

### 验证

- Excel structure/merged-cell parser test。
- PDF page/paragraph parser test。
- Chroma retrieval-time authorization filter test。
- Chroma restart persistence test。
- DocumentService success/active test。
- Vector failure/failed-state test。
- 最终全量测试：47 passed（另有 1 条第三方 Starlette TestClient 弃用警告）。

### 诚实边界

- Hash Embedding 是本地工程演示，不是生产语义模型。
- Scanned PDF OCR、复杂 Excel region detection 阈值和异步任务队列仍未完成。
- 当前完成的是本地文件 Ingestion Service；Admin Upload API 尚未实现。

---

## Next Milestone

Docker、最终全量运行验证、文档一致性审计和面试交付包。

---

## 2026-09-04 — Milestone 6 / Day 2: Complex Excel Region Detection

### 本次目标

把“第一个非空行就是整张 Sheet 表头”的简单 Parser，升级为先识别 Region、再转换语义 Block 的结构化 Parser。

### 数据流

```text
Workbook / Sheet
-> 非破坏式 merged-cell view
-> 空白行、合并标题和 Section 边界
-> Title / Key-Value / Table / Note / Paragraph
-> ParsedBlock
```

### 核心实现

- `ParsedBlock` 新增 `content_type` 和 `cell_range`。
- 多行表头组合成父子路径，例如 `CAN信号 / 信号名`。
- 纵向合并的功能 ID 继承到相关数据行。
- 标题型横向合并只保留一次，不复制成多个字段。
- 同一 Sheet 的第二张表重新识别 Header，不使用第一张表的 Header。
- Parser 不 unmerge 或改写原 Workbook，而是在内存中建立只读逻辑视图。

### 测试发现的问题

第一次全量测试中，只有两列两行的 `Rule / Value` 普通表被误判为 Key-Value，导致旧 `rows="2"` 变成 `rows="1:2"`。

根因是“两列”本身不能证明它是 Key-Value。修正为：两列两行默认按 Table；两列 Key-Value 至少三行，多组 Key-Value 可通过中间空列判断。

此外明确区分：

- `cell_range`：包含 Header 的完整原始范围。
- `rows`：兼容旧 Citation，只表示 Table 的数据行。

### 验证

- 复杂 Excel 和 DocumentService 定向测试：7 passed。
- 项目全量测试：47 passed。
- PDF、Chroma、Authorized RAG、年假余额和安全年假申请均未回归。

### 面试要点

- 复杂 Excel 不能默认一个 Sheet 只有一张表。
- 合并单元格处理必须区分标题合并和数据合并。
- 结构分类存在歧义时，应选择保守默认值并用回归测试固定行为。
- Citation 定位由 Parser metadata 产生，而不是让 LLM 猜测。

## 2026-09-05 — Milestone 6 / Day 3: PDF 与统一 Metadata

### 本次目标

让文字型 PDF 的检索结果不仅“能读到文字”，还能够排除重复页眉页脚、识别章节，并把准确页码一直带到 Citation。

### 数据流

```text
PDF 每页文本
-> 页边重复模式检测
-> 标题/正文识别
-> 页内 Chunk
-> ParsedBlock
-> IndexedChunk
-> Chroma metadata
-> SourceCitation
```

### 核心规则

- 只检查每页顶部和底部的候选行，避免删除正文中的重复业务句子。
- 页边文本至少出现在 60% 页面并覆盖不少于 2 页时，才视为重复页眉页脚。
- 页码数字先转换为占位符，因此不同页的 `Page 1 / 3`、`Page 2 / 3` 能够匹配。
- 标题生成 `title` Block，同时成为后续正文的 `section`。
- Chunk 不跨页，优先保证 Citation 页码准确；超长文本只在当前页内切分。

### 为什么不能只依赖 PDF 文本提取

`pypdf` 能够拿到文本，不代表已经理解文档结构。直接把每页文本整体送去 Embedding，会让每个 Chunk 重复包含页眉页脚，也无法说明某段正文属于哪个章节。本次在文本提取后增加了确定性结构整理，但没有声称支持扫描件或视觉表格。

### Metadata 贯通

Day 2 已让 Excel Parser 产生 `content_type` 和 `cell_range`。Day 3 将这两个字段继续传入 IndexedChunk、Chroma 和 SourceCitation。这样 API 返回的来源位置来自 Parser 和索引数据，不需要 LLM 猜测。

为了兼容旧 Chroma 数据，缺少 `content_type` 的旧记录按 `paragraph` 读取，不要求立刻重建全部本地索引。

### 验证

- 完全虚构的三页日语 HMI PDF 能提取日文文本。
- 三页渲染结果均已人工查看，无截断或排版问题。
- 重复页眉、版本行和页脚没有进入 ParsedBlock。
- PDF/metadata 相关测试：16 passed。
- 项目全量测试：50 passed；只有 1 条第三方 Starlette 弃用警告。

### 面试要点

- PDF 有文本层只解决“能提取文字”，结构和 Citation 仍需程序处理。
- 页眉页脚删除应使用保守规则，并限制在页面边缘。
- 不跨页 Chunk 是为了让页码 Citation 可验证。
- metadata 必须从 Parser 一直贯通到检索结果，不能在回答阶段临时猜测。

## 2026-09-05 — Milestone 6 / Day 4: Filtering、Citation 与 Evaluation

### 本次目标

让用户能够按文档结构缩小搜索范围，同时确保这些条件永远不能绕过原有权限过滤；并用可重复运行的指标验证检索和来源定位。

### 调用链

```text
ChatRequest.retrieval_filter
-> AgentRouter
-> SearchDocumentTool
-> RagService
-> AuthorizationService 取得允许版本
-> VectorRepository.search(允许版本, metadata 条件)
-> Chroma AND where
-> evidence threshold
-> SourceCitation(location, score)
```

### 权限与筛选的区别

- 权限回答“这个用户能不能看到该文档”，只能由可信 Authentication Context 和 Business DB 决定。
- metadata filter 回答“用户想在已经允许的资料中看哪一部分”，例如只看 Excel Table 或 `CAN信号` Sheet。
- Filter 只能缩小集合，不能把新的文档版本加入权限集合。

### Citation

Citation 继续保留结构字段，并增加适合界面显示的 `location` 和检索 `score`。PDF 显示 `文件 / Page N`，Excel 显示 `文件 / Sheet / Cell Range`。这些字段由程序组装，不由 LLM 生成。

同一原文位置可能被多个 Chunk 命中。去重键不包含 score，因此排序靠前的最高分结果被保留，不会在界面显示重复来源。

### 小型评测

评测把有答案问题和无答案问题分开统计：

- Retrieval Hit Rate：Top-K 是否包含预期 Chunk。
- Source Hit Rate：是否命中人工确认的文件和位置。
- No Evidence Accuracy：负例是否真的返回空集合。

六题固定回归结果均为 1.0，但这不能解释成生产准确率，因为数据量很小，且使用的是确定性本地检索。正式阈值和模型质量需要更大的人工标注集。

### 验证

- Repository、RAG、Agent、API 和 Evaluation 定向测试：21 passed。
- 全量测试：58 passed。
- 1 条第三方 Starlette 弃用警告仍不影响行为。

### 面试要点

- 权限条件和用户筛选条件必须使用 AND，不能让筛选参数改变授权结果。
- Citation 的定位和分数属于程序数据，不是模型生成文本。
- 指标必须先定义再计算；小型回归测试不能冒充线上准确率。

## 2026-09-05 — Milestone 6 / Day 5: 本地演示工作界面

### 本次目标

把已经完成的后端能力变成面试和本地验收时可以直接操作的工作界面：上传虚构文档、查看状态、提出问题并检查 Citation。

### 技术选择

项目本身已经是 FastAPI 应用，因此使用原生 HTML/CSS/JavaScript，并由 FastAPI 提供静态文件。这样不需要为一个本地演示页增加 Node、React、打包工具和第二套部署流程。

### 上传链路

```text
Browser FormData
-> ADMIN + file boundary validation
-> temporary transport file
-> DocumentService
-> Business DB processing state
-> Document Storage
-> PDF/Excel Parser
-> Chroma
-> uploader read permission
-> active response
```

上传是业务写操作，因此不能只做文件选择按钮：后端检查 ADMIN 角色、文件扩展名、空文件和 10 MB 大小限制。返回结果删除 `stored_path`，避免向客户端暴露服务器目录。

### 真实 E2E 发现的问题

第一次真实上传和查询成功，但 Citation 显示 `tmpbiz__6yx.pdf / Page 2`。Fake Service 测试只确认 API 参数和返回结构，没有发现 `DocumentService` 使用了临时路径的随机文件名。

修正方法是把两个概念分开：

- `source_path`：服务器读取上传内容的临时路径。
- `source_name`：用户上传的原始文件名，经 `Path(...).name` 清理后用于 Storage 和 Citation。

修正后重新清理本轮生成的错误演示数据，再次上传同一虚构 PDF。系统生成 12 个 Chunk，Chat 返回 Page 2 的正确内容，Citation 变为 `fictional_hmi_policy.pdf / Page 2`。

### 界面设计

- 第一屏直接展示身份、聊天、筛选、上传和状态，不放营销 Hero。
- 所有服务端回答和 Citation 使用 DOM `textContent` 写入，避免把返回文本当成 HTML 执行。
- 显示 loading、empty、success 和 error 状态。
- 支持键盘焦点、小屏布局和减少动画设置。

### 验证

- 文档 API 与 DocumentService 定向测试：9 passed。
- 全量自动化测试：65 passed。
- Python 与 JavaScript 语法检查通过。
- 本地根路径和静态资源返回 HTTP 200。
- 真实上传 → Parser → Chroma → 权限 → Chat → Citation 链通过。

### 面试要点

- UI 不是核心业务逻辑，仍然只调用既有 API/Service。
- 上传文件名和服务器临时路径是不同数据，Citation 必须保留原始来源名。
- Fake 测试速度快，但真实 E2E 能发现对象组装和跨层传递问题。

## 2026-09-10 — OCR / Vision / Image Evidence Phase 1

### 本次目标

先让现有 RAG 数据链“认识”图片证据需要的 metadata。这个阶段不读取图片，也不调用 OCR 或 Vision。

### 为什么不另建一套图片模型

文字证据和图片证据最终都要经过索引、权限过滤、检索和 Citation。如果另建平行流程，会重复实现权限和检索逻辑，也更容易出现一条链漏掉安全检查。因此复用：

```text
ParsedBlock -> IndexedChunk -> Chroma -> RetrievedChunk -> SourceCitation
```

### 关键边界

- `content_type` 回答“它在文档中是什么结构”，例如表格或备注。
- `modality` 回答“证据来自文字还是图片”。
- `image_path` 是服务器内部位置，不能进入浏览器响应或向量数据库。
- `image_id` 是可以安全传递的逻辑标识，后续访问图片时再通过权限检查换成 URL。
- 旧文本 Chunk ID 不改变，避免升级 metadata 后把全部旧索引当成新数据。

### 验证

- Schema、DocumentService、Chroma、RagService 定向测试：20 passed。
- 全项目回归测试：71 passed。
- 保留 1 条第三方 Starlette 弃用警告，与本次功能无关。

### 当前停止点

Phase 1 已完成。图片存储、提取、OCR、Vision、图片访问 API 和前端展示均未开始，等待项目所有者发出下一步指令。

## 2026-09-13 — OCR / Vision / Image Evidence Phase 2

### 本次目标

建立最小本地图片资产存储，使后续 Excel/PDF Parser 提取图片后有统一保存位置。这个阶段不修改 Parser，也不调用 OCR 或 Vision。

### 数据流

```text
图片 bytes
+ document_id / document_version_id
+ image_index / mime_type
-> 生成稳定 image_id
-> 保存到对应 DocumentVersion 的 assets 目录
-> 返回 StoredImageAsset
```

### 设计理由

- 图片属于具体文档版本，所以和原文保存在同一版本目录下。
- 调用方使用 `store/find/read/delete`，不需要知道真实目录怎么拼接。
- image_id 包含内容哈希和来源身份，重复处理同一张图片时结果稳定。
- 外部输入不能直接成为文件路径；文档标识、image_id 和 MIME 都需要白名单或格式验证。

### 测试中遇到的问题

Phase 2 定向测试 12 项一次通过。第一次全量测试有两个旧 Chat API 用例失败，堆栈显示 Chroma 尝试写只读数据库。获得独立工作树写权限后，没有修改代码，原样重跑得到 75 项全部通过，因此判断为测试环境权限问题，而不是 Phase 2 回归。

### 当前停止点

图片保存、稳定 ID、查找、读取、删除和路径防护已经完成。Excel 图片提取属于 Phase 3，尚未开始。

## 2026-09-13 — OCR / Vision / Image Evidence Phase 3

### 本次目标

从 Excel 中提取 openpyxl 能读取的普通嵌入图片，保存原图并保留 Sheet、图片序号和可靠单元格锚点。暂时不调用 OCR 或 Vision。

### 为什么先使用独立 Extractor

现有 `ExcelDocumentParser` 已经稳定负责文字、表格和合并单元格。Phase 3 只验证“能否取出并保存原图”，因此先用独立 `ExcelImageExtractor` 控制变化范围。Phase 6 再由 DocumentService 统一组装文字 Parser 和图片流程，避免当前阶段同时改变太多模块。

### 数据流

```text
Workbook
-> Worksheet 普通嵌入图片
-> openpyxl 图片 bytes
-> MIME 与可靠 anchor
-> LocalImageAssetStorage
-> ExtractedExcelImage
```

### 实现注意点

- openpyxl 读取嵌入图片需要 Pillow，因此将它记录为项目直接依赖。
- openpyxl 当前没有公开的 Worksheet 图片迭代接口，私有 `_images` 和 `_data()` 被限制在一个组件内部，并用测试固定行为。
- openpyxl 对部分非 PNG/JPEG/GIF 图片会输出 PNG bytes，因此 MIME 必须按实际输出记录，不能只相信原文件扩展名。
- 没有可靠 anchor 时宁可返回 `None`，不能伪造 Cell Range。

### 验证

- 两个 Sheet 两张图片、稳定 ID、无图片 Workbook、原有文字 Parser：12 passed。
- 全项目回归：79 passed。
- 1 条第三方 Starlette 弃用警告与本阶段无关。

### 当前停止点

Excel 图片已能被提取和保存，但还没有可搜索文字。下一阶段 Phase 4 将建立 OCR Provider 与扫描 PDF fallback；等待项目所有者指令。

## 2026-09-13 — OCR / Vision / Image Evidence Phase 4

### 本次目标

为扫描 PDF 建立“原生文字优先、文字不足才 OCR”的 fallback，同时让 Parser 不依赖具体云厂商。

### 数据流

```text
page.extract_text
-> 文字充分：继续原有 PDF 规则
-> 文字不足：PyMuPDF 渲染 PNG
             -> LocalImageAssetStorage
             -> OcrProvider
             -> OcrResult
             -> ParsedBlock
```

### 为什么需要两个 Protocol

- `OcrProvider` 隔离 OCR 厂商，测试可以换成 Fake。
- `PdfPageRenderer` 隔离 PDF 渲染工具，Parser 不需要知道 PyMuPDF 的 API。

Parser 只负责决定什么时候需要 fallback，并把结果转换为 ParsedBlock。Renderer 负责产生图片，Storage 负责保存，Provider 负责识别文字。

### 失败策略

Fake OCR 可以返回 `success=False` 模拟 timeout。Parser 不把 `error_message` 当成正文，也不会因为单页结构化失败立即抛异常；如果最终没有任何 Block，DocumentService 仍会按主文档无可索引内容处理为 failed。

### 验证

- Fake OCR、PDF fallback、原生文字跳过 OCR、真实页面渲染：14 passed。
- 真实图片型 PDF 已经通过真实 PyMuPDF Renderer，并到达 Fake OCR。
- 全项目回归：87 passed。
- 1 条第三方 Starlette 弃用警告与本阶段无关。

### 当前停止点

OCR 接口和 PDF fallback 已实现，但默认上传流程尚未组装 OCR，真实云 OCR 也未选择。下一阶段是 Vision Provider；等待项目所有者指令。

## 2026-09-13 — Excel 闭合边框表格与上下文关联

### 为什么修改

代码复习时发现，旧规则会把“不是键值对的连续多行”全部当成表格，因此连续说明文字也可能误分类。项目所有者确认：表格应具有超过两个单元格的闭合边框矩形；没有闭合边框不能当作表格。

### 新数据流

```text
连续普通行
-> Key-Value 特征成立：key_value
-> 否则检查闭合外边框
   -> 闭合且超过两个单元格：table
   -> 不闭合：paragraph
-> 检查表格前置标题/说明与后置备注
-> 相关文字加入 table 检索正文
-> table 的 Cell Range 仍只指向真实表格
```

### 面试要点

第一版不能因为数据连续多行就认定它是表格。边框矩形是确定性结构证据；附近文字只通过有限距离和内容类型关联，避免把下一章节无条件合并。这里选择可解释、可测试的规则，没有使用缺少评测依据的主观分数。

### 验证

- 规则表格、无边框多行、闭合边框、开放边框、标题/备注关联、紧贴说明关联和既有复杂样本：9 passed。
- 全项目回归：92 passed。
- 保留 1 条与本功能无关的第三方 Starlette 弃用警告。
