# 実Demoのスクリーンショット

2026-10-13、既存のAWS私有DemoをSSHポート転送先 `http://127.0.0.1:8000/` で開き、ローカルのPython Playwright 1.57.0 / Chromiumで撮影しました。画像生成・回答の差し替え・DOMへの架空データ挿入は行っていません。

## 検証結果

認証入力は `U001 / D-SALES / EMPLOYEE,ADMIN`。画像は1440 × 1100のPNGです。

| 画像 | 実際の質問 | 確認結果 |
|---|---|---|
| [RAG照会](images/rag-query.png) | 国内出張の宿泊費上限はいくらですか？ | HTTP 200、knowledge_query、1泊10,000円、evidence_found=true、TravelPolicy_v1.pdf / Page 3 |
| [残日数照会](images/leave-balance.png) | 私の有給休暇はあと何日ありますか？ | HTTP 200、leave_balance、8日、本人の残日数APIと一致。sourcesは空（業務DB照会） |

各質問を新しいページ表示から実行し、チャット欄に問答全体が収まることを検証してから撮影しました。2枚とも目視確認済みで、質問・回答・RAGのCitationが欠けず、日本語が明瞭に表示され、中国語翻訳の残留はありません。AWS、DB、索引、RAGアルゴリズム、業務APIは変更していません。申請・seed・アップロードも実行していません。

## 再撮影

Playwrightは撮影用の任意依存で、アプリの依存設定には追加していません。今回は本機にインストール済みの環境を使用しました。未導入の場合は別の撮影用venvにインストールしてください。

```powershell
python -m pip install playwright
python -m playwright install chromium
python scripts/capture_recruiter_demo.py --aws-v2-confirmed
```

`--aws-v2-confirmed`は接続先の更新確認を表す既存の指定です。AWSのイメージ名をブラウザから検証する機能ではありません。現在の残日数APIと回答を比較するため、8日を固定値として扱いません。両方の検証成功後にのみPNGを保存します。失敗時は以前のPNGが残るので、新規撮影成功のログと画像を確認してください。

モデル回答とCitationを検証する読み取り照会のみですが、接続先のモデル設定によって外部API利用が発生する場合があります。再撮影後は画像を目視確認し、READMEの撮影日・観測値も更新してください。
