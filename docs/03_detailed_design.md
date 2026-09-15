# 03 详细设计书 / Detailed Design

## v0.20 修订补充（2026-09-14，Draft）

本补充更新 §6.17 与 DD-062：前置 title/paragraph 必须以“表、下表、本表、以下の表、次の表、下記の表、Table ”等引导语开头。距离使用 cell_range 的物理范围并要求列重叠，不使用排除表头的 rows。单行超过两格也参与闭合检查。附加正文标明上下文自身的 Sheet/Cell Range；结构化 Citation 仍为表格范围。空白边缘、同组相邻表格和装饰边框仍有已知限制。新增4项回归，全量96项通过。

本文档记录 Project 3 在 Phase 4 实现过程中确认的详细设计。

本文档基于原始要件定义、基本设计以及开发过程中的确认结果持续更新。它不能覆盖或擅自修改上位式样；发现冲突时，必须回到原始式样重新确认。

---

## 0. 文档管理 / Document Control

| 项目 | 内容 |
|---|---|
| 文档名称 | Project 3 详细设计书 |
| Document Version | v0.21-draft |
| Status | Draft（草稿，尚未正式 Review） |
| Created Date | 2026-08-24 |
| Last Updated | 2026-09-15 |
| Prepared By | 项目负责人；Codex 辅助整理 |
| Reviewed By | Pending（待审阅） |
| Approved By | Pending（待批准） |
| Related Phase | Phase 4 Coding |
| Current Scope | 三条核心主链；Chat Agent/Tool；Document Ingestion、本地 Chroma、复杂文档解析、Excel 边框表格与上下文关联、OCR/Vision Phase 4 PDF OCR fallback |
| Related Requirements | `REQ-F-001`～`REQ-F-005`、`REQ-F-007`～`REQ-F-016`、`NFR-SEC-001` |

### 0.1 状态定义

- `Draft`：正在整理或实现，尚未正式审阅。
- `Under Review`：已经提交 Review，正在确认。
- `Approved`：已经审阅并批准，可作为正式开发依据。
- 未经过实际 Review，不得标记为 `Approved`。

### 0.2 信息来源分类

- `Original Specification`：原始 Excel 开发式样书或 Word 基本设计书明确记载。
- `Phase 4 Decision`：原始式样未明确，在 Phase 4 沟通中确认并固化的实现级决定。
- `Pending`：尚未正式确定，不得擅自实现。

### 0.3 上位式样 / Source Documents

- `Project3_Development_Spec_v0.1.xlsx`
- `Project3_Basic_Design_v0.1.docx`

---

## 1. 变更历史 / Revision History

以下历史根据 `docs/phase4_progress.md` 和当前会话记录重建（reconstructed from current project records）。

| Version | Date | 变更内容 | 来源/关联 | Status |
|---|---|---|---|---|
| v0.20 | 2026-09-14 | 表格边界与临近说明关联修正 | §6.17 | Draft |
| v0.21 | 2026-09-15 | Vision 接口、Fake、Gemini REST 适配与 ParsedBlock 转换 | OCR/Vision Phase 5 | Draft |
| v0.1 | 2026-08-24 | 创建技术基线、第一条纵向切片、API 契约、调用链和授权边界 | `REQ-F-005`、`REQ-F-016` | Draft |
| v0.2 | 2026-08-24 | 将 `LeaveBalance` 调整为 `balance_id` 主键、`user_id` 外键加 UNIQUE；确定 `unit` 不持久化 | Phase 4 Decision | Draft |
| v0.3 | 2026-08-26 | 合并上位式样来源、文档管理、决定记录、Repository 边界和 Traceability；明确动态状态由进度文档维护 | 文档治理调整 | Draft |
| v0.4 | 2026-08-26 | 确定余额记录不存在的业务异常，以及 API 和未来 Agent Tool 各自负责的传输映射边界 | Phase 4 Decision | Draft |
| v0.5 | 2026-09-01 | 固化 Service、API、Repository 测试矩阵和测试追踪编号 | Phase 4 Verification | Draft |
| v0.6 | 2026-09-01 | 固化 Authorized RAG Read 的检索前权限过滤、有效版本、证据阈值和 metadata citation 契约 | Original Specification + Phase 4 Decision | Draft |
| v0.7 | 2026-09-01 | 接入 `POST /api/chat`、确定性 AgentRouter 与两个只读 Tool，并固化统一响应和测试 | Original Specification + Phase 4 Decision | Draft |
| v0.8 | 2026-09-01 | 固化安全年假申请的 Prepare/Confirm/Revalidate/Transaction/Execute、余额预留和 Idempotency 契约 | Original Specification + Phase 4 Decision | Draft |
| v0.9 | 2026-09-01 | 实现 PDF/Excel 解析、原本存储、跨存储处理状态、本地 Hash Embedding 与持久化 Chroma | Original Specification + Phase 4 Decision | Draft |
| v0.10 | 2026-09-04 | 确定 Level 2 复杂文字文档范围、目标 ParsedBlock metadata、架空 HMI 样本和测试矩阵；OCR/视觉理解留到后续版本 | Phase 4 Decision | Draft |
| v0.11 | 2026-09-04 | 实现 Excel Region Detection、多行表头路径、非破坏式合并单元格视图和 ParsedBlock 新 metadata | Phase 4 Implementation + Verification | Draft |
| v0.12 | 2026-09-05 | 增强文字型 PDF 的重复页眉页脚清理、标题/段落识别与页内 Chunk，并将结构 metadata 贯通到 Chroma 和 Citation | Phase 4 Implementation + Verification | Draft |
| v0.13 | 2026-09-05 | 增加不会扩大权限的 metadata Filtering、可显示 Citation 定位与分数，以及六题小型检索回归评测 | Phase 4 Implementation + Verification | Draft |
| v0.14 | 2026-09-05 | 增加本地工作界面、ADMIN 文档上传/状态 API、上传者读取权限和原始文件名保护 | Phase 4 Implementation + E2E Verification | Draft |
| v0.15 | 2026-09-10 | 在现有 RAG 单一数据链中增加 OCR/Vision/Image Evidence metadata 契约，并保持旧文本 Chunk ID 兼容 | OCR/Vision Phase 1 Decision + Verification | Draft |
| v0.16 | 2026-09-13 | 增加绑定 DocumentVersion 的本地图片资产存储、稳定 image_id、受控读取与路径跳转防护 | OCR/Vision Phase 2 Decision + Verification | Draft |
| v0.17 | 2026-09-13 | 增加 Excel 普通嵌入图片提取、Sheet/锚点定位、MIME 识别及本地资产保存 | OCR/Vision Phase 3 Decision + Verification | Draft |
| v0.18 | 2026-09-13 | 增加 OCR Provider 契约、Fake OCR、PDF 页面渲染和扫描页 OCR fallback | OCR/Vision Phase 4 Decision + Verification | Draft |
| v0.19 | 2026-09-13 | 将 Excel 表格识别收紧为闭合边框矩形，并把临近标题、说明和备注加入表格检索正文 | Phase 4 Decision + Verification | Draft |

变更历史只记录影响接口、数据模型、权限、异常处理或测试预期的重要变化；排版和错别字修正不单独增加版本。

---

## 2. 已确认的技术基线 / Confirmed Technical Baseline

以下为 Phase 4 已确认决定：

- Language：Python 3.12
- Web Framework：FastAPI
- DTO / Validation：Pydantic
- ORM：SQLAlchemy 2.x
- Business Database：SQLite（本地开发）
- Test Framework：pytest
- Authentication v1：Mock Authentication Context
- Authentication Input：`X-User-Id`
- Vector Database：Chroma 1.5.x（本地 `PersistentClient`）
- Embedding v1：本地确定性 Hash Embedding，不下载模型、不调用外部 API

`X-User-Id` 仅用于本地开发阶段模拟身份。Authentication Dependency 必须将认证输入转换为可信的 `current_user`，业务代码不得直接相信客户端提供的任意目标 `user_id`。

---

## 3. 纵向切片 1：查询自己的年假余额

### 3.1 对应上位式样 / Source Specifications

| 类型 | 位置 | 内容 |
|---|---|---|
| Requirement | `REQ-F-005` | 员工可以查询自己的年假余额 |
| Security Requirement | `REQ-F-016` | 员工不能查询其他员工的个人业务数据 |
| Function | `FN-LEAVE-001` | 年假余额查询 |
| API | `API-002` | `GET /api/me/leave-balance`，Self only |
| Permission Matrix | `leave_balance / read` | Employee = self |
| Data | `LeaveBalance` | 保存当前年假余额 |
| Basic Design | §3 | Layer / Class Responsibility Map |
| Request Flow | §4.1 | 有給残日数照会；`LeaveService -> LeaveRepository -> Business DB` |
| Authentication / Authorization | §6 | 数据访问前进行认证与授权 |
| Data Model | §7 | `User : LeaveBalance = 1 : 1` |

### 3.2 API 契约 / API Contract

来源：Original Specification 与 Phase 4 Decision。

```text
Method: GET
Path: /api/me/leave-balance
```

成功响应：

```json
{
  "remaining_days": 8.0,
  "unit": "day"
}
```

规则：

