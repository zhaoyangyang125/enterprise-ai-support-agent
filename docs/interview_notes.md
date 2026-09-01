# Project 3 面试说明 / Interview Notes

| 项目 | 内容 |
|---|---|
| 用途 | Project 3 中日双语面试说明与背诵稿 |
| Last Updated | 2026-09-01 |
| Status | Living Document（随开发持续更新） |
| 使用方法 | 先掌握短版；面试官追问后，再使用对应的展开回答 |

本文档只记录已经实现或已经明确标注为 Roadmap 的内容。未完成的功能不得在面试中描述为已经完成。

## 1. 一分钟项目介绍

这是一个面向企业内部员工的生成式 AI 支持系统。后端使用 Python、FastAPI、Pydantic、SQLAlchemy 和 SQLite。项目目标不是只做聊天，而是让 Agent 通过受控 Tool 安全访问业务数据和公司文档，并在写操作中加入确认、最终校验、事务和幂等保护。

目前完成的第一条纵向切片是“员工查询自己的年假余额”。接口不接受目标用户编号，而是从认证上下文取得当前用户，经过 Service 和 Repository 查询 Business DB。数据不存在时 Service 抛出与 HTTP 解耦的业务异常，再由 API 层映射为 404。

## 2. 当前调用链

```text
X-User-Id（开发阶段模拟认证）
-> get_current_user
-> CurrentUser
-> GET /api/me/leave-balance
-> LeaveService.get_my_leave_balance
-> LeaveRepository.find_by_user_id
-> SQLAlchemy
-> SQLite
-> LeaveBalanceResponse
```

## 3. 关键设计决定

### 为什么 API 不接受 user_id？

因为该接口表达“我的年假余额”。如果客户端能指定目标用户编号，就可能尝试查询其他员工的数据。业务查询只使用认证后生成的 `current_user.user_id`。

### 为什么 Service 不直接使用 Session？

Service 负责业务流程，Repository 负责 SQLAlchemy 和数据库查询。分离后可以独立测试业务规则，也可以在以后替换数据库实现。

### 为什么余额为 0 和记录不存在不同？

余额为 0 是有效业务数据；Repository 返回 `None` 表示数据尚未初始化或存在异常。把两者合并会掩盖数据问题。

### 为什么业务异常不使用 HTTPException？

同一个 Service 以后还会被 Agent Tool 调用。Service 只表达业务事实，API 将它映射为 HTTP 404，Tool 则可以映射为自己的结构化结果。

### 为什么 unit 不存数据库？

`day` 是固定的响应说明，不是每条余额记录独立变化的业务数据。放入每条记录会重复，并产生 `day/days` 不一致风险。

## 4. 测试策略

```text
Service Unit Test
-> 使用 Fake Repository，只验证业务规则

API Test
-> 替换 Service dependency，只验证 HTTP 边界、认证上下文和错误映射

Repository Integration Test
-> 使用隔离的内存 SQLite，验证真实 SQLAlchemy 查询
```

这种分层测试可以更快定位错误：业务判断错误看 Service 测试，HTTP 契约错误看 API 测试，SQL 查询错误看 Repository 测试。

## 5. 常见追问

1. 生产环境为什么不能继续信任 `X-User-Id`？
   - 它只是本地 Mock Authentication。生产环境需要由 JWT、Session 或企业 Identity Provider 验证身份后生成 `CurrentUser`。
2. `User : LeaveBalance` 为什么是 1:1？
   - v1 只保存当前余额，`leave_balances.user_id` 使用 UNIQUE 保证每个用户最多一条记录；年度历史版本可以扩展为 1:N。
3. `balance_id` 和 `user_id` 有什么区别？
   - `balance_id` 标识余额实体，`user_id` 表示余额属于哪个用户，并承担关联与唯一约束。
4. 为什么使用依赖注入？
   - 统一组装 Session、Repository 和 Service，并允许测试时替换依赖。
5. Repository 返回什么？
   - 找到时返回 `LeaveBalance` 模型对象，找不到时返回 `None`，不决定 HTTP 状态码。
6. RAG 的安全核心是什么？
   - RAG 权限过滤必须在 Retrieval 前执行；引用必须来自 metadata；证据不足时不能让 LLM 猜测公司规则。该核心链已实现并通过测试，Chat/Agent/Tool 接入仍是下一阶段。

## 6. 当前诚实边界

