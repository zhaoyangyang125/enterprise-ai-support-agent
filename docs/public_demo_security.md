# Public Demo 第一段階：ローカルの安全境界

独立入口 `app.public_demo:app` はログイン不要の読み取り専用Demoです。既存の `app.main:app`、私人AWSのaws-v2、業務API、RAGアルゴリズム、開発用DB設定は変更していません。本段階では公開・AWS配置を行いません。

## ローカル起動

プロジェクトのPython 3.12以上の既存venvを使用します。初回に**存在しない新しいディレクトリ**へ虚構データを生成します。既存ディレクトリを指定すると拒否します。この処理は私人DBや索引を読み込まず、固定の架空データのみを生成します。`app.db.seed`は使用しません。

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_public_demo --output public_demo_data
$env:PUBLIC_DEMO_DATA_DIR = Join-Path (Get-Location) 'public_demo_data'
$env:PUBLIC_DEMO_STATE_DIR = Join-Path (Get-Location) 'public_demo_state'
$env:PUBLIC_DEMO_MODEL_MODE = 'offline'
.\.venv\Scripts\python.exe -m uvicorn app.public_demo:app --host 127.0.0.1 --port 8001 --workers 1 --no-proxy-headers
```

再起動時は準備コマンドを繰り返さず、環境変数設定とuvicorn起動だけを実行します。`http://127.0.0.1:8001/` を閲覧します。8000番の私人Demoとは別プロセスです。`public_demo_data/` と `public_demo_state/` はGit対象外です。

## APIと権限

| メソッド | パス | 用途 |
|---|---|---|
| GET | / | 日本語公開ページ |
| GET | /static/styles.css、/static/public.css、/static/public.js | 必要な静的資源のみ |
| POST | /api/chat | 500文字以下の読み取り照会 |
| GET | /api/me/leave-balance | 架空のU001の残日数 |

上記以外は登録せず404。登録済みパスの別メソッドは405です。GET、HEAD、POST、PUT、PATCH、DELETE、OPTIONS、TRACE、CONNECTで検証しています。Swagger、ReDoc、OpenAPI、文書管理、アップロード、画像、休暇申請、Prepareは非公開です。静的ディレクトリ全体はmountせず、私人UIのJavaScriptも配信しません。

固定ユーザーはサーバー側の `U001 / D-SALES / EMPLOYEE`。訪問者の認証Header、Cookie、query parameterは使用せず、チャットJSONの未定義フィールドも拒否します。ADMIN権限はありません。EMPLOYEEに許可されたTRAVEL_POLICY-V1を既存ACL・Evidence Gate・Vector/BM25/RRFで検索します。

## データの隔離と非書き込み

準備スクリプトは架空のU001（8日）と旅行規定の純粋な新規SQLite/Chromaを生成します。実在社員情報、秘密情報、API Keyをコピーしません。生成後のmanifestが全ファイルのSHA-256を記録します。これは変更検出であり、電子署名ではありません。運用者による改ざんや不正なmanifest作成まで防ぐものではありません。

公開データの唯一の文書allowlistは `app/public_demo_fixtures.py` です。開発版の `app.demo_data` とは独立しており、準備コマンドに私人DB・文書・索引の入力/コピーオプションはありません。起動時は全業務tableの行を公開allowlistと比較し、追加文書・変更された残日数・余分なcollection・想定外のファイルも拒否します。申請tableは空である必要があります。Chroma 1.5で新規生成する既知の索引ファイルだけを許可するため、ライブラリ更新時には形式を再検証してください。

起動時は明示的なデータ・quota状態ディレクトリが必須です。私人storageとのパス重複、欠落・不整合、承認済み以外のChunk、U001以外のUser、EMPLOYEEの読み取り権限不足は起動を拒否します。業務DBには `mode=ro&immutable=1` と `PRAGMA query_only=ON` を適用し、SQLAlchemy側でもSELECT以外を拒否します。公開アプリはcreate_allやseedを実行しません。

Chromaは永続クライアント自体が内部ファイルを書き込む場合があるため、**公開用に準備した索引を一時ディレクトリにコピー**して使用します。元の公開bundle・私人索引には接続して書き込みません。一時コピーは終了時に破棄します。第二段階ではbundleをOS/コンテナの読み取り専用volumeに置く必要があります。

quota専用SQLiteとプロセスlockだけは別の状態ディレクトリに書き込みます。これは訪問者の会話・業務データではなく、UTC日付ごとの使用回数です。状態ディレクトリの削除・交換は禁止し、再起動後も保持してください。

## 負荷と使用量の上限

| 設定 | 初期値 | 許可範囲 |
|---|---:|---|
| PUBLIC_DEMO_PER_MINUTE | 20 | 1–60（全体/60秒） |
| PUBLIC_DEMO_DAILY_REQUESTS | 200 | 1–2000（全体/UTC日） |
| PUBLIC_DEMO_CONCURRENCY | 2 | 1–4 |
| PUBLIC_DEMO_TIMEOUT_SECONDS | 10 | 0より大、30以下 |
| PUBLIC_DEMO_MODEL_MODE | offline | offlineのみ |