- API 不接受目标 `user_id`。
- 查询对象来自可信的 `current_user`。
- `unit` 固定为 `"day"`。
- `unit` 属于 `LeaveBalanceResponse`，不存入 Business DB。
- 找不到 `LeaveBalance` 记录时，API 最终返回 HTTP 404。
- `remaining_days = 0` 与“记录不存在”是不同状态。

### 3.3 数据模型 / Data Model

关系：

```text
User 1 : 1 LeaveBalance
```

`LeaveBalance` 当前字段：

| 字段 | 约束 | 含义 |
|---|---|---|
| `balance_id` | Primary Key | `LeaveBalance` 实体标识 |
| `user_id` | Foreign Key、UNIQUE、NOT NULL | 对应用户；保证每个用户最多一条当前余额记录 |
| `remaining_days` | NOT NULL | 当前剩余年假天数 |
| `updated_at` | 自动维护策略 Pending | 最后更新时间 |

`unit` 不属于数据库字段，因为 `"day"` 是固定的 API 表示，不是每条余额记录独立变化的业务数据。

### 3.4 调用链 / Call Chain

```text
Authentication Context
-> API / Tool
-> Authorization Boundary
-> LeaveService
-> LeaveRepository
-> SQLAlchemy
-> SQLite
```

职责：

- Authentication：确认当前用户身份，并生成可信的 `current_user`。
- API / Authorization Boundary：限制只能查询当前用户自己的资源。
- LeaveService：执行“查询我的年假余额”业务用例。
- LeaveRepository：负责数据库访问。
- SQLAlchemy：Repository 使用的 ORM 技术。
- SQLite：本地开发阶段的 Business DB。

### 3.5 授权边界 / Authorization Boundary

来源：`REQ-F-005`、`REQ-F-016`、`API-002` 和 Permission Matrix。

- API 表示当前认证用户自己的资源。
- API 不接受客户端指定的目标 `user_id`。
- 查询目标来自可信的 `current_user.user_id`。
- `LeaveService` 不得使用客户端任意传入的目标用户编号。
- 当前 Mock Header 仅用于开发；生产环境认证机制尚未确定。

### 3.6 Repository 边界 / Repository Boundary

来源：Basic Design §3 与 §4.1。

- Service 不直接使用 SQLAlchemy `Session`。
- Service 通过 `LeaveRepository` 查询数据。
- SQLAlchemy 的 `select`、`where` 和 Session 操作属于 Repository。
- Repository 找到记录时返回 `LeaveBalance`。
- Repository 没找到记录时返回 `None`。
- Repository 不决定 HTTP 状态码。

### 3.7 无记录与余额为零 / Missing Record vs Zero Balance

来源：Phase 4 Decision。

```text
记录存在，remaining_days = 0
-> 用户的真实余额为 0

Repository 返回 None
-> LeaveBalance 记录不存在
-> 可能是尚未初始化或数据异常
```

系统不得把 `None` 自动转换成 `remaining_days = 0`，否则会掩盖数据缺失问题。

HTTP 契约已经确定：

```text
No LeaveBalance record
-> HTTP 404
```

业务异常类型和到 HTTP 404 的映射边界已确认，详见下一节。

### 3.8 业务异常与传输映射 / Business Error and Transport Mapping

来源：Phase 4 Decision。

业务异常：

- 名称：`LeaveBalanceNotFoundError`
- 计划位置：`app/services/errors.py`
- 表达的业务事实：当前用户的 `LeaveBalance` 记录不存在。
- 该异常不继承或依赖 FastAPI `HTTPException`。
- 该异常不包含 HTTP 状态码。

API 映射：

- 计划位置：`app/api/error_handlers.py`
- API 层将 `LeaveBalanceNotFoundError` 映射为 HTTP 404。
- 对用户返回安全、简洁的信息，不暴露内部实现或敏感数据。

Agent Tool 映射：

- 未来 Agent Tool 复用相同业务异常。
- Tool 层独立将 `LeaveBalanceNotFoundError` 转换为适合 Tool / Agent 的结果。
- 业务异常不依赖 HTTP 或 Tool 协议，以保持 Service 层与传输方式解耦。

### 3.9 测试矩阵 / Test Matrix

来源：本详细设计中已确认的 API、业务异常、Repository 和授权边界。

| Test Case ID | 测试层级 | 场景 | 预期结果 |
|---|---|---|---|
| `TC-SVC-LEAVE-001` | Service Unit | 当前用户余额为 `8.0` | 返回 `8.0 / day`，Repository 收到当前用户编号 |
| `TC-SVC-LEAVE-002` | Service Unit | 当前用户余额为 `0` | 正常返回 `0 / day`，不得视为数据缺失 |
| `TC-SVC-LEAVE-003` | Service Unit | Repository 返回 `None` | 抛出 `LeaveBalanceNotFoundError` |
| `TC-API-LEAVE-001` | API | 携带 `X-User-Id` 且余额存在 | HTTP 200 与固定 Response Schema |
| `TC-API-LEAVE-002` | API | Service 抛出余额不存在异常 | HTTP 404 与安全错误信息 |
| `TC-API-LEAVE-003` | API | 缺少 `X-User-Id` | 请求验证失败，不进入业务查询 |
| `TC-REP-LEAVE-001` | Repository Integration | SQLite 中存在指定用户余额 | 按 `user_id` 返回匹配记录 |
| `TC-REP-LEAVE-002` | Repository Integration | SQLite 中不存在指定用户余额 | 返回 `None` |

Repository 集成测试使用隔离的内存 SQLite，不读取或修改本地开发数据库 `business.db`。API 测试必须在每个测试结束后清理 FastAPI dependency overrides，防止测试之间相互污染。

---

## 4. 纵向切片 2：Authorized RAG Read 核心链

### 4.1 对应上位式样 / Source Specifications

| 类型 | 位置 | 内容 |
|---|---|---|
| Requirement | `REQ-F-001` | 认证用户可以在权限范围内对社内文档进行自然语言检索和提问 |
| Security / Quality | `REQ-F-002`、`REQ-F-004` | 只检索有权限且有效的文档；证据不足时不推测 |
| Citation | `REQ-F-003` | 回答显示能够定位依据的 Source Citation |
| Security NFR | `NFR-SEC-001` | 权限判定发生在 Retrieval 前，越权数据不得进入 LLM Context |
| Function | `FN-RAG-001` | 权限和有效版本过滤后的 Semantic Retrieval 与 Source 回答 |
| Permission Matrix | `company_document / read` | role、department、explicit permission + active version |
| Basic Design | §4.2、§6、§8、§9 | RAG 调用链、Authorization、三种存储、Document/RAG 设计 |

### 4.2 核心调用链 / Core Call Chain

上位式样的完整目标链：

```text
ChatController
-> AgentRouter
-> SearchDocumentTool
-> AuthorizationService
-> RagService
-> Permission + Version Filter
-> VectorRepository / Vector DB
-> Answer Generator + Source Citation
```

本里程碑先实现并验证中间的安全核心：

```text
CurrentUser + Query
-> AuthorizationService
-> DocumentAccessRepository / Business DB
-> allowed_document_version_ids
-> RagService
-> VectorRepository.search(query, allowed_document_version_ids)
-> evidence threshold
-> AnswerGenerator
-> metadata-based Source Citation
```

`ChatController`、`AgentRouter` 和 `SearchDocumentTool` 在后续 Agent/Tool 里程碑接入，不在本节伪装成已完成。

### 4.3 权限与有效版本过滤 / Permission and Active-Version Filter

- Business DB 保存 Document、DocumentVersion 和文档访问权限等管理状态。
- `AuthorizationService` 通过 `DocumentAccessRepository` 取得当前用户可读且有效的文档版本编号。
- 允许范围可以来自 user explicit、department 或 role；三者均属于确定性程序判断，不由 LLM 决定。
- `VectorRepository.search()` 必须接收 `allowed_document_version_ids`。
- Vector Repository 必须在 Retrieval 查询时过滤；禁止先检索越权 Chunk，再在 Service 或 LLM 前丢弃。
- 允许集合为空时直接返回 No Evidence，不执行不受限的 Vector Search。

### 4.4 Evidence 与 Source Citation

每个检索 Chunk 至少携带：

- `chunk_id`
- `document_id`
- `document_version_id`
- `content`
- `score`
- `source_name`
- 可选定位：`page`、`section`、`sheet`、`rows`

规则：

- citation 只由上述 metadata 组装。
- Answer Generator 只能使用已授权且达到阈值的 Chunk。
- 回答生成器不得自行生成来源名称、页码、Sheet 或行号。
- 相同来源定位可去重，但不得删除定位所需字段。

### 4.5 No Evidence

以下情况返回 No Evidence，而不是 System Error：

- 当前用户没有任何可读且有效的文档版本。
- Vector Repository 没有返回 Chunk。
- 最高相关度低于配置阈值。

No Evidence 时：

- 返回安全、明确的“未找到足够依据”结果。
- 不调用 Answer Generator，防止模型凭常识猜测公司规则。
- citation 为空。

### 4.6 第一版实现边界 / Initial Implementation Boundary

- 定义可替换的 `DocumentAccessRepository`、`VectorRepository` 和 `AnswerGenerator` 接口。
- 使用 SQLAlchemy + SQLite 验证 Business DB 的权限与有效版本查询。
- 使用确定性的本地 Vector Repository/Fake 验证过滤参数和业务流程。
- 本地运行时已接入 Chroma PersistentClient，并使用离线、可复现的 Hash Embedding；不依赖付费 LLM、外部 Embedding API 或云服务。
- 生产环境使用的 Embedding 模型、LLM Provider 与分数阈值校准仍待后续决定。

