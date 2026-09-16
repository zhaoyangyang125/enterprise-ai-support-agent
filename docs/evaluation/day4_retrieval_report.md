# Day 4 小型检索评测报告 / Small Retrieval Evaluation

## 1. 目的

本报告验证复杂 PDF/Excel metadata、权限过滤、可选 metadata Filtering 和 Citation 定位能否按设计协同工作。

这是一套 6 题的固定回归评测，不是生产环境准确率基准。它使用本地字符二元组检索和完全虚构的 HMI 数据，主要用于尽早发现代码回归。

## 2. 数据集

| 类型 | 数量 | 内容 |
|---|---:|---|
| PDF 有答案问题 | 2 | 视频画面安全规则、证据不足时的处理 |
| Excel 有答案问题 | 2 | `HMI-AC-001`、`VehicleSpeed` |
| 无答案/安全问题 | 2 | 越权文件筛选、不存在的 Sheet |
| 合计 | 6 | 全部为虚构数据 |

Top-K 固定为 5。有答案问题的预期 Chunk 和来源位置由人工预先写入测试用例；无答案问题预期过滤后返回空集合。

## 3. 指标定义

- Retrieval Hit Rate：有答案问题中，Top-K 至少包含一个预期 `chunk_id` 的比例。
- Source Hit Rate：有答案问题中，Top-K 至少包含一个与预期文件及 page/Sheet/Cell Range 相符结果的比例。
- No Evidence Accuracy：无答案问题中，权限和 metadata 过滤后确实没有返回 Chunk 的比例。
- Average Retrieval Time：本次运行中 Repository 检索阶段的平均耗时，仅供本机回归观察，不用于跨机器性能比较。

## 4. 2026-09-05 运行结果

| 指标 | 结果 |
|---|---:|
| Total Cases | 6 |
| Retrieval Hit Rate | 1.0000 |
| Source Hit Rate | 1.0000 |
| No Evidence Accuracy | 1.0000 |
| Average Retrieval Time | 0.313 ms |

逐题结果：

| Case | 预期 | 结果 |
|---|---|---|
| `PDF-001` | 命中 PDF Page 2 | 通过 |
| `PDF-002` | 命中 PDF Page 3 | 通过 |
| `XLSX-001` | 命中 `機能仕様 / A8:H12` | 通过 |
| `XLSX-002` | 命中 `CAN信号 / A5:F9` | 通过 |
| `SECURITY-001` | metadata 指向秘密文件也不能扩大权限 | 通过，返回空集合 |
| `NO-ANSWER-001` | 不存在的 Sheet | 通过，返回空集合 |

## 5. 诚实边界

- 100% 表示这 6 个固定回归用例通过，不表示真实用户问题达到 100% 准确率。
- 当前使用本地确定性字符二元组检索，不代表生产 Embedding 模型效果。
- 当前问题数量过少，不能用于模型选型或阈值校准。
- RAG Service 对低分证据的拒答由独立测试覆盖；本报告主要评测 Repository 的权限、metadata 和定位行为。
- 正式质量评测需要扩大人工标注问题集，并加入 Recall@K、错误分类和真实响应时间统计。

## 6. 运行方法

```powershell
python -m app.evaluation.sample_suite
```

自动化验证：

```powershell
python -m pytest tests/evaluation -q
```
