# 実ファイルRAG評価レポート / 真实文件RAG评测报告

> 2026-09-22 补充说明：原报告的指标仍是 Hash Embedding + 本地证据回答的历史基线，不是 Gemini 结果。现在可显式运行 `python -m app.evaluation.real_provider_suite`，它复用同样的 5 份虚构文档与 24 个问题，分别报告 Vector/Hybrid 检索、ACL／拒答、Citation 和基础回答字面事实命中。运行前须在私有终端设置 `RUN_REAL_RAG_EVALUATION=1`、`RAG_EMBEDDING_MODE=gemini`、模型及密钥；会产生外部 API 调用。本次未运行真实云端评测，因此没有新增真实模型指标。回答字面指标只检查至少一个人工核定事实字符串是否出现在回答中，不等价于真实性或完整性；同义改写需人工复核。OCR／Vision 部分仍为固定模拟输出。新模型的 Evidence Gate 阈值必须根据结果重新校准，不能直接把旧基线当生产准确率。

> 2026-09-23：真实评测入口也支持 `RAG_EMBEDDING_MODE=dashscope` 与可选的 `RAG_ANSWER_MODE=qwen`。千问模式读取 `DASHSCOPE_API_KEY`，使用百炼兼容接口；仍需用户显式开启真实评测。

## 2026-09-26 千问真实 Embedding 验收

本次使用 `text-embedding-v4`（1024维）运行同一套5份虚构文档、60个Chunk和24个问题。为了单独评价检索，回答模式使用确定性的 `evidence`；OCR／Vision仍使用固定模拟Provider。因此，本节证明真实Embedding已经接入检索链，不代表真实OCR或生成式回答的总体准确率。

| 指标 | Vector-only | Hybrid |
|---|---:|---:|
| Hit@1 | 0.5714 | 0.7143 |
| Hit@K | 1.0000 | 1.0000 |
| Recall@K | 1.0000 | 1.0000 |
| MRR | 0.7579 | 0.8135 |
| Source Hit Rate | 1.0000 | 1.0000 |

Evidence Gate 使用真实向量原始语义分数，而不是RRF融合分数。旧阈值 `0.25` 会让两个无答案问题误通过；观察到的无关结果最高分约为 `0.347`，将本数据集候选阈值校准为 `0.36` 后，21个有答案问题、2个无答案问题和1个ACL问题全部通过：

- 正确Citation：21 / 21
- 基础回答事实检查：21 / 21
- 无答案与ACL安全判断：3 / 3

检索耗时不可直接横向解读：同一进程中的查询Embedding有单次运行缓存，Vector阶段先支付云端调用时间，随后Hybrid可能命中缓存。因此不能据此宣称Hybrid天然比Vector快。

正式应用索引采用并行迁移，没有覆盖旧Hash索引：旧位置为 `chroma_data / enterprise_documents`，新位置为 `chroma_data_dashscope / enterprise_documents_text_embedding_v4_1024`。迁移了28个现有正式Chunk；这里的28个应用Chunk与评测套件临时生成的60个评测Chunk不是同一数据集。

浏览器端到端验收还确认：年假余额查询返回8天；国内出差住宿费问题引用 `TravelPolicy_v1.pdf / Page 3`；精确编号 `TEST SAFETY CODE 7392` 只保留对应OCR PDF第1、2页；完全无关的“月面基地停车费”问题正确拒答。最终全量自动测试为 `197 passed, 3 skipped, 2 warnings`。

本次离线复测（2026-09-22）：Vector Hit@1 0.7143、Hit@K 1.0、Recall@K 1.0、MRR 0.831、Source Hit Rate 1.0；Hybrid 分别为 0.6667、1.0、1.0、0.8056、1.0。正例 Citation 21/21；基础答案事实与已传证据的字面一致性 21/21；No-answer／ACL 3/3。以上仅为固定小型虚构数据集结果，并不代表生产环境整体精度。

評価日: 2026-09-20

## 1. 目的

この評価は、メモリ上に手作業で作成したChunkだけではなく、実際のPDF/ExcelファイルをParser、OCR/Vision境界、Chroma、Hybrid Search、Evidence Gateまで通して検証する。

本次评测不只使用内存中的假Chunk，而是让真实PDF/Excel文件经过Parser、OCR/Vision边界、Chroma、Hybrid Search和Evidence Gate。

