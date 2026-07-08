# 项目工作区能力-文件映射

本文档固化 ResearchOS 在用户指定项目工作区下能实现的能力、是否会创建基础功能文件，以及这些文件对能力实现的作用。

## 基础目录

初始化项目工作区时，ResearchOS 可创建：

```text
项目目录/
  annotations/
    inbox.md
    review-log.md
    processed/
    .internal/
  01-reading-cards/
  02-literature-matrix/
    prisma/
    .internal/
  03-manuscript/
  04-reviewer-response/
  .research/
```

`.research/` 用于上下文恢复和机器索引，不是人读成果主入口。

## 能力映射

| 能力 | 基础文件或目录 | 是否默认创建 | 作用 |
|---|---|---:|---|
| 项目工作区初始化 | `annotations/`、`01-reading-cards/`、`02-literature-matrix/`、`03-manuscript/`、`04-reviewer-response/` | 是 | 固定科研成果落点，避免材料混放 |
| 项目上下文恢复 | `.research/project_manifest.yml`、`.research/run_state.json` | 可选 | 记录项目方向、当前状态、开放问题和跨会话恢复信息 |
| 人工批注收件箱 | `annotations/inbox.md`、`annotations/review-log.md`、`annotations/processed/` | 是 | 保存用户阅读意见、疑问和修改建议，处理后可追溯 |
| 单篇论文精读 | `01-reading-cards/*.md` | 按需 | 保存读书卡、事实/推断/建议、来源和 Zotero 链接 |
| 阅读总表 | `02-literature-matrix/LM-004_reading-summary-table.html`、`.internal/*.csv` | 按需 | 跨文献浏览、评分、PRISMA 状态和写作素材管理 |
| 综述矩阵 | `02-literature-matrix/literature-review-matrix.csv` | 按需 | 比较研究对象、方法、指标、结论和缺口 |
| PRISMA 筛选 | `02-literature-matrix/prisma/prisma-records.csv`、`prisma-search-log.csv` | 按需 | 保存检索、筛选、纳入/排除和阅读状态 |
| 缺口到选题 | `topic_dossier.md`、`gaps.yml` | 按需 | 判断研究空间、贡献可能性和可完成性 |
| 论文写作与记忆 | `03-manuscript/`、`.paper/*.yml` | 按需 | 管理论文论断、图表、证据和修改历史 |
| 审稿回复 | `04-reviewer-response/` | 按需 | 拆解审稿意见，生成修改策略和逐条回复 |
| 项目局部语料缓存 | `.research/fulltext_cache/` | 按需 | 保存由 `corpus/` 或父文档派生的文本缓存，不保存 PDF |

## 依赖关系

```text
AGENTS.md
  -> CAPABILITIES.md
  -> TRIGGERS.md
  -> WORKFLOWS.md
  -> docs/capabilities/project-workspace-capability-map.md
  -> templates/
  -> corpus/
  -> 用户指定项目工作区
```

工具只负责准备语料、同步状态或生成机器中间产物；科研判断、写作和审查仍由 Codex 基于语料完成。