### 4.7 测试矩阵 / Test Matrix

| Test Case ID | 测试层级 | 场景 | 预期结果 |
|---|---|---|---|
| `TC-SVC-RAG-001` | Service Unit | 有权限且证据充分 | 只用允许版本检索，返回答案和 metadata citation |
| `TC-SVC-RAG-002` | Service Unit | 无任何允许版本 | 不调用 Vector Repository 与 Answer Generator，返回 No Evidence |
| `TC-SVC-RAG-003` | Service Unit | 检索为空 | 不调用 Answer Generator，返回 No Evidence |
| `TC-SVC-RAG-004` | Service Unit | 最高分低于阈值 | 不调用 Answer Generator，返回 No Evidence |
| `TC-REP-AUTH-001` | Repository Integration | user explicit permission + active version | 返回相应版本编号 |
| `TC-REP-AUTH-002` | Repository Integration | department/role permission | 只返回匹配范围的有效版本编号 |
| `TC-REP-AUTH-003` | Repository Integration | 无权限、旧版或 inactive | 不返回这些版本编号 |
| `TC-AGENT-001` | Agent Unit | 余额意图 | 只调用 `GetLeaveBalanceTool` |
| `TC-AGENT-002` | Agent Unit | 公司规则问题 | 只调用 `SearchDocumentTool` |
| `TC-API-CHAT-001` | API | 有认证上下文和有效消息 | 将完整 `CurrentUser` 与消息传给 Agent，返回统一 Schema |
| `TC-API-CHAT-002` | API | 缺少 `X-User-Id` | HTTP 422，不进入 Agent |
| `TC-API-CHAT-003` | API | 空消息 | HTTP 422，不进入 Agent |
| `TC-RAG-FILTER-101` | Service Unit | metadata 过滤后无结果 | 返回 No Evidence，不调用 Answer Generator |
| `TC-RAG-CITE-101` | Service Unit | Excel 同一来源多个 Chunk | Citation 去重并显示 Sheet/Cell Range 与最高分数 |
| `TC-VECTOR-FILTER-101` | Repository Integration | 权限集合 + metadata 条件 | 使用 AND，只返回同时满足两个条件的 Chunk |
| `TC-EVAL-101` | Evaluation | 4 个有答案问题 + 2 个无答案问题 | 分别计算 Retrieval/Source/No Evidence 指标 |

### 4.8 Chat / Agent / Tool 接入

API 契约来自 `API-001`：

```text
POST /api/chat
Authentication: Required
```

请求：

```json
{
  "message": "国内出差住宿费上限是多少？"
}
```

统一响应包含：

- `intent`：当前为 `leave_balance` 或 `knowledge_query`。
- `answer`：对用户显示的安全文本。
- `evidence_found`：知识查询是否有足够证据；余额查询为 `null`。
- `sources`：只由 RAG metadata 产生；余额查询为空。
- `leave_balance`：余额 Tool 的结构化业务结果；知识查询为 `null`。

当前 `AgentRouter` 使用确定性关键词识别余额意图，其余只读问题进入文档检索。该实现用于先验证 Tool 边界和完整调用链，不宣称是 LLM Agent。未来可以替换 Intent Classifier，但以下安全规则不变：

- Agent 只选择 Tool，不直接访问数据库或 Vector DB。
- Tool 只做受控桥接，不承载 Repository 查询或核心业务规则。
- `GetLeaveBalanceTool` 只把 `CurrentUser` 交给 `LeaveService`。
- `SearchDocumentTool` 把 query 和 `CurrentUser` 交给 `RagService`。

### 4.9 Day 4 Metadata Filtering、Citation 与 Evaluation

知识查询可以携带可选条件：

```json
{
  "message": "VehicleSpeed 的期待值是什么？",
  "retrieval_filter": {
    "content_types": ["table"],
    "sheets": ["CAN信号"]
  }
}
```

`RetrievalFilter` 只允许按 `document_ids`、`source_names`、`content_types` 和 `sheets` 缩小候选范围。它不包含 `allowed_document_version_ids`，不能代替认证或授权结果。

Chroma 查询条件：

```text
document_version_id IN authorization result
AND optional document_id
AND optional source_name
AND optional content_type
AND optional sheet
```

强制权限条件始终存在。即使客户端指定了无权访问的文件名或 Sheet，也不会把该版本加入允许集合。InMemory Repository 与 Chroma Repository 使用相同过滤语义。

`SourceCitation` 在结构化 metadata 之外增加：

- `location`：程序生成的界面显示文字，例如 `policy.pdf / Page 2` 或 `spec.xlsx / Sheet CAN信号 / A5:F9`。
- `score`：Repository 返回的相关度分数，范围为 0～1；它不是概率，生产阈值仍需评测校准。

相同文档版本、内容类型和原文定位的多个 Chunk 只保留一个 Citation。检索结果已按分数从高到低排列，因此去重后保留最高分来源。

小型评测固定 6 题：4 题有答案、2 题无答案/安全场景。指标定义为 Retrieval Hit Rate、Source Hit Rate、No Evidence Accuracy 和本机平均检索耗时。详细结果见 `docs/evaluation/day4_retrieval_report.md`。该评测仅用于回归，不代表生产准确率。

---

## 5. 纵向切片 3：安全年假申请 / Safe Leave Request

### 5.1 对应上位式样 / Source Specifications

| 类型 | 位置 | 内容 |
|---|---|---|
| Requirement | `REQ-F-007`～`REQ-F-015` | 本人申请、余额与规则验证、确认信息、明确确认、成功/失败结果 |
| Function | `FN-LEAVE-002` | `Validate -> Confirm -> Revalidate -> Execute` |
| API | `API-004` | `POST /api/me/leave-requests`，Self + Confirm |
| Permission Matrix | `leave_request / create` | Self only + explicit confirmation required |
| Data | `LeaveRequest` | Business DB 中的业务与交易记录；`User 1:N LeaveRequest` |
| Basic Design | §4.3 | `CreateLeaveRequestTool -> validate -> pending_action -> confirm -> revalidate -> create` |
| Basic Design | §5 | `WAITING_CONFIRMATION -> CONFIRMED -> EXECUTING -> SUCCESS/FAILED` |

### 5.2 API 与两阶段契约

Prepare 是 Phase 4 为满足明确确认流程增加的辅助端点：

```text
POST /api/me/leave-requests/prepare
```

请求只接受日期，不接受目标 `user_id` 或客户端计算的申请天数：

```json
{
  "start_date": "2026-09-07",
  "end_date": "2026-09-09"
}
```

响应显示 `REQ-F-011` 要求的确认信息，并返回短期有效的 `confirmation_token`。

最终创建继续使用上位式样 `API-004`：

```text
POST /api/me/leave-requests
Idempotency-Key: caller-generated unique value
```

```json
{
  "confirmation_token": "...",
  "confirmed": true
}
```

- `confirmed` 不为 `true` 时不得创建记录。
- 确认令牌必须属于当前 `CurrentUser`，不得用于其他用户。
- `Idempotency-Key` 在同一用户范围内唯一。
- 同一 key + 同一确认操作重复调用时返回同一个已创建结果，不再次扣减余额。
- 同一 key 对应不同确认操作时返回 Idempotency Conflict。

### 5.3 v1 规则计算

以下是原始式样未锁定、为实现 v1 固化的 Phase 4 Decision：

- 只支持整天申请，半天申请 Pending。
- `start_date` 必须不晚于 `end_date`。
- 申请天数为日期区间内周一至周五的天数；法定节假日表 Pending。
- 申请区间必须至少包含一个工作日。
- 申请天数大于 `3` 时 `approval_required = true`。
- PREPARE 和最终确认时均检查余额是否充足。
- 与现有 `PENDING_APPROVAL` 或 `SUBMITTED` 申请日期重叠时拒绝。
- v1 在创建申请时立即预留（扣减）余额，避免多个未审批申请超额占用。
- 审批、拒绝、取消以及取消后的余额释放不在当前切片范围。

### 5.4 状态与数据模型

`PendingLeaveAction`：

- `confirmation_token`：Primary Key，不可猜测随机值。
- `user_id`、`start_date`、`end_date`、`requested_days`。
- `current_balance`、`remaining_after_request`、`approval_required`：Prepare snapshot。
- `status`：`WAITING_CONFIRMATION` 或 `EXECUTED`。
- `expires_at`、`created_at`、可选 `executed_request_id`。

`LeaveRequest`：

- `request_id`：Primary Key。
- `user_id`：当前认证用户。
- `start_date`、`end_date`、`requested_days`。
- `status`：`PENDING_APPROVAL` 或 `SUBMITTED`。
- `approval_required`。
- `idempotency_key`：与 `user_id` 组成 UNIQUE。
- `confirmation_token`：与准备操作关联。
- `created_at`。

关系：`User 1:N LeaveRequest`。

### 5.5 Final Revalidation 与 Transaction

确认请求进入事务后依次执行：

```text
1. 按 user_id + idempotency_key 查询既有结果
2. 校验 confirmation token、用户、状态和有效期
3. 重新计算工作日天数与审批要求
4. 重新查询当前余额
5. 重新检查日期重叠和余额
6. 使用条件 UPDATE 原子预留余额
7. INSERT LeaveRequest
8. PendingLeaveAction -> EXECUTED
9. COMMIT
```