## 2. 評価データ

すべての資料は本プロジェクト専用に作成した架空データであり、実在企業の仕様書や機密情報を含まない。

| 文档 | 类型 | 生成Chunk数 |
|---|---|---:|
| `fictional_hmi_policy.pdf` | 文字型PDF | 12 |
| `fictional_hmi_test_spec.xlsx` | 多Sheet Excel | 25 |
| `fictional_can_diagnostics_reference.pdf` | 文字型PDF | 12 |
| `fictional_hmi_change_review.xlsx` | 表格、备注、嵌入图片 | 10 |
| `fictional_ocr_display_notice.pdf` | 扫描风格PDF | 1 |
| 合计 | 5份文件 | 60 |

Golden Dataset包含21个有答案问题，以及2个无答案拒答问题和1个ACL拒绝问题，共24题。预期来源由人工确认到文件、PDF页码或Excel Sheet / Cell Range。

## 3. 実行範囲

实际执行链路：

```text
真实PDF / Excel
-> DocumentService
-> PDF / Excel Parser
-> OCR / Vision边界
-> ParsedBlock / IndexedChunk
-> Chroma + Hash Embedding
-> Vector Search / BM25 / RRF
-> Evidence Gate
-> metadata-based Citation
```

PDF/Excel解析、Business DB、Chroma、Vector/BM25/RRF、权限和Citation均使用真实本地实现。为了离线可重复执行，扫描PDF和Excel图片使用确定性的Fake OCR/Vision Provider；这部分不代表云OCR识别准确率。Google OCR与Gemini Vision的真实云调用结果由现有live测试和README中的独立验收记录覆盖。

## 4. 結果

Top-K固定为5。

| 指标 | Vector-only | Hybrid |
|---|---:|---:|
| Hit@1 | 0.7143 | 0.6667 |
| Hit@5 | 1.0000 | 1.0000 |
| Recall@5 | 1.0000 | 1.0000 |
| MRR | 0.8310 | 0.8056 |
| Source Hit Rate | 1.0000 | 1.0000 |
| 本机平均检索时间 | 3.858 ms | 12.650 ms |

RAG最终证据判断：

| 场景 | 结果 |
|---|---:|
| 21个有答案问题找到正确Citation | 21 / 21 |
| 2个无答案问题正确拒答 | 2 / 2 |
| 无权限用户查询受限文档正确拒绝 | 1 / 1 |

平均耗时只是本机单次回归观测，不用于跨机器性能比较。

## 5. 評価で発見した問題

### 重复Chunk ID

CAN PDF同一页出现两次相同的`100 ms`，旧逻辑生成了相同Chunk ID，导致Chroma拒绝整批写入。修复后，首个Chunk继续使用原ID，后续重复Chunk使用基于出现顺序的稳定ID，因此不会改变普通Chunk的既有ID。

### 无关问题的Hash碰撞

“员工食堂早餐补助”与HMI文档无关，但本地Hash Embedding产生了约0.21的偶然相似度。默认Evidence Gate语义阈值由0.15调整为0.25。调整后，21个正例仍全部找到正确Citation，两个无答案问题均正确拒答。

## 6. 誠実な制約

- 在这套真实文件集上，Hybrid的Hit@1没有超过Vector-only，因此不能宣称Hybrid在所有数据上都更准确。
- Hybrid仍保持Hit@5、Recall@5和Source Hit Rate为1.0，并继续为编号、CAN ID、Sheet和Cell Range提供精确关键词能力。
- 当前Hash Embedding仅用于离线架构和安全链路验证。生产环境需要正式Embedding模型，并重新进行阈值校准和更大规模评测。
- 24题是面试项目规模的人工确认回归集，不代表生产环境总体准确率。

## 7. 再現方法

```powershell
python -m scripts.run_corpus_evaluation
```

相关自动测试：

```powershell
python -m pytest tests/evaluation/test_corpus_suite.py -q
```

## 8. 全体回帰テスト

```text
Backend: 169 passed, 3 skipped, 2 deprecation warnings
Frontend: 4 passed, 0 failed
```

Skip内訳は、明示実行が必要なGoogle OCR / Gemini Vision liveテスト2件と、正式アプリに含まれない任意の`practice`学習モジュール1件。警告2件はStarlette / httpxとAnyIOの非推奨APIに関するもので、今回の業務ロジック失敗ではない。
