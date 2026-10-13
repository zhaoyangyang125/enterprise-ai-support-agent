# Public Demo 第二階段 A：独立コンテナの準備

**現在のComposeは隔離したローカル/内部受け入れ専用であり、最終的なインターネット公開用の配置設定として直接使用できません。** network noneと未publishのportを保持し、公開経路は別段階で設計・審査します。

本段階はローカルのLinuxコンテナ検証までです。AWSへ接続・配置せず、私人版aws-v2の再構築/停止、EC2・security group・DNSの変更を行いません。以下のAWS手順は、利用者が内容と資源評価を確認した後に実施するための準備です。

## 分離する対象

| 対象 | Public Demo専用 |
|---|---|
| Dockerfile | `Dockerfile.public`（既存Dockerfileは変更しない） |
| イメージ | `enterprise-ai-support-agent-public:phase2a` |
| コンテナ | `enterprise-ai-support-agent-public-demo` |
| Compose project | `enterprise-public-demo-prep` |
| ユーザー | UID/GID `10001:10001`、publicdemo、非root |
| アプリ | 固定ENTRYPOINTから `app.public_demo:app`、1 process / 1 worker |
| 内部HTTP | コンテナの `127.0.0.1:8001`（ホストへpublishしない） |
| データvolume | `enterprise-public-demo-fictional-data` → `/public-data:ro`、bundle以下 |
| quota volume | `enterprise-public-demo-quota-state` → `/public-state:rw`、別volumeで永続化 |

`app.main`、私人API、私人DB設定、seed入口はイメージへ含めません。固定ENTRYPOINTは別アプリの引数、root実行、private provider/AWS環境変数を拒否します。Docker管理権限を持つ運用者はENTRYPOINT・mount等を上書きできるため、Docker daemonそのものは信頼境界の外です。

原則denyの公開ソースmanifest `deploy/public-demo/source-files.txt` を使い、専用ビルドスクリプトが一時contextへ許可ファイルだけをコピーします。Dockerfileも個別COPYを使います。ローカルの最初のビルドではDockerfile固有ignoreだけに依存すると私人moduleが残ることを検出したため、この二重制限を採用しました。既存の `.dockerignore` は変更しません。

基盤はPython 3.12の検証済みdigest、direct/transitive dependencyは検証したversionで固定しています。lockはパッケージの暗号学的hashやCVE審査ではありません。更新時には再build・回帰・脆弱性確認が必要です。Linux/amd64（t3.smallのarchitecture）で検証しています。

## ローカルのビルドと自動受け入れ

既存Python 3.12以上のvenvを使用します。Docker DesktopはLinux engineを起動してください。スクリプトはUnix socketまたはDocker Desktopのlocal named pipeのみを許可し、remote TCP/SSH Docker contextを拒否します。private Docker authを読まず、一時的な空のclient configを使います。Docker Hubへの匿名pullが制限された場合は停止し、private authを自動でコピーしません。

```powershell
.\.venv\Scripts\python.exe -m scripts.build_public_demo_image
.\.venv\Scripts\python.exe -m scripts.verify_public_demo_docker
# イメージも同時に再buildする場合:
.\.venv\Scripts\python.exe -m scripts.verify_public_demo_docker --build
```

自動受け入れは毎回固有名のテストcontainer/volumeを作成します。純粋な虚構データの新規準備、健康状態、Linux上の非root/readonly mount/capabilities、全HTTP method、偽装ADMIN/U999、日語RAG/Citation、8日の残日数、429、データhash不変、restartとcontainer交換の両方で日次quota保持を確認します。終了時は**自分が作成した一時test objectだけ**を削除し、既存volume・container・imageをpruneしません。受け入れのquotaは2回に設定し、通常Composeの200回とは分離します。

## ローカルで常設確認用containerを起動する場合

下記はまだ実行していない運用向けコマンドです。最初にDocker接続先が本機であることを確認してください。このComposeはbuildを自動実行せず、上で作成した専用imageを使います。

```powershell
docker context show
docker compose -f compose.public-demo.yaml --profile prepare run --rm prepare-data
docker compose -f compose.public-demo.yaml up -d --no-build --wait public-demo
docker exec enterprise-ai-support-agent-public-demo python -m app.public_demo_health
docker compose -f compose.public-demo.yaml ps
```

prepareは空の専用volumeに**新規**bundleだけを生成し、private DB/索引のcopy・seedは行いません。bundleが存在する場合は上書きせず拒否します。通常の `up` はprepare profileを実行しません。既存bundleを消して再生成する運用にはせず、変更が必要なら別の公開用versioned volumeを準備・審査してください。

