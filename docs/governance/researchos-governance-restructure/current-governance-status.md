# ResearchOS 当前治理状态

- 更新时间：2026-07-07
- 维护方式：本文件是 ResearchOS 治理的当前状态入口。
- 当前目标：让 `00_ResearchOS` 稳定承担 Codex 科研助理运行框架。

## 1. 稳定入口

| 类型 | 当前入口 | 作用 |
|---|---|---|
| 最高规则 | `AGENTS.md` | 定义身份定位、安全边界、代码写入边界和任务分层门禁 |
| 人工导航 | `README.md` | 指向权威文档 |
| 能力编号 | `CAPABILITIES.md` | 维护 `C01-C12` 能力边界 |
| 语义路由 | `TRIGGERS.md` | 把自然语言请求映射到能力、skill 和工作流 |
| 执行流程 | `WORKFLOWS.md` | 承载标准步骤和输入输出 |
| 验收标准 | `QUALITY_GATES.md` | 定义证据、来源、方法、输出和治理检查 |
| 工具契约 | `TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/` | 定义工具边界和高风险审批规则 |
| 当前状态 | `PROJECT_STATE.md` | 记录当前阶段和下一步 |
| 共享事实源 | `corpus/` | 保存 Zotero 父文档、规范化全文、集中读书卡和索引 |
| 低层机器留存 | `.researchos/outputs/machine/` | 保存试运行计划、机器 CSV/JSON 和执行记录 |
| 外部写入审计留存 | `.researchos/outputs/archive/` | 保存 Zotero 等外部写入审批、回滚和执行证据 |

## 2. 当前结构

| 模块 | 当前规则 |
|---|---|
| 共享事实源 | `corpus/` 是 Zotero 父文档、规范化全文、集中读书卡和索引入口 |
| 人读文档 | 系统级人读说明和报告进入 `docs/` |
| 项目成果 | 读书卡、综述矩阵、研究报告、论文草稿和审稿回复进入用户指定项目工作区 |
| 低层机器留存 | 机器 CSV/JSON、试运行计划和执行记录进入 `.researchos/outputs/machine/` |
| 外部写入证据 | 审批、执行前后、回滚和审计材料进入 `.researchos/outputs/archive/` |
| 集中读书卡 | `corpus/reading-cards/cards/` 使用 `RC-###_ZoteroKey_短题名.md` 和简短 YAML 头部 |
| 期刊等级 | `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 中的 `journal_rankings` 词典表作为映射来源 |
| Zotero governance | 用户入口为 `tools/zotero_ai_governance.py` |
| 高风险写入 | 通过 `tools/high_risk/` 和 Zotero Web API 审批流程执行 |

## 3. 当前边界

- 普通科研任务优先由 LLM 完成理解、总结、推理、写作、润色和审查。
- 工具用于本地语料获取、批量结构化、PDF/OCR、Zotero 读写和外部系统桥接。
- Zotero 默认只读；写入标签、文献集、笔记或条目必须单独审批。
- ResearchOS 根目录保存规则、能力、流程、模板、契约、策略、运行说明和共享事实源。
- 具体科研成果写入项目工作区或 `0.Inbox/`。

## 4. 下一步建议

下一步优先做真实科研请求闭环验证。

建议顺序：

1. 用三项目文献治理请求验证项目登记、Zotero 父文档、规范化全文和集中读书卡是否能支撑真实汇报。
2. 对验证中暴露的缺口，只修复会影响当前功能闭环的入口、规则或工具。
3. 如需自动审计，按当前 `docs/`、`corpus/`、`.researchos/outputs/` 和 `tools/` 结构设计。
