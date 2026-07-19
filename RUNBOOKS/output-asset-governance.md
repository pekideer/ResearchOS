# Output Asset Governance

本操作手册规定 ResearchOS 根级 `docs/`、`corpus/`、低层运行留存区和未归属材料入口 `0.Inbox/` 的边界。目标是让人读说明、共享事实源、机器运行痕迹和未归属材料各自归位。

## 0. 未归属入口

`0.Inbox/` 是 `00_ResearchOS/` 的平级兄弟目录，不在 `00_ResearchOS/` 内部：

```text
0.Inbox/
00_ResearchOS/
具体课题目录/
```

`0.Inbox/` 用于暂存尚未明确课题归属、但需要人工查看和后续归档的材料。推荐结构：

```text
0.Inbox/
  README.md
  01-unassigned-literature/
  02-unassigned-ideas/
  03-unassigned-materials/
  04-to-triage/
  .internal/
```

规则：

- 未归属但需要人工查看的材料放入 `0.Inbox/`。
- 未归属的机器中间产物放入 `0.Inbox/.internal/`。
- 明确归属后，再迁移到具体课题目录的 `01-05` 编号结构。
- 未归属人工材料进入平级 `0.Inbox/`；人读说明进入 `docs/`，共享事实源进入 `corpus/`。

## 1. 根级资产结构

```text
docs/
  capabilities/
  governance/
  guides/
  modes/
  reports/
corpus/
  zotero/
  fulltext/
  reading-cards/
  indexes/
.researchos/outputs/
  archive/
  machine/   # 机器运行产物
```

`.researchos/outputs/machine/` 和 `.researchos/outputs/archive/` 是本地工具的兼容运行与详细证据暂存区，不跨端，也不能保存唯一正式证据。日常任务的人读结果进入 `docs/`、项目工作区或平级 `0.Inbox/`；项目专属持久状态、审批和精简审计进入项目 `.research/`。

## 2. 分类规则

- `docs/`：给人阅读、复核、决策的说明、指南、治理过程、能力映射和系统级报告。
- `corpus/`：给项目工作区和 LLM 使用的共享事实源，包括 SQLite、规范化全文、集中读书卡和索引。
- `.researchos/outputs/archive/`：本地外部写入详细证据暂存，任务收束前受保护，晋升必要摘要后可按策略清理。
- `.researchos/outputs/machine/`：本地机器运行产物、试运行计划和执行记录，可再生成内容不进入项目持久状态。
- 项目 `.research/`：manifest、状态、交接、决策、已批准计划和数据最小化后的最终审计。

项目级课题目录继续使用既有编号结构：

- `01-课题入口/`：课题入口、索引、项目说明和指针页。
- `02-证据材料/`：来源记录、证据地图、材料索引和证据链。
- `03-文献矩阵/`：人工矩阵、报告和 PRISMA 主状态。
- `03-文献矩阵/.internal/`：机器 CSV/JSON/cache/report。
- `.internal/zotero-collection-overlay/`：具体项目的 Zotero 文献集覆盖层试运行计划和执行记录。
- `04-决策记录/`：点子判断、路线决策、候选分诊和研究进展。
- `05-论文稿件/`：论文正文、稿件片段和投稿材料。
- `06-报告材料/`：阶段性报告、汇报和对外材料。
- `07-审稿回复/`：审稿意见、回复表和修改记录。
- `08-写作材料/`：写作计划、提纲、草稿素材和导师反馈。
- `10-批注/`：人工批注、处理记录和批注归档。
- `.research/fulltext_cache/`：旧项目兼容缓存，目标架构中应迁入本地 Agent Core 的 `.researchos/cache/`；完成盘点和校验前不删除。

## 3. 编号规则

- 系统级人读文档不使用 `H-###` 目录，直接进入 `docs/` 下的语义目录。
- 机器运行留存目录可使用 `M-###-name`，但不能作为人工入口。
- 外部写入审计留存目录可使用 `A-###-name`，但不能保存 ResearchOS 内部迁移备份。
- 课题级人工参阅编号继续使用 `RC-###`，提醒编号使用 `TODO-###`，文献矩阵使用 `LM-###`。

## 4. 多终端规则

- Python venv、Python package 缓存、vcpkg、Tesseract 源码和 Tesseract runtime 只放本机本地目录，例如 `%LOCALAPPDATA%\ResearchOS\...`。
- SQLite、规范化全文、集中读书卡和索引进入同步盘 `corpus/`。
- `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/` 是后续 Zotero 文献管理、阅读、综述、AI 分类和治理任务的共享事实源。
- 同步盘 SQLite 采用单写多读：同一时间只允许一个终端执行写入型 `sync` 或 `watch`。
- `zotero_library_index.py` 使用 `zotero_library.sqlite.writer.lock` 做 advisory writer lock；只有确认无其他终端写入时才可使用 `--force-lock`。
- Agent Core、共享 corpus、具体项目和 Zotero 分别授权写入；Framework Maintainer、Corpus Publisher、Project Writer、Zotero Writer 角色互不自动继承。
- 项目同一时刻只允许一个 Project Writer；写入权通过项目 `.research/handoff.yml` 显式交接。