任何步骤失败都 ROLLBACK，不得出现“余额已扣但申请不存在”或“申请存在但余额未扣”。只有 COMMIT 成功后返回成功。

### 5.6 Idempotency

- 幂等键由调用方生成，通过 `Idempotency-Key` Header 传入。
- Business DB 使用 `UNIQUE(user_id, idempotency_key)` 作为最终防线。
- 重试首先查询已创建记录；匹配同一 `confirmation_token` 时直接返回该记录。
- 已存在 key 但 token 不同视为冲突，不能返回错误操作的结果。
- 幂等命中不再次执行 Final Revalidation、余额预留或 INSERT。

### 5.7 测试矩阵

| Test Case ID | 层级 | 场景 | 预期结果 |
|---|---|---|---|
| `TC-SVC-WRITE-001` | Service Unit | Prepare 有效日期和足够余额 | 返回完整确认信息并持久化 WAITING token |
| `TC-SVC-WRITE-002` | Service Unit | 日期无效、无工作日或余额不足 | 不生成确认操作 |
| `TC-SVC-WRITE-003` | Service Unit | Confirm 后状态已变化 | Final Revalidation 拒绝且无部分写入 |
| `TC-SVC-WRITE-004` | Service Unit | 明确确认且状态仍有效 | 创建申请并预留余额 |
| `TC-SVC-WRITE-005` | Service Unit | 同一 idempotency key 重试 | 返回同一申请，余额只扣一次 |
| `TC-SVC-WRITE-006` | Service Unit | 同一 key 对应不同 token | Idempotency Conflict |
| `TC-SVC-WRITE-007` | Service Unit | 并发请求在 UNIQUE 约束竞争 | 失败事务回滚后重新读取并返回同一结果 |
| `TC-REP-WRITE-001` | Repository Integration | 成功事务 | 余额、申请和 pending 状态同时提交 |
| `TC-REP-WRITE-002` | Repository Integration | 事务中发生异常 | 所有变更回滚 |
| `TC-API-WRITE-001` | API | Prepare | HTTP 200 与确认预览 |
| `TC-API-WRITE-002` | API | Confirm + Idempotency-Key | HTTP 201；重试返回同一结果 |
| `TC-API-WRITE-003` | API | 未明确确认或缺少 Idempotency-Key | 不创建申请 |
| `TC-E2E-WRITE-001` | End-to-End | Prepare 后相同 Confirm 重试两次 | 同一结果、单一申请、余额只预留一次 |
| `TC-TOOL-WRITE-001` | Tool Unit | Agent Tool Prepare/Confirm | 完整转发给同一 Service，不复制业务规则 |

`CreateLeaveRequestTool` 已实现并可由依赖组装入口提供。当前确定性 Chat Router 不从普通自然语言直接触发写操作；在结构化日期、pending state 和明确确认的 Agent 会话状态接入前，保持专用 API 为唯一执行入口，避免误触发。

---

## 6. Document Ingestion 与持久化 Vector DB

### 6.1 对应上位式样

- `REQ-F-019`～`REQ-F-021`：上传、DocumentVersion 与旧版状态管理。
- `FN-DOC-001`：Storage → Parse → Chunking → Embedding → Indexing。
- Basic Design §8：Business DB、Document Storage、Vector DB 的职责分离。
- Basic Design §9：PDF 保留 page，Excel 按 Sheet/Region/Structure/Semantic Record 处理，citation 来自 metadata。

### 6.2 实现链

```text
Local PDF / Excel
-> DocumentVersion = processing (Business DB)
-> Original copy (Document Storage)
-> PDF page/heading/paragraph or Excel sheet/region/structure parser
-> IndexedChunk + stable SHA-256 chunk_id
-> local Hash Embedding
-> Chroma upsert(content + embedding + metadata)
-> DocumentVersion = active
```

发生解析、存储或索引异常时，DocumentVersion 改为 `failed`，不得进入 Authorized Retrieval。原文件使用 `document_storage/{document_id}/{document_version_id}/` 保存，Chroma 使用 `chroma_data/` 本地持久化；两者均不进入 Git。

### 6.3 权限与 Citation 不变量

- Chroma metadata 至少保存 `document_id`、`document_version_id`、`source_name`、`content_type`。
- PDF 额外保存 `page` 和 `section`；Excel 保存 `sheet`、`cell_range` 和兼容字段 `rows`。
- Chroma query 的 `where` 使用 `document_version_id: {$in: allowed_ids}`，在向量查询阶段过滤。
- Business DB 中只有 `active` 且当前用户有 user/department/role read permission 的版本才能进入允许集合。
- Vector DB 不独立决定权限；LLM 不生成 citation 字段。

### 6.4 v1 实现边界

- PDF v1 只处理存在文本层的文件；先检测多页重复的顶部/底部候选行，再按页面、标题和正文生成 Block。OCR 仍为 `OI-001`。
- Excel v1 展开 merged cell，并按 Sheet、Header 和数据行生成语义记录，不使用固定 500 字切割。
- Hash Embedding 用于离线、确定性和可重复测试，不声称达到生产语义模型质量。
- 真实 Embedding 模型和 LLM Provider 仍可通过现有 Protocol 替换。

### 6.5 测试矩阵

| Test Case ID | 层级 | 场景 | 预期结果 |
|---|---|---|---|
| `TC-PARSE-001` | Parser Unit | Excel Header、Row、Merged Cell | 保留 Sheet/Row 并恢复 Header=Value 语义 |
| `TC-PARSE-002` | Parser Unit | PDF 多页自然段 | 保留 page 并按自然段组合 Chunk |
| `TC-PARSE-PDF-101` | Parser Integration | 三页架空日语 PDF | 清除重复页眉页脚，保留正确 page/section |
| `TC-PARSE-PDF-102` | Parser Unit | 单行超过 Chunk 上限 | 在同一页内稳定拆分，不生成跨页 Chunk |
| `TC-VECTOR-001` | Chroma Integration | 越权 Chunk 更相似 | Chroma where 只返回允许版本 |
| `TC-VECTOR-002` | Chroma Integration | 重建 Repository | 从本地持久化目录重新读取索引 |
| `TC-VECTOR-003` | Chroma Integration | 结构化 Excel metadata | `content_type`、Sheet、Cell Range 和 rows 可完整写入并恢复 |
| `TC-DOC-001` | Service Integration | Excel Ingestion 成功 | 原本存在、metadata 完整、版本 active |
| `TC-DOC-002` | Service Integration | Vector Index 故障 | 版本 failed，不标记 active |
| `TC-DOC-003` | Service Integration | API 临时文件 + 原始文件名 | Storage 和 Citation 使用原始文件名，不使用随机临时名 |
| `TC-API-DOC-101` | API | ADMIN 上传 PDF/XLSX | HTTP 201，返回 active 与 Chunk 数，不暴露服务器路径 |
| `TC-API-DOC-102` | API | 非 ADMIN 上传 | HTTP 403，DocumentService 不执行 |
| `TC-API-DOC-103` | API | 不支持类型或空文件 | HTTP 415/422，不进入解析流程 |
| `TC-API-DOC-104` | API | ADMIN 查询版本状态 | 返回 processing/active/failed/inactive 状态结构 |
| `TC-UI-101` | API/UI | GET `/` | 返回本地工作界面与静态资源 |

### 6.6 Level 2 复杂文档增强范围

本轮只增强“存在文本层、结构可由程序规则读取”的企业文档：

- Excel：多 Sheet、同 Sheet 多区域、Key-Value、多行表头、合并单元格、多张表、Note。
- PDF：重复页眉页脚清理、标题与自然段识别、页内 Chunk、页码定位。
- Citation：继续由 Parser 和索引 metadata 产生，不由 LLM 生成。

以下内容明确不进入本轮：OCR、扫描 PDF、图片/图表视觉理解、任意排版自动推断和复杂跨页表格视觉还原。

完整范围与 6 天计划见 `docs/complex_document_upgrade_plan.md`。

### 6.7 ParsedBlock 目标契约

在保持现有调用链的前提下，`ParsedBlock` 已增加：

| 字段 | 含义 |
|---|---|
| `content_type` | `title / key_value / table / note / paragraph` |
| `cell_range` | Excel 原始定位，例如 `A8:H12` |

现有 `content`、`page`、`section`、`sheet` 保留；`rows` 作为旧 Citation 的过渡兼容字段，迁移完成前不直接删除。

### 6.8 Excel 结构规则

- 已按空白行和独立合并标题检测 Region。
- 多行表头按列路径组合，例如 `CAN信号 / 信号名`。
- 数据区域的纵向合并值可继承到所属数据行。
- 标题型横向合并不能复制成多个重复字段。
- 不修改、不 unmerge 原 Workbook；Parser 通过只读逻辑视图取得合并值。
- 同一 Sheet 的多个表按 Section 和区域边界分开，后一个表不得错误复用前一个表头。
- Key-Value、Table、Title、Note 和 Paragraph 生成不同 `content_type`，但最终都转换为统一 `ParsedBlock`。
- 两列两行存在歧义时保守按 Table 处理；两列 Key-Value 至少需要三行，多组 Key-Value 可通过中间空列识别。