ホストの8000/8001をpublishしません。`network_mode: none`によりcontainerにはloopbackだけがあり、EC2 IMDSやインターネットへ到達できません。[Dockerのnone network仕様](https://docs.docker.com/engine/network/drivers/none/)。この状態ではブラウザ・SSH転送・reverse proxyからも閲覧できず、Docker exec経由の内部検証だけを行います。実際の公開に必要なネットワーク変更は別の段階で承認・設計します。

## 制限と健康検査

| 項目 | 設定 |
|---|---|
| CPU | 最大0.5 vCPU、予約ではなく上限 |
| メモリ | 最大768 MiB、memory-swapも768 MiB（追加swapなし） |
| process/thread | 最大128、native libraryのthreadも抑制 |
| root filesystem | read-only |
| 一時領域 | `/tmp`の256 MiB tmpfs、noexec/nosuid/nodev |
| capabilities | ALLをdrop、no-new-privileges、init有効 |
| application | worker 1、proxy_headers=false、keepalive 5秒、接続処理上限32 |
| log | json-file、最大5 MiB×2、access logなし |
| restart | この準備段階は自動restartなし |
| health | 30秒毎、timeout 10秒、startup猶予120秒、3回失敗でunhealthy |

tmpfsの使用量はメモリ上限内に含まれます。768+256 MiBの予算ではありません。[Dockerのtmpfs説明](https://docs.docker.com/engine/storage/tmpfs/)。quota SQLiteだけは永続volumeへ書き込みます。Chromaは公開bundleからtmpfsへ複製し、元bundleはroで保持します。

healthは公開ホームの文言、架空残日数8日、Docs/OpenAPI/管理/申請が404であることを確認します。チャットを送らずquotaを消費しません。Dockerのunhealthy表示だけでは自動停止/復旧せず、運用監視が別途必要です。healthは公開APIの必要な境界確認で、認証・全APIの網羅検証は自動受け入れが行います。

private `DASHSCOPE_API_KEY`、AWS credentials、`RAG_*`、SSM値、`.env`、private database/Chroma/document_storage、Docker socketはmount/envへ渡しません。公開版はofflineのみです。既存のprivate起動スクリプトを流用しません。起動後の管理者による `docker exec -e` 等の意図的な注入までアプリは防げないため、Docker管理権限と運用手順を制限してください。

## t3.smallでの併用判定

t3.smallは2 vCPU / 2 GiB、baselineはvCPUあたり20%のburstable instanceです。[AWS T3仕様](https://aws.amazon.com/ec2/instance-types/t3/)。本輪はEC2へ接続していないため、aws-v2の実際のRSS/peak、MemAvailable、swap、OOM履歴、SSM/CloudWatch使用量は未計測です。安全な同時稼働を確認したとは扱いません。

保守的な仮予算（実測の代わりではありません）：

| 用途 | MiB |
|---|---:|
| OS / Docker / SSM / CloudWatch等 | 640 |
| Public Demoの設定上限 | 768 |
| 残しておく安全余裕 | 256 |
| 私人aws-v2に残る予算 | 384 |
| 合計 | 2048 |

公開版の小型fixtureに対するローカル検証のmemory.peakとDocker statsは本ページ末尾に記録します。private OCR/upload/索引の負荷、長時間の連続処理、EC2固有のメモリ挙動まで表す数値ではありません。

aws-v2の実測peakが384 MiBを超える、または公開起動前のMemAvailableが1024 MiB未満の場合は、この予算での共存を進めません。privateの通常・最大負荷を観測し、OS予算が妥当か再確認してください。判断できない場合も開始せず、別instanceかRAM増量を選択します。0.5 vCPUを持続使用するとprivate負荷と合わせてT3 CPU creditを消費する可能性があり、CPU上限だけでは費用上限を保証しません。

EC2でのimage buildはこのruntimeメモリ上限外であり、pip/BuildKitが私人版を圧迫する恐れがあります。t3.small上でaws-v2を動かしたままbuildしません。承認後の配置では、本機で検証済みの公開imageを保存・移送して使う方針です。

## 承認後のAWS配置手順（本輪では未実施）

1. reviewerが公開fixture、source manifest、Compose、依存lockとimage IDを確認。公開image/rollback用の旧公開imageをversioned tagで保持し、private aws-v2のtagを上書きしない。
2. 利用者の承認後にのみEC2で `free -m`、private対象を限定した `docker stats`、OOM/credit/ディスク余裕を確認。環境変数を含むfull Docker inspectを共有しない。上記予算を満たさない場合は停止。
3. 本機で専用imageをexportし、SHA-256を確認して承認済み手段でEC2へ移送。EC2では同じhashを確認して `docker load`。private imageのbuild/停止/削除は行わない。
4. 公開専用Composeだけを専用ディレクトリで使い、`prepare-data`で新しい公開volumeを作成。private DB/索引/SSM/DashScopeの設定は取り込まない。
5. 公開serviceだけを `up --no-build --wait public-demo`。no ports、network none、non-root、ro data/rootfs、永続quotaをinspectの必要な項目だけで確認。
6. `docker exec ... python -m app.public_demo_health`で内部検査し、公開containerのstats/OOMKilled/PIDsとprivate側の影響を観測。悪化したら公開containerだけを停止。security group、DNS、8000/8001、reverse proxyは変更しない。

本機でimageを保存する例（アーカイブをGitへ追加しない）：

```powershell
New-Item -ItemType Directory -Force public_demo_artifacts
docker image inspect --format '{{.Id}}' enterprise-ai-support-agent-public:phase2a
docker save -o public_demo_artifacts/public-demo-phase2a.tar enterprise-ai-support-agent-public:phase2a
Get-FileHash public_demo_artifacts/public-demo-phase2a.tar -Algorithm SHA256
```

本機でのimage ID/アーカイブhash記録だけでは配信後の設定確認を代替しません。immutable image ID、変更していないbundle、quota volumeの保持を運用者が確認してください。

## 公開版だけの停止とrollback

```bash
docker compose -f compose.public-demo.yaml stop public-demo
docker compose -f compose.public-demo.yaml rm -f public-demo
```

初回配置で問題が起きた場合は、公開containerを停止・削除した状態をrollback完了とします。公開volumeは調査/再起動用に保持し、aws-v2へは触れません。

公開版の更新から戻す場合は、停止後に公開専用Composeのimageを**記録済みの旧公開image**へ戻し、同じro bundle・同じquota volumeで `up -d --no-build --wait public-demo`。旧imageとbundleの互換性を確認してください。quota stateを新しい空volumeへ交換すると日次上限がリセットされるため禁止です。今回quota schema migrationはありません。将来migrationする場合は、停止中のquotaを整合性のある方法でバックアップし、復元時に当日の使用数を減らさない手順を追加する必要があります。

`down -v`、`volume prune`、`system prune`、private containerのstop/rm/rename、私有データのseedは実行しません。公開bundleが破損した場合は安全側で停止し、勝手にmanifestを再生成して受け入れません。

## 検証記録と残るリスク

本ページの実測値はDocker Desktop Linux/amd64上の一時containerです。AWSの測定ではありません。既存の未追跡ファイルは保持します。最終imageのbuild・受け入れ結果をここへ追記します。

2026-10-13の最終検証：

- 公開専用contextは41ファイル。最終image IDは `sha256:ff9d53fb406220c2a892b1a677933ebd97edbeda19442a7bf8bbe455c2dc271c`。Docker image inspectのSizeは175,641,876 bytes（ホストのbuild cache/展開サイズ全体ではありません）。
- Linux Dockerでbuild成功。`pip check` は `No broken requirements found`。
- 一時containerで全HTTP method、偽装身份、RAG/Citation、只読rootfs/data、non-root、cap drop、no-new-privileges、IMDS到達不可を検証。`app.main`はimport不能、private API directoryは存在しません。
- 受理済み2回の照会でquotaを使い切り、restart後とcontainer削除/新規作成後の両方で429を確認。公開bundleの全file hashは一致。
- memory.peak = **138,223,616 bytes（約132 MiB）**。照会後のDocker statsは **90.94 MiB / 768 MiB、PIDs=14、CPU=0.18%、NetIO=0B/0B**。これらは短い小型fixtureテストの観測値です。
- 全量Python：**249 passed / 3 skipped**。Node：**9 passed**。既存の依存library非推奨warningは2件。git diff --check成功。
- 固有名のtest container/volumeを清掃済み。常設Compose container、EC2、aws-v2への操作はありません。コードはローカルでreview待ちです。

第二階段Aの提出前確認：最終imageをローカルのGit対象外archiveへexportし、参照される全20layer・17,157個のregular file entryを確認しました。40個のapplication/requirements fileは作業treeとSHA-256が一致し、private API、.env、private database/Chroma、Docker/AWS credentials fileは含まれていません。一般的な秘密情報patternの候補はONNX Runtimeの2つのbinary library内のNUL終端PEM format markerだけで、key本文を伴わないことを確認しました。この確認はCVE/悪意ある依存packageの完全な審査を代替しません。

実imageのENTRYPOINT/USER/HEALTHCHECKをinspectし、88件のinstalled dependencyがlockと一致することを確認しました。app serverのDocker受け入れはimageのdefault ENTRYPOINT/commandのまま起動します。entrypointをpythonへ上書きするのは、別のprepare jobと読み取り検査だけです。Composeのpublic-demo serviceもENTRYPOINT/commandをoverrideしません。旧Dockerfile・app.main・旧部署設定は変更していません。

公開ネットワーク/TLS/IMDS対策の変更設計、WAF等のDoS対策、運用監視・予算警報、実モデルの課金制御は次段階です。none networkをbridgeへ変える場合、EC2 roleのIMDS到達性や信頼proxy経路を改めて検証する必要があります。dependency/baseのversion固定は脆弱性がないことの保証ではなく、imageのCVE/supply-chain審査も公開前に必要です。Docker healthは実行停止を強制せず、アプリの10秒timeoutも永久停止したthreadを強制終了しません。