## 5. 当前默认映射

| 功能 | 面向 | 默认路径 |
|---|---|---|
| Zotero SQLite 索引 | 机器 | `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` |
| Zotero 原始字段 JSON | 机器留存 | `.researchos/outputs/machine/M-002-library-governance/zotero_items_raw.json` |
| Zotero 字段清单 CSV | 机器留存 | `.researchos/outputs/machine/M-002-library-governance/zotero_field_inventory.csv` |
| Zotero 字段用途报告 | 人工 | `docs/reports/library-governance/zotero_field_inventory.md` |
| Zotero 治理矩阵 CSV/JSON | 机器留存 | `.researchos/outputs/machine/M-002-library-governance/` |
| Zotero 主题相似对 CSV | 机器留存 | `.researchos/outputs/machine/M-002-library-governance/zotero_similar_pairs.csv` |
| Zotero 主题聚类报告 | 人工 | `docs/reports/library-governance/zotero_topic_clusters.md` |
| Zotero 治理报告 | 人工 | `docs/reports/library-governance/zotero_governance_report.md` |
| Zotero 治理 plan | 机器留存 | `.researchos/outputs/machine/M-002-library-governance/zotero_governance_plan.json` |
| Zotero PDF 全文文本缓存 | 机器 | `corpus/fulltext/zotero-library/ITEMKEY__ATTACHMENTKEY.txt` |
| Zotero PDF AI 规范化文本缓存 | 机器 | `corpus/fulltext/zotero-library-normalized/ITEMKEY__ATTACHMENTKEY.txt` |
| Zotero 父文档上下文包 | 人工/机器留存 | `docs/reports/library-governance/zotero-library-context-packet.md` 与 `.researchos/outputs/machine/M-002-library-governance/zotero-library-context-packet.jsonl` |
| 临时 PDF 文本抽取 | 机器 | 项目 `.research/fulltext_cache/`；无项目时进入 `corpus/fulltext/` |
| Zotero 新条目监控报告 | 人工 | `docs/reports/zotero-new-item-monitor/new-items-report.md` |
| Zotero 新条目监控状态和试运行计划 | 机器留存 | `.researchos/outputs/machine/M-004-zotero-new-item-monitor/` |
| Zotero 全库/增量摄取流水线日志 | 机器留存 | `.researchos/outputs/machine/M-006-zotero-ingestion-pipeline/` |
| 期刊与单位词典、集中初筛读书卡 | 共享事实源 | `corpus/zotero/M-001-zotero-library/zotero_library.sqlite`、`corpus/reading-cards/indexes/` 与 `corpus/reading-cards/cards/` |
| 项目级 Zotero 文献集覆盖层报告 | 人工 | 具体项目工作区内，优先使用 `03-文献矩阵/project-collection-plan.md` |
| 项目级 Zotero 文献集覆盖层计划和执行记录 | 机器留存 | 具体项目工作区内的 `.internal/zotero-collection-overlay/` |
| ResearchOS 当前治理状态 | 人工 | `docs/governance/researchos-governance-restructure/current-governance-status.md` |

## 6. 维护规则

- 新增根级产物前，先判断面向人、共享事实源、机器留存还是外部写入审计。
- 面向人的系统级文档进入 `docs/`；具体项目文档进入项目目录；共享事实源进入 `corpus/`；外部写入详细证据先进入本地 `.researchos/`，项目专属长期摘要晋升到项目 `.research/`。
- 具体项目名称、项目级分类计划和项目级 Zotero 覆盖层不得写入 ResearchOS 通用机器目录。
- `.researchos/outputs/machine/M-002-library-governance/` 只作为 Zotero 文献库治理的运行时机器目录，不是事实源；旧批处理请求、CSV/JSON 中间产物和写入试运行计划没有当前任务引用时应删除，必要时从 `corpus/` 和 `docs/reports/library-governance/` 再生成。
- 本地 `.researchos/` 清理前必须确认不存在唯一项目状态、唯一正式审计、未完成外部写入或未关闭回滚事项。
- 未归属材料放入与 `00_ResearchOS/` 平级的 `0.Inbox/`。
- 机器 CSV/JSON 中可保留 raw Zotero key；人工 Markdown/HTML/YAML 中必须使用可点击 Zotero 链接。
- PDF 文件、真实 API key、Python 环境、本机构建产物和人工主文档分别进入对应安全位置或项目工作区。
- ResearchOS 自身治理以直接形成稳定入口为目标。
- 读书卡主库固定为 `corpus/reading-cards/cards/`；格式统一直接在主库完成。