### 6.9 Day 1 测试矩阵

测试输入为完全虚构的 `samples/fictional_hmi_test_spec.xlsx`，预期区域清单位于 `tests/fixtures/complex_documents/fictional_hmi_expected_regions.json`。

| Test Case ID | 场景 | 预期结果 |
|---|---|---|
| `TC-PARSE-XLSX-101` | Key-Value 区域 | 生成一个 `key_value` Block 并保留 Sheet/Range |
| `TC-PARSE-XLSX-102` | 两行 Header | 生成父子 Header 路径，不丢失上层语义 |
| `TC-PARSE-XLSX-103` | 数据行纵向合并 | 功能 ID 继承到相关记录，不生成无 ID 的错误记录 |
| `TC-PARSE-XLSX-104` | 同一 Sheet 两张表 | 分成不同 Section/Block，不混用 Header |
| `TC-PARSE-XLSX-105` | 合并的备注区域 | 生成 `note` Block，不复制为多个字段 |
| `TC-PARSE-XLSX-106` | 多 Sheet | 每个 Block 保存正确 Sheet 和 `cell_range` |
| `TC-PARSE-XLSX-107` | Citation | Citation 的 Sheet/Range 与原文位置一致 |
| `TC-PARSE-XLSX-108` | 原有简单 Excel | 现有基础解析能力不回归 |

### 6.10 Day 2 实现结果

调用链：

```text
ExcelDocumentParser.parse
-> _WorksheetLayout（非破坏式 merged-cell view）
-> Sheet row scan
-> standalone title/note 或 contiguous region
-> key_value / table / paragraph conversion
-> ParsedBlock(content_type, sheet, section, cell_range, rows)
```

`cell_range` 表示包含 Header 的完整原始区域，例如 `A8:H12`；兼容字段 `rows` 对 Table 只表示数据行，例如 `10:12`。这一区分保留了旧 Citation 的语义，同时提供新的精确范围。

Day 2 验证结果：复杂 Parser 定向测试 4 项通过；修正两列区域歧义后，全项目 47 项测试通过。现有 PDF Parser、DocumentService、Chroma 和业务链未回归。

### 6.11 Day 3 PDF 与 metadata 实现结果

PDF 调用链：

```text
PdfReader 每页提取文本
-> 保留非空文本行
-> 只统计每页顶部/底部候选行
-> 规范化空白并遮蔽页码数字
-> 在至少 60% 页面重复时认定为页眉/页脚
-> 仅从页边候选区域删除
-> 标题识别和页内段落组合
-> ParsedBlock(content_type, page, section)
```

页眉页脚清理采用保守规则：相同文本必须跨页重复，并且只能从页边候选区域删除。正文中偶然重复的业务句子不会因为内容相同就被全局删除。`Page 1 / 3`、`Page 2 / 3` 等页码先将数字规范化为占位符，因此能够被识别为同一页脚模式。

Chunk 不跨页。即使相邻两页属于同一章节，也分别生成带各自 `page` 的 Block，以保证 Citation 能准确定位。单个超长文本行超过上限时，在当前页内按上限切分。

统一 metadata 流：

```text
ParsedBlock
-> DocumentService._to_indexed_chunk
-> IndexedChunk
-> Chroma metadata
-> Vector Repository search result
-> RagService
-> SourceCitation
```

`content_type` 和 `cell_range` 已沿上述链路完整传递。读取旧 Chroma 数据时，如果没有 `content_type`，使用 `paragraph` 作为兼容默认值；Citation 字段仍由程序根据 metadata 组装，不交给 LLM 生成。

Day 3 使用完全虚构的三页日语 HMI 方针 PDF 做真实文件测试，并对全部页面进行了渲染检查。验证结果：Day 3 相关测试 16 项通过；全项目 50 项测试通过，保留 1 条第三方 Starlette 弃用警告。

### 6.12 Day 5 本地演示界面与上传 API

界面由现有 FastAPI 直接提供原生 HTML/CSS/JavaScript，不新增 Node、React 或前端构建链。根路径 `/` 返回工作界面，`/static` 提供样式和脚本。

首屏包含：

- 开发阶段的 User/Department/Role 身份输入。
- 聊天、示例问题、`content_type` 和 Sheet 筛选。
- PDF/Excel 上传表单。
- 文档版本处理状态。
- `evidence_found`、Citation location 和 score 展示。

上传调用链：

```text
POST /api/admin/documents
-> Mock CurrentUser + ADMIN 检查
-> 扩展名/空文件/10 MB 大小检查
-> 临时传输文件
-> DocumentService
-> DocumentVersion = processing
-> 原本存储 + Parser + Chroma
-> 给上传用户授予 read permission
-> DocumentVersion = active
-> 安全的 DocumentUploadResponse
```

支持 `.pdf` 和 `.xlsx`，最大 10 MB。本轮同步处理，因此上传响应在解析与索引完成后返回；状态 API 仍统一展示 `processing/active/failed/inactive`。生产级后台 Job Queue 不属于 Day 5。

上传接口不返回 `stored_path`。原始浏览器文件名与服务器临时路径分离，Storage 和 Citation 只使用 `Path(original_name).name` 清理后的原始文件名，防止随机临时名或客户端路径进入 metadata。

真实端到端验证使用虚构 `fictional_hmi_policy.pdf`：上传成功并生成 12 个 Chunk；同一用户查询走行中视频规则后，返回 Page 2 的证据与 `fictional_hmi_policy.pdf / Page 2` Citation。修复前曾显示临时文件名，该问题已加入 `TC-DOC-003` 回归测试。

Day 5 自动化验证结果：全项目 65 项测试通过，保留 1 条第三方 Starlette 弃用警告；Python 和 JavaScript 语法检查通过。

### 6.13 OCR / Vision Phase 1：Schema 与 metadata 基础

本阶段只扩展现有数据契约，不提取图片、不调用 OCR/Vision Provider，也不提供图片访问 API。所有信息继续沿用同一条链：

```text
ParsedBlock
-> DocumentService
-> IndexedChunk
-> Chroma metadata
-> RetrievedChunk
-> RagService
-> SourceCitation
```

`content_type` 表示内容的结构角色（标题、表格、备注等），`modality` 表示内容来自文字还是图片，两者不能混为一个字段。新增 metadata 如下：

| 模型 | 新增字段 | 边界 |
|---|---|---|
| `ParsedBlock` | `modality`、`extraction_method`、`image_id`、`image_path`、`image_index`、`mime_type`、`confidence` | `image_path` 只允许在服务器内部解析阶段使用 |
| `IndexedChunk` / `RetrievedChunk` | 除 `image_path` 外的上述证据字段 | 不保存服务器路径 |
| Chroma metadata | `modality` 及非空的提取方法、图片标识、序号、MIME、置信度 | 禁止图片二进制、Base64、绝对路径和访问 URL |
| `SourceCitation` | 图片证据字段及 `image_url` | Phase 1 的 `image_url` 固定为空；后续由有权限检查的 API 生成 |

`extraction_method` 的允许值为 `text_layer / native_excel / ocr / vision`。为了不把现有 Excel 错误标成 `text_layer`，旧 Parser 未显式设置时暂为 `None`，后续 Parser 接入时按真实提取方式赋值。

稳定 ID 规则保持兼容：旧文本 Chunk 继续使用原字段和原顺序计算 SHA-256；只有存在 `image_id` 的图片证据才把 `image_id` 与 `image_index` 追加到身份材料中。

Phase 1 测试：

| Test Case ID | 验证内容 |
|---|---|
| `TC-SCHEMA-IMAGE-001` | 旧文本模型使用兼容默认值；图片模型区分内部路径与对外字段 |
| `TC-DOC-IMAGE-001` | metadata 从 ParsedBlock 进入 IndexedChunk，且不带 `image_path` |
| `TC-DOC-IMAGE-002` | 旧文本 Chunk ID 计算结果不变 |
| `TC-VECTOR-IMAGE-001` | Chroma 往返恢复图片 metadata，且不保存路径或 URL |
| `TC-RAG-IMAGE-001` | Citation 返回安全图片 metadata，Phase 1 不生成 `image_url` |

定向测试 20 项通过；全项目 71 项通过，保留 1 条第三方 Starlette 弃用警告。

### 6.14 OCR / Vision Phase 2：本地图片资产存储

本阶段只提供后续 Parser 可以调用的图片存储组件，不修改 PDF/Excel Parser，也不接入 OCR、Vision、图片 API 或前端。

存储调用链：

```text
图片 bytes + document_id + document_version_id + image_index + mime_type
-> LocalImageAssetStorage.store()
-> SHA-256 稳定 image_id
-> document_storage/{document_id}/{document_version_id}/assets/{image_id}.{suffix}
-> StoredImageAsset
```

`StoredImageAsset` 只用于服务器内部传递 `image_id`、内部 `Path`、图片序号和 MIME 类型，不属于新的 Chunk/Evidence 模型。业务调用方通过 `store/find/read/delete` 操作图片，不自行拼接实际文件路径。

稳定 `image_id` 由以下内容共同计算：

```text
document_id
+ document_version_id
+ image_index
+ mime_type
+ image content SHA-256
```

相同来源、序号、类型和内容会得到相同 ID；同一版本中序号不同的图片会得到不同 ID。第一版本地存储只接受 `image/png`、`image/jpeg`、`image/gif`、`image/bmp`、`image/webp`。

