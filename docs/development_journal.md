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
- Planned commit：`feat: implement authenticated leave balance vertical slice`

---

## Next Milestone

Authorized RAG Read：权限过滤发生在 Retrieval 前，来源引用来自 metadata，无足够证据时拒绝猜测公司规则。
