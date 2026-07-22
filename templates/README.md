# ResearchOS Templates

`templates/` 只保存可复用输出结构，不保存具体项目成果。模板按能力主题归组；目录表达
主题，文件名与实际项目输出名保持一致。

## 模板索引

| 目录 | 能力与调用方 | 模板 | 实际输出 |
|---|---|---|---|
| `annotations/` | C03 `human-annotation-inbox` | `inbox-entry.md` | `10-批注/inbox.md` 条目 |
| `ideas/` | C04 `idea-to-research-potential` | `idea-card.md`、`research-brief.md`、`source-log.md`、`live-direction.md` | `IDEA-..._*.md` |
| `ideas/` | C04/C05/C08 外部候选阅读 | `external-reading-candidates.md/.csv` | `*-external-reading-candidates.*` |
| `literature/` | C06 单篇精读 | `paper-reading-card.md`、`first-page-bibliographic-extraction-prompt.md` | 集中读书卡及题录抽取 |
| `literature/` | C07 文献矩阵 | `literature-review-matrix.csv`、`reading-summary-table.md/.html` | 项目文献矩阵和阅读总表 |
| `prisma/` | C07 PRISMA | `records.csv`、`search-log.csv`、`zotero-tag-map.yml` | `prisma-records.csv` 等项目状态 |
| `gap-to-topic/` | C08 `gap-to-topic` | `topic_dossier.md`、`gaps.yml` | 同名选题判断资产 |
| `writing/` | C09/C10 写作审查 | `manuscript-outline.md`、`claim-evidence-audit-table.md`、`reviewer-response-table.md` | 稿件提纲、审计表和回复表 |
| `paper-memory/` | C09 `paper-memory-builder` | `manuscript_map.yml`、`claims.yml`、`figures.yml`、`evidence_artifacts.yml`、`revision_history.yml` | `.paper/` 同名文件 |
| `project-state/` | C12 项目状态 | `project-manifest.yml`、`run-state.*`、`run-record.json`、`data-dictionary.yml`、`experiment-matrix.yml`、`open-questions.md` | 项目 `.research/` 状态资产 |

## 维护规则

- 每个模板只有一个主维护位置；skill、工作流和工具引用模板，不维护第二套完整结构。
- 模板文件名应与实际落地文件名一致；项目前缀和编号由调用方添加。
- 新增模板必须登记能力编号、调用方、实际输出和质量检查。
- 删除模板前必须确认全仓无直接引用和隐式输出契约。
- Zotero 治理矩阵和报告由 `tools/zotero/zotero_ai_governance.py` 动态生成，不保留易漂移的静态模板。
- 代码闭环审计以 `WORKFLOWS.md` 工作流 0C 和 `QUALITY_GATES.md` 为唯一规则源，不维护重复 Prompt 模板。