安全边界：

- `find/read/delete` 只接受文档 ID、版本 ID 和系统生成格式的 `image_id`，不接受任意路径。
- 文档标识拒绝 `/`、反斜杠和 `..` 路径跳转形式。
- 图片文件名由系统生成的 ID 与 MIME 白名单扩展名组成。
- 内部 Path 不会在本阶段进入 API、Chroma 或 SourceCitation。

Phase 2 测试：

| Test Case ID | 验证内容 |
|---|---|
| `TC-STORAGE-IMAGE-001` | 图片保存到版本 assets 目录，并可按 ID 查找和读取 |
| `TC-STORAGE-IMAGE-002` | 相同来源与内容生成稳定 image_id；不同序号得到不同 ID |
| `TC-STORAGE-IMAGE-003` | 图片可以删除，删除后读取明确失败 |
| `TC-STORAGE-IMAGE-004` | 拒绝路径跳转、空内容、非法 image_id 和非白名单 MIME |

Phase 2 相关定向测试 12 项通过；全项目 75 项通过，保留 1 条第三方 Starlette 弃用警告。

### 6.15 OCR / Vision Phase 3：Excel 图片提取

本阶段新增 `ExcelImageExtractor`，负责从 openpyxl Workbook 中取得普通嵌入图片，并调用 Phase 2 的 `LocalImageAssetStorage`。现有 `ExcelDocumentParser` 的文字、表格和合并单元格规则保持不变。

调用链：

```text
ExcelImageExtractor.extract(path, document_id, document_version_id)
-> openpyxl load_workbook
-> 按 Workbook 顺序遍历 Worksheet
-> 读取 Worksheet 普通嵌入图片
-> 取得图片 bytes / 实际输出 MIME / 可靠锚点
-> LocalImageAssetStorage.store
-> ExtractedExcelImage（内部提取结果）
```

`ExtractedExcelImage` 只表示尚未经过 OCR/Vision 的内部资产及来源定位，不是新的 Chunk、Evidence 或 Citation 模型。Phase 5/6 才会把图片理解结果转换回统一 `ParsedBlock`。

第一版范围和限制：

- 支持 openpyxl 3.1 能读取的普通嵌入图片。
- openpyxl 没有公开的 Worksheet 图片迭代接口，因此在隔离的 Extractor 内集中使用其 `_images` 集合和图片 `_data()`；版本行为由自动化测试固定。
- Pillow 是 openpyxl 读取图片 bytes 的直接运行依赖，项目声明为 `pillow>=10,<13`。
- 图片序号按 Workbook 与 Sheet 的稳定遍历顺序从 1 开始，不在每个 Sheet 重新计数。
- OneCellAnchor 保存起点单元格；TwoCellAnchor 可保存起止范围；没有可靠单元格锚点时返回 `None`，不得伪造位置。
- JPEG/GIF/PNG 保留对应输出 MIME；openpyxl 对其他可读取格式转换成 PNG 时，保存的 MIME 也记录为 `image/png`。
- SmartArt、Shape、Chart 和 openpyxl 无法读取的特殊 Office 对象仍明确不支持。
- 本阶段不调用 OCR/Vision，不生成描述文字，不接入 DocumentService、Chroma、Citation 或前端。

Phase 3 测试：

| Test Case ID | 验证内容 |
|---|---|
| `TC-XLSX-IMAGE-001` | 两个 Sheet 的普通嵌入图片被提取并保存，保留 Sheet、序号、MIME 和锚点 |
| `TC-XLSX-IMAGE-002` | 重复提取同一 Workbook 时 image_id 与位置稳定 |
| `TC-XLSX-IMAGE-003` | 无图片 Workbook 返回空列表 |
| `TC-XLSX-IMAGE-004` | 带图片 Workbook 的原有文字 ParsedBlock 结果不改变 |

Phase 3 相关定向测试 12 项通过；全项目 79 项通过，保留 1 条第三方 Starlette 弃用警告。

### 6.16 OCR / Vision Phase 4：PDF OCR fallback

本阶段为 `PdfDocumentParser` 增加可选 OCR 能力。Parser 仍优先调用 pypdf 的 `page.extract_text()`；只有配置了 OCR 且页面非空白字符少于默认阈值 20 时，才渲染并 OCR 该页。

调用链：

```text
PdfDocumentParser.parse
-> page.extract_text()
-> 原生文字是否足够？
   -> 是：原有页眉页脚/标题/段落规则，extraction_method=text_layer
   -> 否：PdfPageRenderer
          -> LocalImageAssetStorage
          -> OcrProvider.extract_text(image_path)
          -> OcrResult
          -> ParsedBlock(modality=image, extraction_method=ocr)
```

新增契约：

- `OcrProvider`：Parser 只依赖 `extract_text(image_path)`，不依赖具体云厂商。
- `OcrResult`：包含 `text`、`confidence`、`provider_name`、`success`、`error_message`。
- `FakeOcrProvider`：测试专用，返回固定结果并记录调用路径，不访问网络。
- `PdfPageRenderer`：隔离 PDF 页面渲染接口。
- `PyMuPdfPageRenderer`：本地使用 PyMuPDF 将指定页渲染成 PNG；依赖范围为 `pymupdf>=1.24,<2.0`。

OCR 成功时，渲染页面先由 `LocalImageAssetStorage` 保存。生成的每个 OCR `ParsedBlock` 都保留 page、image_id、内部 image_path、image_index、PNG MIME 和 confidence；进入 IndexedChunk 时内部路径仍会被 Phase 1 边界移除。

失败策略：Provider 返回 `success=False` 或空文字时，该页不生成可搜索 Block，错误只写 warning 日志，不把 `error_message` 写入正文。若整份文档最终没有任何可索引内容，现有 DocumentService 仍会把版本标记为 failed。

当前接入边界：`DocumentParserRegistry` 仍使用未配置 OCR 的默认 `PdfDocumentParser`，所以现有上传 API 行为不变；Phase 6 才正式组装 OCR Provider、Renderer、Image Storage 和文档上下文。真实云 OCR Provider、API Key、超时重试仍待后续决定，缺少 API Key 不影响应用启动。

Phase 4 测试：

| Test Case ID | 验证内容 |
|---|---|
| `TC-OCR-001` | Fake OCR 成功并记录图片路径 |
| `TC-OCR-002` | Fake OCR 返回结构化失败，不访问网络 |
| `TC-OCR-003` | 拒绝超出 0～1 的 confidence |
| `TC-PDF-OCR-001` | 空文字层页面渲染、保存并生成 OCR ParsedBlock |
| `TC-PDF-OCR-002` | 足够的原生文字层不会调用 Renderer 或 OCR |
| `TC-PDF-OCR-003` | OCR 失败只跳过该页，不直接抛出 Parser 异常 |
| `TC-PDF-OCR-004` | PyMuPDF 把真实图片型 PDF 页面渲染为 PNG |
| `TC-PDF-OCR-005` | 真实图片型 PDF 经真实 Renderer 到达 Fake OCR |

Phase 4 相关定向测试 14 项通过；全项目 87 项通过，保留 1 条第三方 Starlette 弃用警告。

### 6.17 Excel 闭合边框表格与临近上下文

本轮修正早期“连续多行且不是键值对就默认作为表格”的宽松规则。键值对仍优先按照其确定性结构识别；其余候选区域只有同时满足以下条件才分类为 `table`：

- 候选矩形包含两个以上单元格。
- 最上方所有单元格具有可见上边框。
- 最下方所有单元格具有可见下边框。
- 最左侧所有单元格具有可见左边框。
- 最右侧所有单元格具有可见右边框。

没有闭合边框的连续多行不得仅根据行数推断为表格，统一保留换行并生成 `paragraph`。本阶段不使用主观评分，也不让 LLM 决定原始文档结构。

表格生成后，Parser 检查同一 Sheet 中相邻的前后 Block。距离最多允许一行空白：

- 前一个 Block 为 `title` 或 `paragraph` 时，作为表格前置说明加入表格的检索正文。
- 后一个 Block 为 `note` 时，作为表格备注加入表格的检索正文。
- 原独立 Block 继续保留，表格的 `cell_range` 仍只指向真实表格矩形，不能把附近文字伪装成表格单元格位置。
- 新章节标题不是后置备注，不会从表格后方向前错误关联。
- 无边框说明与紧随其后的有边框区域没有空行时，Parser 先按边框状态变化拆成两个候选区域，再进行上下文关联。

第一版明确限制：当前规则不负责识别同一行内并排且没有空列分隔的多个表格，也不处理 Shape、SmartArt 或视觉箭头关系。

相关测试：

| Test Case ID | 验证内容 |
|---|---|
| `TC-PARSE-XLSX-109` | 无边框连续多行分类为 paragraph |
| `TC-PARSE-XLSX-110` | 超过两个单元格的闭合边框矩形分类为 table |
| `TC-PARSE-XLSX-111` | 缺少一侧边框的开放区域不能分类为 table |
| `TC-PARSE-XLSX-112` | 临近标题和备注进入表格检索正文，表格 Cell Range 不扩大 |
| `TC-PARSE-XLSX-113` | 无边框说明紧贴有边框表格时仍能拆分并关联 |

