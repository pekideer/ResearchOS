---
name: human-annotation-inbox
description: 读取和处理用户在项目/idea 本地 `10-批注/inbox.md` 或全局 `.researchos/human-annotation-inbox/inbox.md` 中记录的阅读想法、意见、疑问和修改建议；当用户说“处理我的批注”“读取我的阅读意见”“把我的标记映射到文档”“检查这些想法并更新对应报告/读书卡/简报/实时方向文档/草稿”“清理批注收件箱”时使用。用于把人工条目映射到目标文档位置，检查其证据边界和可采纳性，输出建议、行动计划，并在允许时更新目标文档和归档已处理条目。
---

## 目标

把用户随手记录的阅读批注变成可追踪的文档更新线索。该 skill 处理的是“人工意见 -> 文档位置 -> 检查判断 -> 建议/更新”的闭环，不把用户想法直接改写成事实结论。

## 存储策略

- 项目/idea 本地收件箱优先：`<project-or-idea-root>/10-批注/inbox.md`
- 本地执行记录：`<project-or-idea-root>/10-批注/review-log.md`
- 本地已处理归档：`<project-or-idea-root>/10-批注/processed/`
- 全局未归属入口：`.researchos/human-annotation-inbox/inbox.md`
- 全局执行记录：`.researchos/human-annotation-inbox/review-log.md`
- 全局已处理归档：`.researchos/human-annotation-inbox/processed/`

默认不要让所有批注长期堆在一个全局文件里。若用户正在阅读某个 IDEA、课题项目或文档包内材料，优先使用该根目录下的 `10-批注/inbox.md`；只有跨项目、未确定归属或用户明确要求集中记录时，才使用全局 `.researchos/human-annotation-inbox/inbox.md`。

活跃 `inbox.md` 只保留 `new`、`needs-confirmation` 或近期未决条目。已处理条目归档到 `processed/YYYY-MM-processed.md` 或用户指定的归档文件，`review-log.md` 保留处理索引。

## 收件箱条目格式

每条批注使用一个二级标题。推荐格式：

```markdown
## ANNO-YYYYMMDD-001 简短标题

- status: new
- created_at: YYYY-MM-DD
- target_document: path/to/document.md
- target_anchor: 标题 / 引文 / 表格名 / 行号 / 页码 / Zotero item / 不确定
- target_type: report / reading-card / brief / live-direction / matrix / manuscript / other
- request_type: question / correction / suggestion / TODO / evidence-check / update
- priority: high / normal / low
- archive_after_processing: yes / no

### 我的想法或意见

写你的原始想法。可以很粗糙，不需要整理成正式表述。

### 希望你做什么

例如：帮我判断是否成立；映射到文档位置；改写这段；加入下一步计划；标记需要补证据。

### 证据或上下文

可选。写你看到的句子、页码、截图说明、文献名、Zotero key 或“需要我后续补”。
```

允许自由写，但处理时优先读取上述字段。缺 `target_document` 或 `target_anchor` 时，先尝试根据题名、关键词和上下文匹配；仍不确定时输出候选位置，不直接改文档。项目本地 inbox 中的 `target_document` 默认相对项目/idea 根目录解析。

## 工作流

1. 选择收件箱：
   - 若用户给出 IDEA、项目目录或目标文档，优先读取其最近上级项目/idea 根目录的 `10-批注/inbox.md`。
   - 若用户只说“处理我的批注收件箱”，先检查当前活跃 IDEA/项目的本地 inbox；再检查全局 `.researchos/human-annotation-inbox/inbox.md`。
   - 若本地 `10-批注/inbox.md` 不存在且目标根目录明确，创建 `10-批注/inbox.md`、`10-批注/review-log.md` 和 `10-批注/processed/`。
2. 读取选中 `inbox.md` 中 `status: new`、`status: needs-confirmation` 或用户指定的条目。
3. 解析每条条目的目标文档、锚点、请求类型和用户原始意见；保留原文，不擅自替换用户表述。
4. 打开目标文档，按优先级定位：
   - 精确路径 + 标题/行号/表格名。
   - 精确引用片段或关键词。
   - Zotero 条目 key、文献题名、IDEA ID 或报告编号。
   - 若多个位置都可能匹配，列出候选位置并标记 `needs-confirmation`。
5. 检查用户意见：
   - 区分事实、推断、建议、假设和需要核查。
   - 检查是否缺证据、过度声称、与文档已有内容冲突、引用位置不合适或更新范围过大。
   - 对涉及文献、数据、图表、审稿意见或实验结果的内容，遵守 ResearchOS 科研诚信规则，不编造来源。
6. 输出处理结果：
   - `mapped_location`：目标文档位置和定位依据。
   - `assessment`：可采纳、需改写、需补证据、需人工确认或不建议采纳。
   - `suggested_update`：建议加入/替换/移动/删除的文字或 TODO。
   - `risk_notes`：证据边界、可能冲突和不确定项。
7. 若用户明确要求“更新/应用”，且目标是人工文档，按最小改动更新目标文档；否则只生成建议和 行动计划。
8. 更新同目录 `review-log.md`：记录条目 ID、处理日期、目标文档、状态、行动、归档文件和未决问题。
9. 清理活跃 inbox：
   - `needs-confirmation` 条目保留在 `inbox.md`。
   - `mapped`、`suggested`、`applied`、`rejected` 或 `archived` 条目默认移动到 `processed/YYYY-MM-processed.md`，除非 `archive_after_processing: no`。
   - 归档时保留原始意见正文、处理摘要和目标文档位置；不要只删除。

## 更新规则

- 默认只改人工文档：reports、reading cards、研究简报、实时方向文档、manuscript、review tables 等。
- 不直接改 `.internal/`、CSV/JSON、Zotero 父文档、规范化文本、数据库导出或机器 registry；这些文件只输出更新建议。
- 对读书卡和报告的更新应尽量追加 `## 人工批注处理` 或局部 TODO，不把未核查意见混入正文结论。
- 如果用户意见涉及已发表文献结论，未核查原文前只能写“用户提出的待核查意见”或“需要核查”。
- 如果目标文档路径不清楚，先输出候选映射，不执行更新。
- 清理 inbox 只能移动已处理条目到 `processed/`，不得丢弃原始意见；用户明确要求删除时才删除。
- 写回人工文档时必须遵守 `POLICIES/OUTPUT_LANGUAGE_POLICY.md`：普通概念用中文表达；英文只保留文献题名、DOI/URL、数据库/软件/API 名、路径/命令/字段名、skill 名、文献专门术语和领域共同认可缩写。必要术语首次出现尽量写成“中文译名（英文原文）”。

## 输出

- 面向用户的处理摘要：哪些条目已映射、哪些需要确认、哪些建议更新。
- `review-log.md` 的追加记录。
- 可选：`.researchos/human-annotation-inbox/annotation-action-plan.csv`，字段包括 `annotation_id,target_document,mapped_anchor,status,recommended_action,updated_file,archive_file`。
- 如执行了文档更新，说明被更新的文件和更新位置。
- 如执行了清理，说明归档文件和 inbox 剩余未决条目数。

## 完成条件

- 已读取指定批注或 `inbox.md` 中所有 `status: new` 条目。
- 每条批注都有映射结果或明确说明无法唯一映射。
- 每条建议都区分事实、推断、建议、假设和需要核查。
- 已输出检查意见、更新建议和下一步动作。
- 若执行更新，目标文档已最小改动更新，且 `review-log.md` 已记录。
