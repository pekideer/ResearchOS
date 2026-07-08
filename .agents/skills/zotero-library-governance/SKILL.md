---
name: zotero-library-governance
description: 只读盘点 Zotero 文献库、文献集、标签、期刊和主题相似性，生成治理矩阵、主题聚类、分类排序和修改建议；任何写入 Zotero 的操作必须另行审批。
---

## 目标

帮助用户整理 Zotero 文献库和文件夹分类。该 skill 默认读取 ResearchOS 共享事实源：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。Zotero Local API 只作为维护父文档的上游。该 skill 提取对科研与治理最有用的元信息、所在 文献集、标签、期刊信息、DOI、年份、PDF 文本状态和 规范化文本路径等字段，形成可筛选、可排序、可审计的文献治理矩阵、主题聚类和 文献集/标签/元数据治理建议。

## 输入

- ResearchOS Zotero SQLite 父文档，默认 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite`。
- AI 规范化 PDF 文本目录，默认 `corpus/fulltext/zotero-library-normalized/`。
- Zotero Local API 地址，默认 `http://localhost:23119/api/`，仅用于父文档缺失、过期或需要增量同步时。
- Zotero user ID，默认 `0`。
- 可选分类规则文件，例如 `configs/zotero_governance_rules.example.json`。
- 可选筛选要求：研究方向、研究方法、研究对象、期刊名、期刊级别、文献集、标签、年份范围。
- 可选输出目录，推荐课题目录下的 `02-literature-matrix/`；ResearchOS 系统级人读报告进入 `docs/reports/library-governance/`，机器 CSV/JSON 写入低层机器留存区 `.researchos/outputs/machine/M-002-library-governance/`。
- 可选字段盘点需求：是否导出全部原始字段、是否读取子条目、是否生成字段用途清单。
- 可选主题整理需求：是否基于题目、摘要、标签和期刊生成相近主题文献簇、相似文献对和合并候选。

## 工作流

1. 先检查 `RUNBOOKS/zotero-library-parent-documents.md`，确认 SQLite 父文档和 规范化文本 目录可读。
2. 从 SQLite 读取 collections/items/tags/attachments/pdf_texts，建立 文献集 key 到层级路径、条目 key 到 规范化文本 的映射。
3. 使用父文档字段生成字段用途清单；只有父文档缺失或过期时才通过 Zotero Local API 重新同步。
4. 读取 顶层条目，提取元信息、文献集 keys、文献集路径、标签、期刊、DOI、年份、PDF 状态和 规范化文本路径等字段。
5. 可选读取 规范化文本 摘要片段，标记是否有可用全文。
6. 使用规则文件对研究方向、研究方法、研究对象、期刊级别做可解释匹配。
7. 生成 CSV/JSON 文献治理矩阵。
8. 使用根级 Zotero 治理工具根据题目、摘要、标签、期刊等字段计算主题相似度，输出相近主题文献簇和相似文献对。
9. 基于矩阵生成治理报告，包括元数据缺失、无 文献集、无 标签、疑似重复、标签别名、文献集建议等。
10. 如用户要求修改 Zotero，只生成修改建议和计划；写入操作必须在用户明确批准后单独执行。

## 输出

- Zotero 原始字段导出：`zotero_items_raw.json`。
- Zotero 字段用途清单：`zotero_field_inventory.csv`。
- Zotero 字段用途报告：`zotero_field_inventory.md`。
- Zotero 文献治理矩阵：`zotero_library_matrix.csv`。
- 可选 JSON 矩阵：`zotero_library_matrix.json`。
- 主题相似文献对：`zotero_similar_pairs.csv`。
- 主题聚类报告：`zotero_topic_clusters.md`。
- 主题整理计划：`zotero_topic_cluster_plan.json`，仅供审批。
- Zotero 文献库治理报告：`zotero_governance_report.md`。
- 可选修改计划：`zotero_governance_plan.json`，仅供审批，不自动执行。

## 质量规则

- 不编造研究方向、研究方法、研究对象或期刊级别。
- 原始字段必须完整保留在 JSON 中；CSV 矩阵只保留高价值字段和分类结果。
- 字段用途判断必须区分科研用途、治理用途和 API 技术字段。
- 主题相似性必须基于题目、摘要、标签、期刊等可复查字段，不把相近主题直接等同于重复条目。
- 合并候选只能作为人工复核线索；只有 DOI 或规范化标题高度一致时才标注为高风险重复候选。
- 自动分类必须给出规则来源；无匹配时留空或标注 `Unclassified`。
- 期刊级别必须来自用户提供的规则或可信来源，不能由模型直接臆测。
- 疑似重复只能作为候选，不能直接删除。
- 文献集/标签 修改建议必须说明理由和风险。
- 每条建议必须保留 Zotero 条目 key，方便人工复查。

## 安全规则

- 默认只读。
- 不读取或修改 `zotero.sqlite`。
- 不移动、复制、删除、重命名 PDF。
- 不自动删除 Zotero 条目、文献集、标签、笔记或附件。
- 不自动写入 Zotero。
- 如果进入写入阶段，必须满足：
  1. 用户明确批准具体计划 文件。
  2. 计划文件列出 `action`、条目 key、当前状态、目标状态、风险。
  3. 先 试运行。
  4. 每次批量修改前确认 Zotero 已同步或用户已备份。

## 完成条件

- 已生成用户请求的字段盘点、文献库矩阵、主题聚类、治理报告或治理计划。
- 每条治理建议保留 Zotero 条目 key 和可复查依据。
- 相近主题、疑似重复和写入候选清楚区分。
- 输出计划明确标注仅供审批，不自动写入 Zotero。
- 未读取或修改 `zotero.sqlite`，未移动、复制、删除或重命名 PDF。

## 写入能力说明

Zotero 官方 Web API 支持创建和更新 条目、文献集，以及通过 条目 JSON 的 `collections` 字段改变条目所在 文献集。ResearchOS 默认不写入 Zotero，Zotero Local API 不用于写入。任何写入必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`，经 试运行、人工确认、金丝雀测试、分批执行和回滚计划 后才能进行。

## 用法

从父文档构建上下文包：

```powershell
python tools\build_zotero_library_context_packet.py --query "KEYWORD" --limit 20
```

生成治理语料和报告：

```powershell
python tools\zotero_ai_governance.py prepare-corpus
python tools\zotero_ai_governance.py build-plan
python tools\zotero_ai_governance.py aggregate-directions
python tools\zotero_ai_governance.py build-collection-plan
python tools\zotero_ai_governance.py build-tag-plan
```
