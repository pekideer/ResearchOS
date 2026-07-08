# Project State

## 当前阶段

ResearchOS 是 Codex 科研助理运行框架。它维护科研场景、触发规则、质量标准、上下文恢复、语料准备流程和必要工具边界；具体科研成果写入用户指定项目路径。

当前治理重点是功能闭环验证：用脱敏示例或用户本地科研请求检查项目登记、Zotero 父文档、规范化全文、集中读书卡、输出路径和审批边界是否能顺畅工作。

## 稳定入口

| 类型 | 当前入口 |
|---|---|
| 最高规则 | `AGENTS.md` |
| 人工导航 | `README.md` |
| 能力编号 | `CAPABILITIES.md` |
| 语义路由 | `TRIGGERS.md` |
| 执行流程 | `WORKFLOWS.md` |
| 验收标准 | `QUALITY_GATES.md` |
| 工具契约 | `TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/` |
| 当前治理状态 | `docs/governance/researchos-governance-restructure/current-governance-status.md` |
| 本地共享事实源 | `corpus/` |
| 低层机器留存 | `.researchos/outputs/machine/` |
| 外部写入审计留存 | `.researchos/outputs/archive/` |

## 当前边界

- Zotero 默认只读；写入 Zotero 必须走 Web API 审批、试运行、金丝雀测试、分批执行和回滚计划。
- 本地共享事实源默认使用 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`；公开仓库不提交真实父文档和全文。
- 本地集中读书卡主库可使用 `corpus/reading-cards/cards/`，索引位于 `corpus/reading-cards/indexes/`；公开仓库不提交真实读书卡和索引。
- 系统级人读说明和报告进入 `docs/`。
- 具体项目读书卡、综述矩阵、研究报告、论文草稿和审稿回复进入用户指定项目工作区。
- 低层机器留存进入 `.researchos/outputs/machine/`。
- 外部写入审批、执行和回滚证据进入 `.researchos/outputs/archive/`。
- 未归属人工材料进入与 `00_ResearchOS/` 平级的 `0.Inbox/`。

## 当前已稳定能力

- `C01-C12` 能力编号、自然语言触发路由、标准工作流、质量门禁和工具契约层。
- Zotero 父文档与规范化全文读取。
- 集中读书卡命名、YAML 头部、项目索引和期刊等级词典映射。
- Zotero governance 主入口：`tools/zotero_ai_governance.py`。
- 高风险 Zotero 写入工具审批隔离：`tools/high_risk/`。

## 下一步

1. 用脱敏示例或用户本地科研请求验证多项目文献治理链路。
2. 按功能闭环修复入口、规则、语料读取、项目输出和审批边界问题。
3. 对自动审计能力只按当前结构重新设计，不恢复阶段性治理文本。