設定が不正な場合は起動を拒否します。JSON本文は8192 bytes以下、受信は5秒以内。超過は413、受信タイムアウトは408、質問は1–500文字（空白のみも不可）です。

チャットの受理前に全体の頻度・日次quota・実行slotを確認し、超過時は429とRetry-Afterを返します。実行中のタスク数を上限以内に固定し、待機キューを積みません。失敗・タイムアウトした受理済み照会も日次quotaを消費します。HTTP応答は制限時間で504となりますが、実際の処理が終わるまでslotを解放しません。Pythonスレッドの強制停止はできないため、処理が永久に停止した場合は安全側でslotを保持します。

10秒はexecutorへの投入後の `asyncio.wait_for(asyncio.shield(work), timeout)` による応答待機の上限であり、受信・quota処理・応答転送まで含む厳密な総所要時間ではありません。BoundedSemaphoreは完了callbackでのみ解放します。頻度は受理したチャットの直近60秒をdequeで管理し、再起動するとリセットされます。日次quotaは別SQLiteに保存されるため再起動でも継続します。GETページ/残日数、拒否された不正JSONの通信負荷自体はこのチャットquotaの対象外です。Retry-After: 60は再試行の目安で、日次上限到達時に60秒後の成功を保証しません。

X-Forwarded-Forや送信元IPをquotaキーにしません。偽装Headerで制限を回避できず、無制限なIP別状態も保存しません。一方、全体quotaを悪意ある利用者が消費する可用性リスクは残ります。第二段階で信頼するproxy経路の限定、IP別のネットワーク層防護を追加します。

同一stateディレクトリのプロセスlockにより複数workerの起動を拒否します。**1プロセス・1instance限定**です。別stateを持つ複数instanceでは集約quotaが成立しないため、現段階では水平スケール不可です。将来の分散環境では共有された原子的quota・同時実行管理が必要です。

第一段階はHash Embedding + EvidenceOnly回答のみで、外部LLM/Embeddingを呼び出しません。私人用RAG_*設定やAPI Keyを流用せず、課金は発生しません。将来の実モデル接続には、別の公開用秘密情報、HTTP Providerタイムアウト、最大出力token、retry上限、1要求当たりの呼び出し数上限が必要です。日次要求上限×最大呼び出し数×最大token単価で最悪時の費用上限を見積もり、モデルの価格を確認してから有効化してください。環境変数だけで本実装をクラウドモデルへ切り替えることはできません。

## UI・検証・残る課題

UIは既存の配色を使い、「架空データを使用した公開デモです」と表示します。質問例は入力のみで、送信時に問い合わせます。本人の架空残日数とCitationを表示し、身份入力・ADMIN・文書管理・アップロード・申請入口はありません。DOM表示はtextContentを使用し、任意HTMLを解釈しません。CSP、nosniff、no-storeを設定しています。

自動テストは日語回答・PDFページCitation、固定身份、Header偽装、全HTTPメソッド、Docs非公開、本文・質問長、頻度・日次quota、並行・タイムアウト、再起動、只読DB、元bundle非変更、欠落/改ざん/不正設定時の拒否を検証します。私人版の全回帰と既存の前端テストも実行します。

2026-10-13のローカル検証：Python **233 passed / 3 skipped**（うち公開版21テスト）、Node **9 passed**。既存の2件の依存ライブラリ非推奨警告があります。pytestは既存Tempディレクトリの権限問題を避け、独立した `--basetemp` を使用しました。Playwrightで1440pxのデスクトップと390pxのスマートフォンを確認し、宿泊費10,000円・Page 3 Citation・残日数8日を検証しました。公開版のローカル確認サーバーは確認後に停止しました。

提出時は源コード・公開用のPython虚構fixture・テスト・文書だけを明示的にstageします。公開bundle/state、SQLite、Chromaのbinary、.env、秘密鍵は含めません。.gitignoreは通常のgit addへの防御で、git add -fや既存trackedファイルを禁止する仕組みではないため、毎回staged diffを確認してください。配置前には運用者が公開fixtureを承認し、bundleが新規の準備スクリプトだけで作られたことを確認する必要があります。私人索引のコピー・手動でmanifestを再生成したbundleは使用しないでください。SQLite/Chromaに削除済みデータの残存がないことまでmanifestから証明することはできません。

本段階だけでインターネット運用の承認はしません。TLS、AWSネットワーク層防護、監視・予算通知、OS権限、データvolumeのread-only mount、状態volumeの保持と実際のreverse proxy経路の検証は第二段階です。ローカルHTTPのアプリ上限では通信・接続全体のDoSを防げません。現在のRAG文書は旅行規定1Chunkの架空データで、実モデル回答品質の評価は含みません。
