# 复杂文档增强计划 / Complex Document Upgrade Plan

本文档记录 Project 3 的 6 天加速开发范围。开发在独立 Git 工作树中进行，不修改项目所有者当前用于复习的目录。

## 1. 开发隔离

| 项目 | 内容 |
|---|---|
| 复习目录 | `D:\AI\enterprise-ai-support-agent` |
| 开发目录 | `D:\AI\enterprise-ai-support-agent-complex-doc` |
| 基线提交 | `8a1256a` |
| Day 1 分支 | `feature/complex-doc-day1-spec` |
| 原则 | 每天一个独立分支；测试通过后才形成当天提交；未经确认不合并 |

原目录中的 `practice/` 和 `tests/services/test_leave_availability_service.py` 是未跟踪学习文件，不会进入隔离工作树，也不会被覆盖。

## 2. 本轮目标

本轮实现 Level 2：企业文字型复杂文档的结构化解析。

包含：

- Excel 多 Sheet。
- 一个 Sheet 中存在多个结构区域。
- Key-Value、Table、Note、Paragraph 等区域分类。
- 多行表头组合。
- 合并单元格的语义继承。
- Section、Sheet 和 `cell_range` 定位。
- PDF 页眉页脚清理、标题和正文区分、页内 Chunk。
- Citation 与小型检索评测。
- 可演示前端和交付文档。

本轮不包含：

- OCR 和扫描 PDF。
- 图片、图表及视觉模型理解。
- 任意排版的自动推断。
- 复杂跨页表格视觉还原。
- 生产级大规模性能优化。

## 3. 目标数据流

```text
原始 PDF / Excel
-> Parser 读取原始结构
-> Region Detection（区域识别）
-> Structure Conversion（结构转换）
-> ParsedBlock
-> IndexedChunk + stable chunk_id
-> Chroma
-> Authorized Retrieval
-> metadata-based Citation
```

权限边界保持不变：先从 Business DB 取得允许访问的有效 `document_version_id`，再带过滤条件查询 Chroma。Parser 的增强不得削弱 Retrieval 前权限过滤。

## 4. ParsedBlock 目标契约

计划将当前只有内容和基础定位的 `ParsedBlock` 扩充为：

```text
content          必填：供检索使用的结构化文本
content_type     必填：title / key_value / table / note / paragraph
page             PDF 页码，可空
section          所属标题或章节，可空
sheet            Excel Sheet 名，可空
cell_range       Excel 精确范围，例如 A8:H12，可空
rows             兼容旧 Citation 的过渡字段，可空
```

`cell_range` 表达原始位置；`content_type` 表达内容在原文中的结构角色。两者均来自 Parser 的确定性结果，不由 LLM 生成。

## 5. Excel 解析规则

### 5.1 区域类型

- `title`：跨多列的标题或章节标题。
- `key_value`：标签和值成对出现的说明区域。
- `table`：包含 Header 和数据行的二维区域。
- `note`：备注、注意事项或说明块。

### 5.2 多行表头

多行表头按列路径组合。例如：

```text
CAN信号
  ├─ 信号名
  └─ 期待値
```

转换后使用：

```text
CAN信号 / 信号名
CAN信号 / 期待値
```

避免只保留第二行而丢失上级语义。

### 5.3 合并单元格

- 读取合并区域左上角的原始值。
- 数据行中的纵向合并值可继承给所属行。
- 标题型横向合并不能复制成多个重复字段。
- 不通过全工作表无条件展开来破坏标题和区域边界。

### 5.4 多区域

同一 Sheet 中由空白行、Section 标题和 Header 变化分隔的多个表，必须生成不同 Block，不能把后一个表的数据套用前一个表头。

## 6. PDF 解析规则

- 仅处理有文本层的 PDF。
- 保留 `page`。
- 检测重复出现的短页眉和页脚，并从正文 Chunk 中去除。
- 页内按标题和自然段组合，不按固定字符盲切。
- 超过大小上限时再进行有边界的拆分。
- OCR、图片和表格视觉还原留到后续版本。

## 7. Day 1 架空样本

`samples/fictional_hmi_test_spec.xlsx` 是完全虚构、可公开的日语车载 HMI 测试式样书，包含：

- `README`：样本声明和解析目标。
- `機能仕様`：Key-Value、多行表头、纵向合并、多张表和 Note。
- `画面遷移`：Key-Value、两个独立表格和 Note。
- `CAN信号`：多行表头、信号表和值定义表。

测试预期保存于 `tests/fixtures/complex_documents/fictional_hmi_expected_regions.json`。

## 8. 6 天安排

| Day | 内容 | 安全停止点 |
|---|---|---|
| 1 | 式样、样本、目标 Schema、测试矩阵 | 不修改 Parser 业务代码 |
| 2 | Excel Region Detection 和结构转换 | Excel 新旧测试全部通过 |
| 3 | PDF 增强和统一 metadata | PDF/Excel Parser 测试通过 |
| 4 | Citation、Filtering 和小型 Evaluation | 无证据拒答和权限测试通过 |
| 5 | 前端演示：上传、状态、聊天、Citation | 本地端到端演示通过 |
| 6 | Docker、日志、README、架构图、面试资料 | 全量测试通过，准备 PR；不自动合并 |

## 9. 学习分类

- 【模板代码｜理解即可】：配置、文件选择、测试 fixture、样式。
- 【半模板代码｜需要会改】：Schema、Parser Registry、metadata 转换、API Response。
- 【核心代码｜需要会讲】：Region Detection、多行表头、合并单元格、Chunk 边界、Citation、Evaluation。

核心代码的学习顺序保持为：目标 → 数据流 → 输入输出 → 数据结构 → 关键规则 → 测试 → 错误解释 → 面试总结。
