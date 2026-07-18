# Zotero 文献库治理与语义聚合契约

## 1. 适用工具

- 主入口：`zotero_ai_governance.py`
  - `prepare-corpus`
  - `build-agent-packet`
  - `build-plan`
- `zotero_new_item_monitor.py`

## 2. 工具目的

本专题工具用于只读盘点 Zotero 文献库、文献集、标签、新条目和候选文献，准备带来源的语料包，并校验当前 ChatGPT/Codex agent 输出的结构化治理结果。工具本身不调用语言模型，不以关键词或评分逻辑替代 agent 完成研究语义分类。

## 3. 输入

- ResearchOS Zotero 父文档。
- 规范化 PDF 文本。
- 已生成的治理 CSV、JSON、JSONL 或 Markdown。
- 用户明确指定的主题、文献集、标签或候选范围。

## 4. 输出

- 文献库盘点表。
- 主题聚类和研究方向矩阵。
- 文献集重构建议。
- 标签治理建议。
- 新条目分诊报告。
- 候选阅读清单。

## 5. 允许行为

- 只读分析父文档和本地治理产物。
- 统计文献集、标签、主题族、条目共现和缺失信息。
- 生成本地 `.researchos/outputs/machine/` 下的机器表，以及 `docs/reports/library-governance/` 下的系统级人读报告。
- 给出待人工确认的治理建议。
- 生成供当前 agent 读取的 JSONL/plain text 语料包，校验 agent 返回的结构化结果。

## 6. 禁止行为

- 不写入 Zotero。
- 不创建、删除、移动或重命名 Zotero 文献集。
- 不直接修改标签、笔记、条目或附件。
- 不把聚类、AI 分类或候选建议当作已批准写入计划。
- 不直接调用 OpenAI 或其他通用语言模型 API，不读取或管理模型 API key。
- 不依据关键词命中自动生成研究方向、方法、对象标签或稳定文献集归属。
- 不编造文献、DOI、作者、期刊、会议或条目事实。

## 7. 质量检查

- 报告必须明确区分事实、推断、建议和需要核查项。
- 主题聚类必须保留人工复核入口。
- 候选文献若来自外部检索，应记录来源、URL 或 DOI。
- 新条目监控只读顶层元数据，不读取 PDF，不写入 Zotero。
- 新条目 `check/report` 输出只作为 agent 语料；语义分类和标签建议由当前 agent 完成。
