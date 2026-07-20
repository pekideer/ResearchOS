# 读书卡、PRISMA 与期刊元数据契约

## 1. 适用工具

- `configure_easyscholar_api.ps1`
- `sync_journal_rankings.py`
- `build_affiliation_semantic_packet.py`
- `build_prisma_status_outputs.py`
- `sync_reading_summary_table.py`
- `card_common.py`
- `sync_zotero_metadata_to_cards.py`
- `sync_zotero_annotations_to_cards.py`
- `zotero_library_pipeline.py`

## 2. 工具目的

本专题工具用于维护集中读书卡主库、项目读书卡索引、PRISMA 检索筛选状态、期刊等级、第一作者机构和 Zotero 可读引用链接。

## 3. 允许行为

- 读取 ResearchOS 父文档和集中读书卡。
- 生成或同步读书卡汇总表。
- 维护 PRISMA 状态输出。
- 从批准配置读取 EasyScholar 信息并同步期刊等级。
- 生成可读引用标签和可点击 Zotero 链接。
- 从父文档 annotation 镜像生成读书卡受控人工标注区。
- 只读冻结并比较 Zotero Local API 顶层条目的 `key + version` 快照。
- 在本机 staging 中运行增量同步、语义结果校验和严格治理审计。

## 4. 禁止行为

- 期刊等级读取以 SQLite 期刊等级词典为准；词典缺失且允许联网时才通过 EasyScholar API 补足。
- 不把 Zotero 条目 key 作为人读正文默认显示标签。
- 不删除读书卡正文，替换前必须先归档原正文。
- 不写入 Zotero。
- 不编造期刊等级、作者机构或 PRISMA 状态。
- 默认 staging 不得冒充已经发布的共享父文档或集中读书卡主库。

## 5. 读书卡规则

- 集中主卡放入 `corpus/reading-cards/cards/`。
- 项目和点子只保留索引或指针页。
- 集中主卡开头保留简短 YAML 头部。
- Zotero 详细题录、期刊等级和 ResearchOS 同步元数据放入文末“元数据”部分。
- 正文引用默认使用 `[第一作者姓(年份)](zotero://select/library/items/KEY)`。

## 6. 验收标准

- 人读 Markdown 不直接暴露机器字段。
- 文献引用可读、可点击、可追溯。
- 期刊等级来源明确。
- PRISMA 状态字段可解释。
- 项目索引和集中主卡关系清楚。

## 7. 工具入口要求

- 读书卡汇总表使用 `sync_reading_summary_table.py`。
- 期刊等级同步使用 `sync_journal_rankings.py`。
- 第一作者单位证据准备使用 `build_affiliation_semantic_packet.py` 或 `zotero_library_pipeline.py semantic-packet`；代码只截取证据，不再用独立正则工具把单位候选写入读书卡。
- 全库、新增或指定条目的首页证据准备优先使用 `zotero_library_pipeline.py semantic-packet`；语义结果必须先经 `semantic-apply` 默认预检，再用 `--write-local` 写入本地 SQLite 和集中读书卡。
- `zotero_library_pipeline.py run` 默认写入本机 `M-006` staging；同一 staging 存在时，`semantic-packet`、`semantic-apply` 和 `audit` 自动沿用它。共享 `corpus/` 发布属于 Corpus Publisher 的独立步骤，未发布时必须报告 `corpus_publication_required`。
- `snapshot` 和 `audit --curation-strict` 只读访问 Local API；后者同时检查规范化 DOI、卡片身份、全文精读状态、中文单位显示和父条目 ResearchOS note 数量。
- `heuristic_candidate`、`existing_card_candidate`、旧 `not_found` 和 `not_processed` 不得作为确定单位显示，也不得通过 Zotero 读书卡发布预检。
