# Paper Reading To Literature Matrix Runbook

本操作手册说明从 Zotero 读书卡到综述矩阵的完整流程。

## 适用场景

- 已有若干 Zotero 条目或读书卡。
- 需要比较研究对象、方法、指标、结论和 gap。
- 需要形成可用于选题或论文综述的矩阵。

## 步骤

### 1. 读取 Zotero 条目

按 `RUNBOOKS/zotero-local-api-readonly.md` 搜索、读取 item、定位 PDF 并抽取文本。

### 2. 生成读书卡

使用 `paper-deep-reading`，每篇读书卡至少包含：

读书卡版式与元数据位置遵循 `RUNBOOKS/reading-card-governance.md`。集中主卡开头保留简短 YAML 头部；题目、作者、第一作者一级单位与国家、年份、期刊/来源、Zotero 条目 key、摘要、阅读状态、计划用途、证据强度、PDF 附件、Zotero 版本、collections、relations 等详细字段放入文末 `## 7. 元数据（折叠）`。正文标题必须编号。作者和单位按 `templates/reading-card-first-page-bibliographic-extraction-prompt.md` 从 PDF 首页或前两页语义识别。

- 条目 key
- 题录信息
- 作者规范化显示名，以及第一作者一级单位和国家
- 生成时间戳 `generated_at`
- 可选 PRISMA record ID
- 可选阅读状态、重要性和计划用途
- `## 一段话综述`：用一段话概括背景、目的、方法、结论和意义
- 可选 `tags`、`topic_relevance`、`journal_abbrev`、`rating_5`、`evidence_strength`、`gap_ids`
- 文本来源和页数范围
- 研究问题
- 方法路线
- 数据/模型/实验条件
- 关键变量
- 主要结论
- 局限性
- 需要核查内容

### 2A. 同步阅读总表

每生成或更新一张读书卡后，可同步项目级阅读总表：

```powershell
python tools\reading_cards\sync_reading_summary_table.py --project-root "课题目录"
```

如课题使用 PRISMA records：

```powershell
python tools\reading_cards\sync_reading_summary_table.py --project-root "课题目录" --prisma-records "课题目录\03-文献矩阵\prisma\prisma-records.csv"
```

`03-文献矩阵/04-阅读总表/LM-004_reading-summary-table.html` 用于紧凑浏览全部题录；`03-文献矩阵/04-阅读总表/分主题阅读总表/LM-004_reading-summary-table-<code>.html` 按课题方向拆分，每个 HTML 标题区显示对应方向。方向由 `.research/project_manifest.yml` 的 `topic_directions` 或 `.research/topic_directions.csv` 指定；未配置时从读书卡 `tags` 中的 `T数字_方向名` 自动发现。表格包含一段话综述、相关程度、读书卡、Zotero 条目/PDF 链接、期刊缩写、评分、阅读状态和 PRISMA 字段；标题下方提供总表和各方向子表的本地 HTML 跳转导航；点击表头可排序，表头分隔线可拖拽调整列宽，同一路径下的列宽由浏览器本地记忆。`LM-004_reading-summary-table.md` 是备用表，CSV 镜像和提醒写入同一 `04-阅读总表/` 目录。它不替代下一步的分析型文献矩阵。需要人工打开参阅的行使用 `RC-###` 编号；同步提醒使用 `TODO-###` 编号。

阅读总表中的“卡”按钮使用本地文件链接。

### 3. 统一字段

统一标题、作者、年份、DOI、条目 key、PRISMA record ID、研究对象、方法、指标、场景、数据来源和结论。

### 4. 生成综述矩阵

使用 `literature-matrix` 输出：

- 文献矩阵表。
- 研究对象分类。
- 方法分类。
- 指标分类。
- 已解决问题。
- 真实研究缺口。
- 伪研究缺口。
- 选题建议。

### 5. 质量检查

使用：

- `Evidence Gate`
- `Source Gate`
- `过度声称门禁`
- `Output Gate`

## 完成标准

- 每篇文献保留 条目 key 或明确来源。
- 每张读书卡保留 `generated_at`；如进入 PRISMA 流程，应能回溯到 `prisma-records.csv`。
- gap 由矩阵支撑，不凭直觉编造。
- 不把“当前材料未覆盖”直接写成“领域空白”。