本轮 Excel 定向测试 9 项通过；全项目 92 项通过，保留 1 条与本功能无关的第三方 Starlette 弃用警告。

---

## 7. 设计决定记录 / Decision Log

### Phase 5 补充契约（v0.21）

- `VisionContext` 为调用方上下文，包括 source_name、sheet、page、section、nearby_text、cell_range；位置不取自模型输出。
- `VisionDescription` 为校验后的模型内容，包括 summary、image_type、extracted_text、confidence。
- `VisionResult` 包含 success、provider_name、model_name、description、error_message。description 是内部 Provider 输出，不是另一套 Chunk 或 Evidence。
- `VisionProvider.analyze(image_path, context)` 可由 FakeVisionProvider 或 GeminiVisionProvider 实现。
- `VisionBlockService.parse(asset, context)` 把成功结果转成既有 ParsedBlock：table 图片映射 table，其余映射 paragraph；modality=image，extraction_method=vision。失败或空摘要返回 None。
- Gemini 通过 HTTPX 调用官方 generateContent REST 接口，使用 JSON Schema 校验输出；模型名和密钥显式传入，无默认联网和模型选择。
- 缺少配置仍可创建对象，调用返回 vision_not_configured。支持 PNG/JPEG/WebP，单图读取限制10 MiB，默认请求超时30秒，不自动重试。
- 超时、HTTP错误、拦截、截断及非法输出使用安全错误分类，不把服务器响应或密钥放入错误信息。置信度是模型自报值，不是实测准确率。
- 图片定位及内部路径来自 StoredImageAsset 与 VisionContext；沿用既有元数据隔离规则。
- 当前阶段未接入默认上传，不修改 HashEmbedding 或 EvidenceOnlyAnswerGenerator。Provider 意外异常的文档级隔离、统计及策略在 Phase 6 完成。
- 官方接口依据：https://ai.google.dev/api/generate-content

真实验证默认跳过。显式设置 RUN_GEMINI_VISION_LIVE=1、GEMINI_API_KEY 和 GEMINI_VISION_MODEL 后，可运行 tests/integration/test_gemini_vision_live.py；测试仅上传生成的虚构图片，但会调用外部服务并可能计费。当前仅完成模拟HTTP验证，未宣称真实Gemini识别质量已验收。

| Decision ID | 决定 | 来源 | Status |
|---|---|---|---|
| DD-001 | v1 使用 Python 3.12、FastAPI、Pydantic、SQLAlchemy 2.x、SQLite、pytest | Phase 4 Decision | Confirmed |
| DD-002 | v1 使用 `X-User-Id` 模拟 Authentication Context，并转换为可信 `current_user` | Phase 4 Decision | Confirmed |
| DD-003 | API 不接受目标 `user_id`，使用 `current_user.user_id` | Original Specification + Phase 4 Decision | Confirmed |
| DD-004 | `LeaveBalance.balance_id` 为主键，`user_id` 为 FK + UNIQUE | Phase 4 Decision | Confirmed |
| DD-005 | `unit = "day"` 只属于 Response Schema，不存入 DB | Phase 4 Decision | Confirmed |
| DD-006 | 无余额记录与余额为 0 不同；无记录最终映射为 HTTP 404 | Phase 4 Decision | Confirmed |
| DD-007 | Service 通过 Repository 访问数据库，不直接使用 SQLAlchemy Session | Original Specification | Confirmed |
| DD-008 | Chroma 曾作为 RAG 阶段的优先候选；该初期决定已由 DD-024 的本地 Chroma 实装决定取代 | Phase 4 Decision | Superseded |
| DD-009 | Service 使用不依赖 FastAPI、且不包含 HTTP 状态码的 `LeaveBalanceNotFoundError` 表达当前用户余额记录不存在 | Phase 4 Decision | Confirmed |
| DD-010 | API 在 `app/api/error_handlers.py` 将该业务异常映射为 HTTP 404；未来 Agent Tool 进行独立映射 | Phase 4 Decision | Confirmed |
| DD-011 | RAG 先从 Business DB 取得可读且有效的 `document_version_id`，再将允许集合传给 Vector Repository | Original Specification + Phase 4 Decision | Confirmed |
| DD-012 | Vector Repository 必须在检索查询阶段应用允许版本过滤；不得先取回越权 Chunk 再由 Service 丢弃 | Original Specification | Confirmed |
| DD-013 | Source Citation 由检索结果 metadata 组装，不允许回答生成器自行编造 | Original Specification + Phase 4 Decision | Confirmed |
| DD-014 | 无结果或最高相关度低于阈值时返回 No Evidence，不调用回答生成器，并与 System Error 区分 | Original Specification + Phase 4 Decision | Confirmed |
| DD-015 | 第一版先建立可替换的 Vector Repository 与 Answer Generator 接口；Chroma 已接入，生产级 Embedding 与 LLM Provider 仍为 Pending | Phase 4 Decision | Confirmed |
| DD-016 | `POST /api/chat` 返回统一只读 Chat Response；Agent 只选择 Tool，Tool 复用既有 Service | Original Specification + Phase 4 Decision | Confirmed |
| DD-017 | 当前 AgentRouter 使用确定性关键词路由，不冒充 LLM Agent；未来替换分类器时保持 Tool 和安全边界 | Phase 4 Decision | Confirmed |
| DD-018 | Prepare 使用辅助端点生成短期 confirmation token；API-004 只在 `confirmed=true` 后执行写入 | Original Specification + Phase 4 Decision | Confirmed |
| DD-019 | v1 按周一至周五计算整天申请，超过 3 个工作日需要审批，法定节假日和半天仍为 Pending | Phase 4 Decision | Confirmed |
| DD-020 | 确认时在同一事务内 Final Revalidation、条件更新余额、创建申请和消费 token | Original Specification + Phase 4 Decision | Confirmed |
| DD-021 | v1 创建申请时立即预留余额；取消释放流程不在当前切片范围 | Phase 4 Decision | Confirmed |
| DD-022 | Idempotency 使用调用方 Header 与 `UNIQUE(user_id, idempotency_key)`；同 key 同操作返回原结果，不同操作冲突 | Phase 4 Decision | Confirmed |
| DD-023 | `CreateLeaveRequestTool` 复用同一写入 Service；普通 Chat 暂不直接触发写操作，直到结构化会话确认状态接入 | Phase 4 Decision | Confirmed |
| DD-024 | v1 使用 Chroma 1.5.x PersistentClient，本地路径 `chroma_data/`，权限版本集合进入 query where | Phase 4 Decision + Official Chroma API | Confirmed |
| DD-025 | v1 使用确定性 Hash Embedding 保持完全离线；生产 Embedding 通过 Protocol 替换 | Phase 4 Decision | Confirmed |
| DD-026 | 多存储处理以 DocumentVersion `processing -> active/failed` 表达最终状态，不把未完成索引暴露给 Retrieval | Original Specification + Phase 4 Decision | Confirmed |
| DD-027 | 6 天增强范围包含 Level 2 文字型复杂文档解析；OCR、扫描件和视觉理解留到后续版本 | Phase 4 Decision | Confirmed |
| DD-028 | ParsedBlock 增加 `content_type` 与 `cell_range`；定位 metadata 必须来自确定性 Parser | Phase 4 Decision | Confirmed |
| DD-029 | Excel 使用区域分类和多行 Header 路径；不得通过全 Sheet 无条件展开破坏标题与表边界 | Phase 4 Decision | Confirmed |
| DD-030 | 使用完全虚构的日语 HMI Workbook 作为复杂 Parser 的固定回归样本，不使用真实公司资料 | Phase 4 Decision | Confirmed |
| DD-031 | Excel Parser 使用非破坏式 merged-cell view；不通过 unmerge 和全 Sheet 写回破坏原始结构 | Phase 4 Implementation | Confirmed |
| DD-032 | 两列两行的歧义区域默认按 Table；该宽松默认规则已由 DD-061 取代 | Phase 4 Implementation + Test Failure Analysis | Superseded |
| DD-033 | PDF 页眉页脚只在页边候选行中检测；规范化后至少出现在 60% 页面且不少于 2 页才删除 | Phase 4 Implementation | Confirmed |
| DD-034 | PDF Chunk 不跨页；标题写入 `section`，超长文本只在当前页内切分 | Phase 4 Implementation | Confirmed |
| DD-035 | `content_type` 与 `cell_range` 从 ParsedBlock 贯通 IndexedChunk、Chroma 和 SourceCitation；旧索引缺少类型时默认 `paragraph` | Phase 4 Implementation | Confirmed |
| DD-036 | PDF 回归测试使用完全虚构、可公开的日语 HMI 方针文件；本轮不加入 OCR 或视觉理解 | Phase 4 Decision + Verification | Confirmed |
| DD-037 | RetrievalFilter 只能按白名单 metadata 缩小候选范围；权限版本集合仍由 AuthorizationService 决定，并在 Chroma 中使用 AND 合并 | Phase 4 Implementation + Security Verification | Confirmed |
| DD-038 | Citation 的 `location` 与 `score` 由检索 metadata 和结果分数确定性生成；相同原文定位去重并保留最高分结果 | Phase 4 Implementation | Confirmed |
| DD-039 | Day 4 使用 6 题虚构数据建立回归评测，分别报告检索、来源和无答案指标，不把小样本 100% 描述为生产准确率 | Phase 4 Evaluation Decision | Confirmed |
| DD-040 | Day 5 界面由 FastAPI 直接提供原生 HTML/CSS/JavaScript，不增加独立前端构建工具 | Phase 4 Implementation | Confirmed |
| DD-041 | 文档管理 API 要求开发阶段 ADMIN 角色；上传成功时自动给上传用户增加 read permission | Phase 4 Security Decision | Confirmed |
| DD-042 | 上传只允许 PDF/XLSX、非空且不超过 10 MB；响应不暴露服务器 stored_path | Phase 4 Security Decision | Confirmed |
| DD-043 | 原始文件名与临时传输路径分离；Storage 和 Citation 使用清理后的原始文件名 | Phase 4 E2E Failure Analysis | Confirmed |
| DD-044 | Day 5 使用同步 Ingestion；生产级后台任务队列和实时进度留到后续版本 | Phase 4 Scope Decision | Confirmed |
| DD-045 | OCR/Vision 复用现有 ParsedBlock 到 SourceCitation 的单一数据链，不建立平行图片模型或第二套索引流程 | OCR/Vision Phase 1 Decision | Confirmed |
| DD-046 | `content_type` 表示结构角色，`modality` 独立表示 `text/image`；提取方法使用 `text_layer/native_excel/ocr/vision` | OCR/Vision Phase 1 Decision | Confirmed |
| DD-047 | `image_path` 只用于服务器内部，不进入 IndexedChunk、Chroma 或 API；Chroma 也不保存图片二进制、Base64 或 URL | OCR/Vision Phase 1 Security Decision | Confirmed |
| DD-048 | 旧文本 Chunk ID 算法保持不变；图片证据存在 `image_id` 时才追加图片身份信息 | OCR/Vision Phase 1 Compatibility Decision | Confirmed |
| DD-049 | 派生图片与 DocumentVersion 绑定，保存在原文目录下的 `assets` 子目录；不引入 S3 | OCR/Vision Phase 2 Decision | Confirmed |
| DD-050 | image_id 根据文档、版本、图片序号、MIME 和内容哈希稳定生成；图片内容或来源变化时 ID 随之变化 | OCR/Vision Phase 2 Decision | Confirmed |
| DD-051 | 图片存储组件集中负责路径拼接与 `store/find/read/delete`；业务层不接受或拼接任意服务器路径 | OCR/Vision Phase 2 Security Decision | Confirmed |
| DD-052 | 第一版本地图片存储使用 MIME 白名单决定文件扩展名，并拒绝路径跳转标识 | OCR/Vision Phase 2 Security Decision | Confirmed |
| DD-053 | Excel 图片提取使用独立 `ExcelImageExtractor` 调用既有图片存储；Phase 6 前不改变现有文字 Parser 和 DocumentService 调用链 | OCR/Vision Phase 3 Scope Decision | Confirmed |
| DD-054 | 第一版只处理 openpyxl 可读取的普通嵌入图片；SmartArt、Shape、Chart 和特殊 Office 对象不在范围内 | OCR/Vision Phase 3 Scope Decision | Confirmed |
| DD-055 | 图片序号按 Workbook/Sheet 顺序统一递增；只有 openpyxl 提供可靠锚点时才记录单元格定位 | OCR/Vision Phase 3 Location Decision | Confirmed |
| DD-056 | Pillow 作为 openpyxl 图片读取的直接依赖；本阶段不调用 OCR/Vision，也不生成可搜索图片描述 | OCR/Vision Phase 3 Dependency + Scope Decision | Confirmed |
| DD-057 | Parser 只依赖 OcrProvider 契约；测试使用不联网的 FakeOcrProvider，正式云 Provider 后续独立实现 | OCR/Vision Phase 4 Provider Decision | Confirmed |
| DD-058 | PDF 默认以 20 个非空白字符作为原生文字充分性阈值；仅在 OCR 已配置且低于阈值时 fallback | OCR/Vision Phase 4 Fallback Decision | Confirmed |
| DD-059 | PDF 扫描页由 PyMuPDF 本地渲染为 PNG，并先保存为版本图片资产，再交给 OCR Provider | OCR/Vision Phase 4 Rendering Decision | Confirmed |
| DD-060 | OCR 成功结果回到统一 ParsedBlock；结构化失败只记录 warning 且不进入可搜索正文 | OCR/Vision Phase 4 Failure Decision | Confirmed |
| DD-061 | 键值对规则优先；其余 Excel 候选区域只有边框形成闭合矩形且超过两个单元格时才分类为 table，无闭合边框的多行区域分类为 paragraph | Phase 4 Decision | Confirmed |
| DD-062 | 同一 Sheet、最多间隔一行空白的前置 title/paragraph 与后置 note 加入表格检索正文，但保留原独立 Block 和真实表格 Cell Range | Phase 4 Decision | Confirmed |
| DD-063 | Excel 原始结构分类继续使用确定性规则，不使用未经评测的特征评分或 LLM 推断 | Phase 4 Decision | Confirmed |

