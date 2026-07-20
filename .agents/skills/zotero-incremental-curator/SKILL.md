---
name: zotero-incremental-curator
description: 编排 Zotero 文献库增量治理：检查条目增减与重键、审计每个父条目下读书卡 note 的 0/1/多条状态、为有全文的新条目生成精读卡、以语义方式识别作者和第一作者一级单位并转换为“中文一级机构，中文国家”，并为新条目准备 collection、tags 与读书卡 note 的受控写入计划。当用户说“检查 Zotero 增减”“处理新增条目”“确保新增文献有精读卡”“治理重复读书卡”“给新条目写 collection/tags”或要求每日完整增量治理时使用。
---

# Zotero 增量治理编排

## 目标

把“发现新增”推进到“语义资产完整且可审计”。本 skill 负责编排现有能力，不在代码中另建语义分类器，也不自动取得 Zotero 写权限。

## 固定边界

- Zotero 读取走父文档或 Local API；不得读取 `zotero.sqlite`，不得改动 PDF 或 annotation。
- 作者对应、一级单位、中文规范名、精读结论、collection 用途和 tags 由当前 agent 语义判断。工具只准备语料、校验身份/格式/版本并应用已确认结果。
- collection membership 与 tags 分开判断。阅读状态 tags 以集中读书卡为事实源，不用 `rs:read/todo` 推断项目用途。
- 真实 Zotero note、collection 或 tags 写入必须各自生成精确计划，经过批准、金丝雀、回读和审计；本 skill 的调用本身不授权写入。
- 同一父条目允许 0 或 1 条 ResearchOS 读书卡 note；多于 1 条立即停止该条目的任何 note 写入，先生成保留/删除计划。

## 执行顺序

### 1. 冻结同步前快照

1. 确认 Zotero Local API 可用并绕过代理。
2. 运行 `tools/reading_cards/zotero_library_pipeline.py snapshot --output <before.json>`，保存顶层条目 `key + version` 快照。
3. 读取上次成功水位线和运行记录；缺失时标记基线待建立，不猜测增减。

### 2. 同步与身份调和

1. 运行 `run --scope new`，默认只更新本机 `M-006` staging 中的父文档副本、全文缓存状态、词典、SQLite 和读书卡；后续语义处理与审计沿用同一 staging。
2. 再次生成快照并用 `snapshot --compare <before.json>` 比较。同步期间出现意外 key/version 变化时停止应用语义结果并重新取证。
3. 以 Zotero item key 为当前身份，以规范化 DOI 为重键证据。发现“删除 key 与活动 key DOI 相同”、同 DOI 多张活动卡或同 key 多张卡时，不新建第二张卡；生成重键/合并计划，保留人工正文最完整的主卡。
4. staging 通过全部检查后仍只标记为“待发布”；共享 `corpus/` 的发布必须由 Corpus Publisher 按独立计划执行并校验发布后快照，本 skill 不把 staging 自动晋升为共享主库。

### 3. 父条目 note 互斥审计

对本次新增、修改、重键和拟发布的每个父条目读取 children，按 `rs:reading-card` tag 或 ResearchOS card marker 统计：

- `0`：记录为 `note_missing`，完成本地精读卡后生成 note 发布 dry-run。
- `1`：核对 note key、card_id、父 item key 和本地映射。
- `>1`：记录所有精确 note key、version、hash 和备份；明确 keeper 与删除候选。未经单独批准不删除。

### 4. 作者单位语义处理

1. 用 `semantic-packet` 准备首页 1–3 页证据；封面页无作者区时继续后续页。
2. 当前 agent 语义识别第一作者、作者标号、对应单位标号、第一作者的第一个一级机构与国家。
3. `first_author_affiliation_raw` 保存原文证据；显示值必须转换为 `中文一级机构，中文国家`。不得保留英文一级机构作为最终显示值，不得把院系/实验室替代一级机构。
4. 结果先 `semantic-apply` 预检，再以 `--write-local` 应用。无法确认时使用明确的 `semantic_needs_check`、`semantic_not_found` 或 `source_unavailable`，不得伪造中文名。

### 5. 精读卡完成门禁

1. 有规范化全文时，调用 `paper-deep-reading`，基于全文完成读书卡 1–5、7 章；状态写为 `generation_mode: llm_fulltext_deep_reading` 和 `fulltext_status: full_text_reviewed`。
2. 只有摘要或元数据时不得冒充精读。记录来源限制和补全文任务，状态保持未完成。
3. 更新既有卡时保留人工正文、annotation 受控区、第 6 章项目关联和人工元数据。
4. 对本次范围运行 `audit --strict --curation-strict --item-key ...`；任何身份、中文单位、精读状态或 note 互斥失败都不得报告完成。

### 6. collection、tags 与 note 计划

1. 当前 agent 根据父文档、精读卡、现有文献集语义和明确项目上下文逐条判断 collection；不明确则进入 triage/待确认，不强配项目。
2. 分别给出 collection membership 与 tags。阅读状态使用 `rs:read/deep-read`、`rs:read/initial-card` 或 `rs:read/todo`，且互斥。
3. 使用 `project-collection-overlay` 生成 collection dry-run；其他 tags/metadata 使用既有受控写入计划。不得从关键词或脚本评分直接生成可发布归属。
4. 使用 `zotero-reading-card-annotation-sync` 为唯一主卡生成 note live dry-run。若父条目已有多条卡，发布器必须阻断。
5. 汇总为冻结计划，逐项列出 item key、目标 collection、增删 tags、note action、版本前置条件、回滚信息和审批边界。

## 完成报告

至少报告：新增/修改/减少/重键数量；卡片 0/1/多条数量；全文可用但未精读数量；中文单位格式失败数量；collection 与 tags 计划数量；共享 corpus 已发布/待发布状态；已写入、待审批、阻断和需要人工核查的精确条目。不要把“已生成占位卡”报告为“已完成精读”，也不要把 staging 完成报告为共享主库已更新。