- 第一条 Authorized DB Read 已完成并通过测试。
- Authorized RAG Core 与本地 Chat/Agent/Tool 调用链已完成；真实文档 ingestion、真实 Vector DB/LLM 仍在 Roadmap 中。
- `X-User-Id` 是开发阶段模拟认证，不是生产认证方案。
- SQLite 是本地开发数据库，未来部署环境可以通过 Repository/ORM 边界迁移到 PostgreSQL。

## 7. 日语面试回答 / Japanese Interview Answers

### 7.1 项目整体介绍（约 60～90 秒）

このプロジェクトは、社内の従業員向けに開発している生成 AI サポートシステムです。

バックエンドには Python、FastAPI、Pydantic、SQLAlchemy を使用し、ローカル開発環境の Business Database には SQLite を使用しています。

単純なチャットシステムではなく、Agent が管理された Tool を通じて、業務データや社内文書へ安全にアクセスできる構成を目指しています。また、書き込み処理については、ユーザー確認、最終チェック、トランザクション、冪等性を考慮する予定です。

現在は、最初の縦方向スライスとして「従業員が自分自身の有給休暇残日数を照会する機能」を実装し、Service、API、Repository の各レベルでテストしています。

### 7.2 最初に答える短いバージョン

`X-User-Id: U001` を含むリクエストを受け取ると、まず `get_current_user` がヘッダーの値を `CurrentUser` に変換します。

次に、FastAPI の依存性注入によって `LeaveService` を準備し、API が `get_my_leave_balance()` を呼び出します。

Service は `current_user.user_id` を Repository に渡し、Repository が SQLAlchemy を使って SQLite を検索します。

残日数が `8.0` の場合、`LeaveBalanceResponse` に変換し、API は HTTP 200 で `remaining_days: 8.0` と `unit: day` を返します。

### 7.3 「なぜ user_id を受け取らないのですか」

この API は「自分自身の有給休暇残日数」を取得するための API です。

クライアントから照会対象の `user_id` を自由に受け取ると、ほかの従業員のデータを参照しようとする可能性があります。そのため、照会対象は API パラメータではなく、認証後に作成された `CurrentUser` の `user_id` から取得します。

現在の `X-User-Id` は開発用のモック認証です。本番環境では JWT や企業の Identity Provider に置き換える必要がありますが、Service は引き続き同じ `CurrentUser` を利用できます。

### 7.4 「残日数ゼロとレコードなしの違いは何ですか」

残日数がゼロの場合は、レコードが存在しており、実際に利用可能な有給休暇がゼロであることを表します。そのため、正常な業務データとして HTTP 200 でゼロを返します。

一方、Repository が `None` を返す場合は、残日数がゼロなのではなく、対象ユーザーの残日数レコード自体が存在しない状態です。データ未初期化やデータ不整合の可能性があるため、同じ状態として扱わず、業務例外を発生させています。

### 7.5 「なぜ Service で HTTPException を使用しないのですか」

Service は HTTP 専用ではなく、将来は Agent Tool からも再利用する予定です。

そのため、Service では HTTP ステータスコードを持たない `LeaveBalanceNotFoundError` という業務例外を発生させます。

API 層ではこの例外を HTTP 404 に変換し、将来の Agent Tool では Tool 用の構造化された結果に変換します。これにより、業務ロジックと通信方式を分離できます。

### 7.6 「どのようにテストしましたか」

テストは三つのレベルに分けました。

Service の単体テストでは Fake Repository を使用し、通常の残日数、残日数ゼロ、レコードなしという三つの業務パターンを確認しています。

API テストでは FastAPI の dependency override を使用し、HTTP 200、業務例外から HTTP 404 への変換、認証ヘッダーがない場合のエラーを確認しています。

Repository の結合テストでは、インメモリの SQLite を使用して、実際の SQLAlchemy クエリで対象データを取得できることと、データがない場合に `None` が返ることを確認しています。

### 7.7 「RAGで権限チェックを検索前に行う理由は何ですか」

検索してから結果を除外する方法では遅すぎます。権限のない文書の Chunk が、すでにアプリケーションのメモリや LLM の Context に入る可能性があるためです。

このプロジェクトでは、まず Business Database から、現在のユーザーが読み取り可能で、かつ有効な `document_version_id` の集合を取得します。その集合を Vector Repository に渡し、Repository が検索クエリの段階でフィルタします。LLM は権限の ALLOW/DENY を判断しません。

### 7.8 「Source Citationはどのように作成しますか」

