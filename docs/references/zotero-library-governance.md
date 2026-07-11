# Zotero 文献库治理规则

## 目标

Zotero 文献库治理的目标不是一次性重构整个库，而是先形成可复查的矩阵，再逐步改进 文献集、tag 和元数据质量。

## 治理对象

- top-level 文献条目
- 文献集和 文献集层级
- tag 和 tag 写法
- 期刊/会议名
- DOI、年份、URL、摘要等元数据
- PDF 附件 是否存在
- 规范化 PDF 文本 是否存在及其父文档路径

## 默认流程

1. 读取 ResearchOS Zotero 父文档：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite`。
2. 读取 `corpus/fulltext/zotero-library-normalized/` 中与 attachment 对应的 规范化 PDF 文本 状态和路径。
3. 只有父文档缺失、过期或需要增量同步时，才通过 Zotero Local API / `tools/zotero/zotero_library_index.py` 更新父文档。
4. 导出或复用父文档中的完整字段快照，保留原始字段。
5. 生成 `zotero_field_inventory.csv` 和 `zotero_field_inventory.md`，判断每类字段的科研用途和治理用途。
6. 生成 `zotero_library_matrix.csv`。
7. 基于用户规则匹配研究方向、研究方法、研究对象和期刊级别。
8. 基于题目、摘要、标签、期刊和 规范化文本 可用性等字段生成 `zotero_topic_clusters.md` 和 `zotero_similar_pairs.csv`。
9. 生成 `zotero_governance_report.md`。
10. 生成 `zotero_governance_plan.json` 作为候选修改计划。
11. 用户逐条确认或修改 plan。
12. 进入写入阶段前，确认 Zotero 已同步或已有备份。

## 字段用途分层

- 高价值科研字段：标题、作者、摘要、年份、期刊/会议、DOI、URL、关键词、文献集、tag。
- 高价值治理字段：条目 key、item type、collections、tags、dateAdded、dateModified、PDF 附件 信息。
- 中等价值字段：卷期页、出版社、语言、extra、relations、格式化引用。
- 低价值或技术字段：API links、library、version、部分 meta 字段。

原则：原始 JSON 全量保留；人工治理矩阵只抽取高价值字段和可解释分类结果。

## 相近主题和合并候选

相近主题判断使用：

- `title`
- `abstractNote`
- `tags`
- `publicationTitle`
- `journalAbbreviation`
- `extra`

输出分三类：

- 主题簇：适合放入相同或相邻 文献集的文献组。
- 相似文献对：需要人工判断是否属于同一研究方向。
- 重复候选：DOI 一致、规范化标题一致，或文本相似度极高的条目。

限制：

- 相近主题不等于重复条目。
- 合并候选不等于自动合并。
- 删除、合并、移动 collection 前必须人工确认。

## 分类规则

研究方向、研究方法、研究对象和期刊级别必须来自显式规则或可信来源。

示例规则文件：

```text
configs/zotero_governance_rules.example.json
```

期刊级别不能由模型直接臆测。可接受来源包括：

- 用户手动维护的期刊分区表。
- 学校或课题组认可的期刊目录。
- 用户明确提供的 JCR、中科院分区、EI、SCI、北大核心等来源。

## 建议类型

- `review_metadata`：元数据缺失，需要人工补全或核查。
- `review_tag_alias`：tag 大小写或写法可能不一致。
- `consider_collection_assignment`：规则匹配到研究方向，但当前 collection 未体现该方向。

这些建议不是最终操作，只能作为人工整理线索。

## 写入前审批要求

任何写入 Zotero 的操作必须满足：

1. 用户明确批准具体 plan 文件。
2. plan 中每条 action 必须包含 条目 key、当前状态、目标状态、理由和风险。
3. 先执行 试运行。
4. 用户确认 Zotero 已同步或已备份。
5. 不批量删除条目、文献集、标签、笔记或 attachment。

## 禁止事项

- 不读取或修改 `zotero.sqlite`。
- 不删除 Zotero 条目。
- 不删除 PDF 附件。
- 不移动、复制、重命名 PDF。
- 不根据自动分类直接覆盖用户已有 collection。
- 不把疑似重复条目直接删除。

## 可接受的未来写入操作

在用户审批后，可以考虑实现以下低风险操作：

- 给条目添加 tag。
- 把条目加入已有 collection。
- 新建 collection。
- 将条目加入新建 collection。

高风险操作，例如删除条目、删除 文献集、删除 标签、移动附件、修改 PDF 文件路径，不纳入默认自动化范围。
