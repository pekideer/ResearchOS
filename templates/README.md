# ResearchOS Templates

`templates/` 保存 ResearchOS 输出模板和提示词模板。模板本身不保存具体项目成果。

## 按能力归属

| 能力 | 模板 |
|---|---|
| C03 人工批注 | `human-annotation-inbox-entry.md` |
| C04 点子捕获 | `idea-card.md`、`idea-research-brief.md`、`idea-source-log.md`、`idea-live-direction.md`、`external-reading-candidates.*` |
| C06 论文精读 | `paper-reading-card.md`、`reading-card-first-page-bibliographic-extraction-prompt.md` |
| C07 文献矩阵与 PRISMA | `literature-review-matrix.csv`、`reading-summary-table.*`、`prisma-*` |
| C08 缺口到选题 | `gap-to-topic-topic-dossier.md`、`gap-to-topic-gaps.yml`、`topic-directions.csv` |
| C09 论文写作与证据 | `paper-memory-*`、`claim-evidence-audit-table.md`、`manuscript-outline.md` |
| C10 审稿回复 | `reviewer-response-table.md` |
| C11 Zotero 治理 | `zotero-library-matrix.csv`、`zotero-governance-report.md` 为人工参考模板；当前工具默认由代码生成报告和矩阵。 |
| C12 项目状态和审计 | `research-project-manifest.yml`、`research-run-state.json`、`research-run-record.json`、其他 `research-*`、`researchos-code-closure-audit-prompt.md` |

## 维护规则

- 被 `WORKFLOWS.md`、skill 或工具引用的模板暂不移动。
- 未引用或过期模板先审计引用关系，再决定是否删除。
- 新增模板必须说明能力编号、使用场景、输出位置和是否可分发。
- C11 Zotero 治理工具以 `tools/zotero/zotero_ai_governance.py` 为主入口；静态模板不得替代工具契约或写入审批流程。
- `research-run-record.json` 是项目 `.research/run-log.jsonl` 的单条记录模板，只保存必要任务元数据，不保存完整对话或正文。