---

## 8. 待确认事项 / Pending Detailed Design

以下事项尚未正式确定，不得擅自标记为 Confirmed：

- `remaining_days` 是否允许负数。
- `remaining_days` 的精度和半天表示方式。
- `updated_at` 的自动维护策略。
- SQLite 以外环境的数据库配置。
- 正式 Authentication / JWT 方案。
- Embedding 模型与 LLM Provider。
- Semantic Retrieval 的生产阈值与校准数据。
- Document 更新到 Vector Index 的同步方式（`OI-004`）。
- OCR/Vision Provider、超时、重试和置信度阈值；大规模 Excel 阈值（`OI-005`）。
- 半天申请、公司节假日表和跨年度处理。
- 审批、拒绝、取消和余额释放流程。
- confirmation token 的生产环境加密/签名与清理策略。

---

## 9. Traceability / 追踪关系

```text
REQ-F-005 / REQ-F-016
-> Project3_Basic_Design_v0.1.docx (§3, §4.1, §6, §7)
-> FN-LEAVE-001
-> API-002
-> docs/03_detailed_design.md
-> Application Code
-> TC-SVC-LEAVE-001..003
-> TC-API-LEAVE-001..003
-> TC-REP-LEAVE-001..002
```

```text
REQ-F-019..021 / FN-DOC-001
-> Project3_Basic_Design_v0.1.docx (§8, §9)
-> docs/03_detailed_design.md §6
-> DocumentService / PDF-Excel Parser / Document Storage / Chroma
-> TC-PARSE-001..002 / TC-VECTOR-001..002 / TC-DOC-001..002
```

```text
Basic Design §9 + Phase 4 DD-027..030
-> docs/complex_document_upgrade_plan.md
-> samples/fictional_hmi_test_spec.xlsx
-> tests/fixtures/complex_documents/fictional_hmi_expected_regions.json
-> TC-PARSE-XLSX-101..108
```

```text
Basic Design §9 + Phase 4 DD-033..036
-> samples/fictional_hmi_policy.pdf
-> PdfDocumentParser
-> ParsedBlock / IndexedChunk / Chroma / SourceCitation
-> TC-PARSE-PDF-101..102 / TC-VECTOR-003
```

```text
REQ-F-001..004 / NFR-SEC-001 + Phase 4 DD-037..039
-> RetrievalFilter / Chroma AND where
-> RagService No Evidence / structured SourceCitation
-> app/evaluation/sample_suite.py
-> docs/evaluation/day4_retrieval_report.md
-> TC-RAG-FILTER-101 / TC-RAG-CITE-101 / TC-VECTOR-FILTER-101 / TC-EVAL-101
```

```text
REQ-F-019..021 / FN-DOC-001 + Phase 4 DD-040..044
-> GET / + POST/GET /api/admin/documents
-> DocumentService / Storage / Parser / Chroma / Permission
-> app/static/index.html
-> TC-DOC-003 / TC-API-DOC-101..104 / TC-UI-101
```

```text
REQ-F-007..015
-> Project3_Basic_Design_v0.1.docx (§4.3, §5, §7, §12)
-> FN-LEAVE-002 / API-004
-> docs/03_detailed_design.md §5
-> LeaveRequest Application Code
-> TC-SVC-WRITE-001..007 / TC-REP-WRITE-001..002 / TC-API-WRITE-001..003
-> TC-E2E-WRITE-001 / TC-TOOL-WRITE-001
```

```text
REQ-F-001..004 / NFR-SEC-001
-> Project3_Basic_Design_v0.1.docx (§4.2, §6, §8, §9)
-> FN-RAG-001
-> docs/03_detailed_design.md §4
-> Authorized RAG Core / SearchDocumentTool / AgentRouter / API-001
-> TC-SVC-RAG-001..004 / TC-REP-AUTH-001..003
-> TC-AGENT-001..002 / TC-API-CHAT-001..003
```


enterprise-ai-support-agent
│
├─ app                         应用程序代码
│  ├─ api                     HTTP 接口层
│  ├─ auth                    身份认证上下文
│  ├─ db                      数据库结构和连接
│  ├─ repositories            数据访问层
│  ├─ schemas                 输入输出数据格式
│  ├─ services                业务逻辑层
│  ├─ dependencies.py         组装这些对象
│  └─ main.py                 应用启动入口
│
├─ docs                        项目设计和开发记录
├─ .gitignore                  Git 不需要保存哪些文件
└─ pyproject.toml              Python 项目和依赖配置
