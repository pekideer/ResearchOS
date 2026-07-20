---
name: zotero-library-governance
description: 只读盘点 Zotero 文献库，并分别生成只基于文献自身内容的 #tags 建议或文献库结构建议；任何写入必须另行审批。
---

## 目标

以 ResearchOS Zotero 父文档和规范化文本为事实源，生成可审计的文献库治理建议。语义任务必须先选择且只选择一种：

- `content-tags`：从文献自身内容生成 `#Type/`、`#Status/`、`#Method/`、`#Object/`、`#Parameter/`、`#Field/` 标签。
- `library-structure`：结合文献内容与单独呈现的库内现状，审查领域和文献集结构。

两个任务不得合并为同一个语料包、结果 schema 或审批计划。

## 强制语义边界

- `content-tags` 的证据只能来自题名、摘要、题录事实和规范化全文片段。
- 条目因何项目、查询、collection 或人工范围被选中，只决定处理范围，不构成标签证据。
- 内容标签包必须物理排除当前 tags、collection paths、项目名称、项目用途、重要性、计划使用位置和项目关联笔记。
- 同一篇文献无论从哪个项目或文献集进入流程，都应得到同一份内容证据和同一类内容标签判断。
- 当前 agent 应输出基于证据能够成立的完整目标内容标签集，而不是只看“是否已有任意 `#` 标签”。在后续确定性对账中，只要目标维度缺失、旧值与目标冲突或存在明确禁用的 `#` 标签，就判定为不足/需修正；机器识别 tags 和 `rs:*` 不算内容标签充分性。
- 当前 agent 完成语义判断；代码只准备证据、记录哈希、校验任务专属 schema 和生成只读计划。
- 不恢复历史 tags 为关键词，不以关键词、评分、聚类或代码内模型调用生成可发布标签或稳定归属。

## 工作流

1. 检查 `RUNBOOKS/zotero-library-parent-documents.md`，确认父文档和规范化文本可读。
2. 明确任务为 `content-tags` 或 `library-structure`；若用户同时要求，两条管线分别运行。
3. 用 `prepare-corpus --task ...` 生成带 `semantic_scope`、`selection_is_not_evidence` 和 `evidence_hash` 的证据记录。
4. 用 `build-agent-packet --task ...` 生成任务专属语料包与结果 schema。
5. 当前 agent 逐条判断；证据不足时设置 `needs_manual_review`，不得猜测。
6. 用 `build-plan --task ... --results-jsonl ...` 校验结果并生成只读语义计划。
7. 如需写 Zotero，另行生成冻结的 item mutation plan，转入写入策略；当前只读计划不构成写入授权。
   阅读状态 `rs:*` 必须从集中读书卡事实源单独计算，并在同一冻结 action 中显式列出增删；不得由文献内容推断。

## 用法

```powershell
python tools\zotero\zotero_ai_governance.py prepare-corpus --task content-tags
python tools\zotero\zotero_ai_governance.py build-agent-packet --task content-tags
python tools\zotero\zotero_ai_governance.py build-plan --task content-tags --results-jsonl RESULTS.jsonl
```

文献库结构任务把三处 `content-tags` 改为 `library-structure`。普通阅读上下文使用：

```powershell
python tools\zotero\build_zotero_library_context_packet.py --profile content --item-key ITEMKEY --include-text
```

只有治理文献集结构时才使用 `--profile library`。

## 完成条件

- 处理范围与语义证据分离，内容标签包不含项目/collection/current tags。
- 结果只含当前任务允许的字段和命名空间，并保留条目 key、证据说明和哈希。
- 语义计划明确为只读；未读取或修改 `zotero.sqlite`，未移动 PDF，未写入 Zotero。
