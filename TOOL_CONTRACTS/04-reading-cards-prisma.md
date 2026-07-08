# 读书卡、PRISMA 与期刊元数据契约

## 1. 适用工具

- `configure_easyscholar_api.ps1`
- `sync_journal_rankings.py`
- `sync_first_author_affiliations.py`
- `build_affiliation_semantic_packet.py`
- `build_prisma_status_outputs.py`
- `sync_reading_summary_table.py`
- `journal_ranking_format.py`
- `sync_zotero_metadata_to_cards.py`
- `researchos_card_metadata.py`

## 2. 工具目的

本专题工具用于维护集中读书卡主库、项目读书卡索引、PRISMA 检索筛选状态、期刊等级、第一作者机构和 Zotero 可读引用链接。

## 3. 允许行为

- 读取 ResearchOS 父文档和集中读书卡。
- 生成或同步读书卡汇总表。
- 维护 PRISMA 状态输出。
- 从批准配置读取 EasyScholar 信息并同步期刊等级。
- 生成可读引用标签和可点击 Zotero 链接。

## 4. 禁止行为

- 期刊等级读取以 SQLite 期刊等级词典为准；词典缺失且允许联网时才通过 EasyScholar API 补足。
- 不把 Zotero 条目 key 作为人读正文默认显示标签。
- 不删除读书卡正文，替换前必须先归档原正文。
- 不写入 Zotero。
- 不编造期刊等级、作者机构或 PRISMA 状态。

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
- 第一作者单位证据准备使用 `build_affiliation_semantic_packet.py`。
