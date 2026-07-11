# Project State

## 当前阶段

ResearchOS 是 Codex 科研助理运行框架。它维护科研场景、触发规则、质量标准、上下文恢复、语料准备流程和必要工具边界；具体科研成果写入用户指定项目路径。

当前治理重点是行为闭环验证：在 skill 边界、上下文恢复链、根规则渐进读取、最小运行记录和首次运行入口已经收敛后，用真实科研请求验证稳定性。

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
- Zotero governance 主入口：`tools/zotero/zotero_ai_governance.py`。
- 高风险 Zotero 写入工具审批隔离：`tools/zotero/write/`。
- 20 个独立 skill；独立汇报导航能力已并入项目上下文恢复，点子、检索、深度报告、立项判断和研究问题边界已分开。
- 唯一上下文恢复链：`active_project.yml` 定位、`project_manifest.yml` 稳定事实、`run_state.json` 当前快照、`run-log.jsonl` 最小历史。
- 精简根规则和紧凑路由：`AGENTS.md` 只保留最高约束，`TRIGGERS.md` 使用单表路由，专题边界按需读取。
- 首次运行先做只读就绪检查；普通科研任务不以 Python、OCR 或 Zotero 配置为前置条件。

## 下一步

1. 为 `C01-C12` 建立真实请求行为评测，重点检查误路由、上下文冲突和日志噪声。
2. 用新建项目和既有项目各验证一次恢复链与 workspace 审计。
3. 只修复行为评测实际暴露的问题，暂缓新增 skill 和独立运行时。
