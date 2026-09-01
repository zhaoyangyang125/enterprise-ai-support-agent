# 03 详细设计书 / Detailed Design

本文档记录 Project 3 在 Phase 4 实现过程中确认的详细设计。

本文档基于原始要件定义、基本设计以及开发过程中的确认结果持续更新。它不能覆盖或擅自修改上位式样；发现冲突时，必须回到原始式样重新确认。

---

## 0. 文档管理 / Document Control

| 项目 | 内容 |
|---|---|
| 文档名称 | Project 3 详细设计书 |
| Document Version | v0.7-draft |
| Status | Draft（草稿，尚未正式 Review） |
| Created Date | 2026-08-24 |
| Last Updated | 2026-09-01 |
| Prepared By | 项目负责人；Codex 辅助整理 |
| Reviewed By | Pending（待审阅） |
| Approved By | Pending（待批准） |
| Related Phase | Phase 4 Coding |
| Current Scope | 查询自己的年假余额；Authorized RAG Read；Chat Agent/Tool 接入 |
| Related Requirements | `REQ-F-001`～`REQ-F-004`、`REQ-F-005`、`REQ-F-016`、`NFR-SEC-001` |

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
| v0.1 | 2026-08-24 | 创建技术基线、第一条纵向切片、API 契约、调用链和授权边界 | `REQ-F-005`、`REQ-F-016` | Draft |
| v0.2 | 2026-08-24 | 将 `LeaveBalance` 调整为 `balance_id` 主键、`user_id` 外键加 UNIQUE；确定 `unit` 不持久化 | Phase 4 Decision | Draft |
| v0.3 | 2026-08-26 | 合并上位式样来源、文档管理、决定记录、Repository 边界和 Traceability；明确动态状态由进度文档维护 | 文档治理调整 | Draft |
| v0.4 | 2026-08-26 | 确定余额记录不存在的业务异常，以及 API 和未来 Agent Tool 各自负责的传输映射边界 | Phase 4 Decision | Draft |
| v0.5 | 2026-09-01 | 固化 Service、API、Repository 测试矩阵和测试追踪编号 | Phase 4 Verification | Draft |
| v0.6 | 2026-09-01 | 固化 Authorized RAG Read 的检索前权限过滤、有效版本、证据阈值和 metadata citation 契约 | Original Specification + Phase 4 Decision | Draft |
| v0.7 | 2026-09-01 | 接入 `POST /api/chat`、确定性 AgentRouter 与两个只读 Tool，并固化统一响应和测试 | Original Specification + Phase 4 Decision | Draft |

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
- Vector Database：Chroma 是未来 RAG 阶段的优先考虑方向，尚未锁定为最终选型

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
- 暂不接入付费 LLM、外部 Embedding API 或云服务。
- Chroma 的最终采用、Embedding 模型、LLM Provider、分数阈值校准仍待后续决定。

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

---

## 5. 设计决定记录 / Decision Log

| Decision ID | 决定 | 来源 | Status |
|---|---|---|---|
| DD-001 | v1 使用 Python 3.12、FastAPI、Pydantic、SQLAlchemy 2.x、SQLite、pytest | Phase 4 Decision | Confirmed |
| DD-002 | v1 使用 `X-User-Id` 模拟 Authentication Context，并转换为可信 `current_user` | Phase 4 Decision | Confirmed |
| DD-003 | API 不接受目标 `user_id`，使用 `current_user.user_id` | Original Specification + Phase 4 Decision | Confirmed |
| DD-004 | `LeaveBalance.balance_id` 为主键，`user_id` 为 FK + UNIQUE | Phase 4 Decision | Confirmed |
| DD-005 | `unit = "day"` 只属于 Response Schema，不存入 DB | Phase 4 Decision | Confirmed |
| DD-006 | 无余额记录与余额为 0 不同；无记录最终映射为 HTTP 404 | Phase 4 Decision | Confirmed |
| DD-007 | Service 通过 Repository 访问数据库，不直接使用 SQLAlchemy Session | Original Specification | Confirmed |
| DD-008 | Chroma 是未来 RAG 阶段的优先方向，但最终 Vector DB 尚未锁定 | Phase 4 Decision | Confirmed |
| DD-009 | Service 使用不依赖 FastAPI、且不包含 HTTP 状态码的 `LeaveBalanceNotFoundError` 表达当前用户余额记录不存在 | Phase 4 Decision | Confirmed |
| DD-010 | API 在 `app/api/error_handlers.py` 将该业务异常映射为 HTTP 404；未来 Agent Tool 进行独立映射 | Phase 4 Decision | Confirmed |
| DD-011 | RAG 先从 Business DB 取得可读且有效的 `document_version_id`，再将允许集合传给 Vector Repository | Original Specification + Phase 4 Decision | Confirmed |
| DD-012 | Vector Repository 必须在检索查询阶段应用允许版本过滤；不得先取回越权 Chunk 再由 Service 丢弃 | Original Specification | Confirmed |
| DD-013 | Source Citation 由检索结果 metadata 组装，不允许回答生成器自行编造 | Original Specification + Phase 4 Decision | Confirmed |
| DD-014 | 无结果或最高相关度低于阈值时返回 No Evidence，不调用回答生成器，并与 System Error 区分 | Original Specification + Phase 4 Decision | Confirmed |
| DD-015 | 第一版先使用可替换的 Vector Repository 与 Answer Generator 接口；真实 Chroma、Embedding 和 LLM Provider 仍为 Pending | Phase 4 Decision | Confirmed |
| DD-016 | `POST /api/chat` 返回统一只读 Chat Response；Agent 只选择 Tool，Tool 复用既有 Service | Original Specification + Phase 4 Decision | Confirmed |
| DD-017 | 当前 AgentRouter 使用确定性关键词路由，不冒充 LLM Agent；未来替换分类器时保持 Tool 和安全边界 | Phase 4 Decision | Confirmed |

---

## 6. 待确认事项 / Pending Detailed Design

以下事项尚未正式确定，不得擅自标记为 Confirmed：

- `remaining_days` 是否允许负数。
- `remaining_days` 的精度和半天表示方式。
- `updated_at` 的自动维护策略。
- SQLite 以外环境的数据库配置。
- 正式 Authentication / JWT 方案。
- RAG 阶段的 Vector DB 最终选择。
- Embedding 模型与 LLM Provider。
- Semantic Retrieval 的生产阈值与校准数据。
- Document 更新到 Vector Index 的同步方式（`OI-004`）。
- OCR 范围（`OI-001`）和大规模 Excel 阈值（`OI-005`）。

---

## 7. Traceability / 追踪关系

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
