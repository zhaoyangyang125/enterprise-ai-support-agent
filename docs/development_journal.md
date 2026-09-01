# Project 3 Development Journal / 开发日志

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
