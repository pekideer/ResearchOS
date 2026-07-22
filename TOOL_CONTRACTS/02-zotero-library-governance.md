# Zotero 文献库语义治理契约

## 适用工具

- `tools/zotero/zotero_ai_governance.py`
- `tools/zotero/governance/contracts.py`
- `tools/zotero/governance/evidence.py`
- `tools/zotero/governance/plans.py`
- `tools/zotero/build_zotero_library_context_packet.py`

## 两种互斥任务

| 任务 | 可用语义证据 | 可输出结果 |
|---|---|---|
| `content-tags` | 文献自身题名、摘要、题录事实、规范化全文片段 | 六类内容 `#tags`、复核状态、证据说明 |
| `library-structure` | 文献内容；另列的当前 tags/collection 只用于库结构治理 | domain/collection candidates、复核状态、证据说明 |

筛选范围不等于语义证据。`content-tags` 记录必须物理排除当前 tags、collection、项目名、项目用途、重要性、计划使用位置和项目关联笔记。两个任务不得共用混合结果 schema。

## 允许行为

- 从只读父文档和规范化文本生成证据记录。
- 为每条记录保存 `semantic_scope`、`selection_is_not_evidence` 和 `evidence_hash`。
- 由当前 agent 完成语义判断；工具验证任务专属字段、标签命名空间和条目映射。
- 生成只读 JSON/CSV/Markdown 语义计划。

## 禁止行为

- 不写 Zotero，不读取 `zotero.sqlite`，不移动 PDF。
- 不调用通用语言模型 API，不读取模型 API key。
- 不恢复历史 Zotero tags 为 AI 关键词。
- 不用关键词、评分、聚类或硬编码规则生成可发布标签、稳定文献集归属或科研结论。
- 不把只读语义计划直接当成已批准写入计划。

## 验收

- 相同文献在不同项目/collection 范围中生成相同的内容证据哈希。
- 内容标签包不存在 `current_state`，结果 schema 不含 domain/collection 字段。
- 文献库结构包把当前状态与文献内容分栏，且不输出内容标签。
- 证据不足时明确进入人工复核。
