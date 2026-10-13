# 実Demoのスクリーンショット

今回の実行環境から`http://127.0.0.1:8000/`に接続できませんでした。利用者のWindows上のSSHトンネルはクラウド作業環境には共有されません。そのため、画像を作成・掲載したとは記録していません。

## 更新後の自動撮影

EC2のaws-v2更新を完了し、SSM設定・既存DB・索引を保持した状態で、本機のSSHポート転送を接続してください。このスクリプトはAWS設定を変更せず、seed・申請・アップロードもしません。撮影は読み取り照会のみですが、既存のQwen/Embedding設定によって外部API費用が発生する場合があります。

プロジェクトのfeature/recruiter-readme-showcaseブランチで、以下を実行します。Playwrightは撮影用の任意依存であり、アプリの依存には追加していません。

```powershell
python -m pip install playwright
python -m playwright install chromium
python scripts/capture_recruiter_demo.py --aws-v2-confirmed
```

`--aws-v2-confirmed`は利用者が更新完了を確認したことを表す指定であり、ブラウザからイメージ名を検証する機能ではありません。スクリプトは日語UI、宿泊費1泊10,000円とTravelPolicy_v1.pdf / Page 3のCitation、現在のDB残日数との一致を検証します。片方でも失敗した場合、新しいPNGは保存しません。モデル回答を作り直したり、DOMへ架空の回答を挿入したりしません。

成功時に`docs/images/rag-query.png`と`docs/images/leave-balance.png`を保存し、READMEの非表示markerを実画像の参照へ置換します。PNGは本機ブラウザで取得した実画面です。保存後、文字の読みやすさと秘密情報・実在企業情報がないことを目視確認し、READMEとPNGだけを追加して同じPRに含めます。

```powershell
git add README.md docs/images/rag-query.png docs/images/leave-balance.png
git commit -m "docs: add verified Japanese private demo screenshots"
git push
```

既存ファイルがある場合、失敗時には前回の画像が残るため、新規撮影成功のログがない状態で古い画像を新しい撮影結果として扱わないでください。図像への個人情報・社内情報の混入が懸念される場合は公開前に除外します。