Source Citation は LLM に自由生成させません。検索された Chunk の metadata に保存されている `document_id`、`document_version_id`、ファイル名、ページ、Section、Sheet、行番号などからプログラムで作成します。

これにより、回答の根拠を追跡でき、存在しない出典をモデルが作るリスクを減らします。

### 7.9 「十分な根拠がない場合はどうしますか」

読み取り可能な文書Versionがない場合、検索結果がない場合、または関連度が閾値より低い場合は、No Evidence として扱います。

この場合、Answer Generator を呼び出さず、「十分な資料を確認できない」と返します。これは System Error とは別の正常な業務・品質結果です。

### 7.10 面试中的使用顺序

```text
第一步：先说 7.2 短版
第二步：等待面试官追问
第三步：根据问题选择 7.3～7.9
第四步：不知道或尚未完成的内容，如实说明 Roadmap
```

不要一开始把所有设计细节全部说完。短版用于证明你能清楚说明调用链；展开回答用于证明你理解安全、异常边界和测试策略。

### 7.11 「現在のAgentはLLM Agentですか」

現在の `AgentRouter` は、まず全体のTool Calling構造と安全境界を検証するための、決定的なキーワードルーターです。LLM Agentとして完成したとは説明しません。

ただし、AgentはIntentを分類してToolを選択し、Toolは既存のServiceを再利用する、という責務分担は実装済みです。今後Intent ClassifierをLLMベースに変更しても、Authorization、Service、Repositoryの境界は変更しない設計です。

### 7.12 「安全な休暇申請をどのように実装しましたか」

休暇申請は、PrepareとConfirmの二段階に分けました。

Prepareでは、対象日から営業日数を計算し、現在の残日数、申請後の残日数、上長承認の要否を表示して、短時間だけ有効な確認Tokenを発行します。この時点ではまだ申請を作成しません。

ユーザーが明示的に確認した後、Confirm処理では、残日数、日付の重複、会社ルール、Tokenの所有者と有効期限を再検証します。その後、残日数の予約、LeaveRequestの作成、Tokenの消費を一つのTransactionで実行します。

### 7.13 「ConfirmationとFinal Revalidationの違いは何ですか」

Confirmationは「ユーザーがこの内容で実行したい」という意思を確認するものです。一方、Final Revalidationは「現在のシステム状態でも実行可能か」を確認するものです。

確認画面を表示した後に、別の申請によって残日数が変わる可能性があります。そのため、ユーザーが確認済みでも、書き込み直前に残日数や重複をもう一度確認する必要があります。

### 7.14 「TransactionとIdempotencyの違いは何ですか」

Transactionは、残日数だけ減って申請が作成されない、という部分成功を防ぎます。

Idempotencyは、通信Retryや二重クリックによって、同じ申請が二回成功することを防ぎます。同じユーザーとIdempotency-Keyの結果を保存し、同じ操作の再実行では既存結果を返すため、残日数も二回減りません。

## 8. 日语关键词与读法

| 日语 | 读法 | 中文 |
|---|---|---|
| 認証済み | にんしょうずみ | 已认证 |
| 従業員 | じゅうぎょういん | 员工 |
| 有給休暇 | ゆうきゅうきゅうか | 带薪休假 |
| 残日数 | ざんにっすう | 剩余天数 |
| 照会 | しょうかい | 查询 |
| 依存性注入 | いぞんせいちゅうにゅう | 依赖注入 |
| 業務例外 | ぎょうむれいがい | 业务异常 |
| 単体テスト | たんたいテスト | 单元测试 |
| 結合テスト | けつごうテスト | 集成测试 |
| 取得する | しゅとくする | 获取 |
| 変換する | へんかんする | 转换 |
| 呼び出す | よびだす | 调用 |
| 差し替える | さしかえる | 替换 |
| 冪等性 | べきとうせい | 幂等性 |
| 検索前 | けんさくまえ | 检索前 |
| 根拠 | こんきょ | 依据、证据 |
| 引用元 | いんようもと | 引用来源 |
| 有効版 | ゆうこうばん | 有效版本 |
| 権限範囲 | けんげんはんい | 权限范围 |

## 9. 背诵原则

1. 不逐字死记，先记住调用顺序和关键词。
2. 第一阶段能够不看稿说出 7.2 短版。
3. 第二阶段分别练习权限、异常、测试三个追问。
4. 每次新增正式功能后，追加一段短版和对应追问。
5. 面试中只把已实现的功能说成完成；Roadmap 必须使用“计划”“下一阶段”等表达。
