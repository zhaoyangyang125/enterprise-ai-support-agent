# 私有EC2 Docker更新手順

この手順は更新準備です。今回AWSへの操作は実施していません。現在のイメージは`enterprise-ai-support-agent:aws-v1`。新イメージへの変更であり、DB migration・seed・再索引は不要です。

## 1. 構成確認とバックアップ

現在の起動スクリプト／実行コマンドをEC2内で確認してください。Docker inspectの全出力や環境変数には秘密情報が含まれる可能性があるため、チャット・Git・共有ログに貼らないでください。

```bash
docker inspect --format '{{.Config.Image}}' enterprise-ai-support-agent
docker inspect --format '{{json .Mounts}}' enterprise-ai-support-agent
docker port enterprise-ai-support-agent
```

- `business.db`、`chroma_data_dashscope`、`document_storage`の実際のホストパスとコンテナ側パス、所有者を確認。
- 同じ環境変数、collection、Embeddingモデル・次元・閾値、Qwen設定を維持。
- インスタンスロールによるSSMからの秘密情報取得処理を維持し、平文キーをファイルやGitへ保存しない。
- CloudWatchログドライバ／ロググループ設定、再起動policy、コンテナuserを維持。
- ホスト公開先は`127.0.0.1:8000:8000`のみ。EC2の8000番ポートを公网へ開放しない。

停止を短くするため、先に新イメージを構築し、その後コンテナを停止して整合性のある3項目のバックアップを取ります。DBのWAL等が存在する場合も含め、元の所有権とアクセス権を保った方法を選びます。稼働中のChromaファイルを単純コピーしないでください。バックアップはアプリのmount先と別の私有場所へ保存します。

## 2. 新しいソースとイメージ

PRを確認・マージ後、既存の作業コピーを確認します。未コミット変更がある場合は上書きしません。

```bash
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse --short HEAD
docker build -t enterprise-ai-support-agent:aws-v2 .
```

ビルド失敗時は旧コンテナを稼働させたまま原因を確認します。`aws-v1`を上書き・削除しません。構築環境にDockerがなかったため、今回のコード変更の実ビルドは未検証です。

## 3. コンテナ差し替え

1. 旧コンテナを停止し、データの整合性を保ったバックアップを取得。
2. 旧コンテナを削除せず、例として`enterprise-ai-support-agent-rollback`にrename。
3. **確認済みの既存起動スクリプト／docker runコマンドで、イメージだけをaws-v2に変更**して新コンテナを起動。名前は`enterprise-ai-support-agent`。mount、env、SSM取得、CloudWatch、loopback bindを維持。
4. 新旧コンテナを同じSQLite / Chromaへ同時接続させない。

環境の実パス・SSM取得コマンドがリポジトリには保存されていないため、推測のdocker runコマンドは記載しません。旧構成を確認してから実行します。seed、索引削除、Docker volume削除、イメージ内データへの置換は行いません。

## 4. 私有環境で検証

SSHポート転送でアクセスし、ブラウザを強制再読み込みします。

- 日语欢迎语、标签、質問例、上传反馈和图片操作提示。
- 「私の有給休暇はあと何日ありますか？」が残日数Toolへ到達し、**現在のDBの値**を返す（8日に固定しない）。
- 「有給休暇の取得ルールを教えてください」がRAGへ到達。既存文書に根拠がなければ拒答する。
- 宿泊費の既存Citation、取り込み済み画像の表示。
- U999への身份切换後に旧結果が消え、無権限の文書・旧画像URLが拒否される。
- 文書バージョン状態と既存索引を確認。既存機密データを検証のためにアップロードしない。
- CloudWatchへのログ転送を確認し、秘密情報が出力されていないことを確認。

## 5. ロールバック

新コンテナを停止してから、旧コンテナを元の名前に戻して起動します。新コンテナは調査用に別名で停止状態を維持できます。書き込みを行わない検証なら既存データをそのまま使用します。書き込み・データ破損がある場合は両コンテナを停止し、確認したバックアップへ戻す必要があります。Dockerの一括削除や索引再作成はしません。
