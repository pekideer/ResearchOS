# ResearchOS 规则、输出边界与审计契约

## 1. 适用工具

- `researchos_outputs.py`

## 2. 工具目的

本专题工具用于治理 ResearchOS 自身文档体系、输出资产、命名规则、治理仪表盘和规则审计。治理目标是保证 `docs/`、`corpus/`、`.researchos/outputs/machine/`、`.researchos/outputs/archive/`、项目工作区和高风险工具边界清楚。

## 3. 允许行为

- 只读审计 ResearchOS 文档、规则和输出边界。
- 检查 `docs/`、`corpus/`、`.researchos/outputs/machine/`、`.researchos/outputs/archive/` 和活跃工具边界。
- 更新系统级人读说明、治理状态、命名规则和工具契约。
- 在用户批准后修复影响功能闭环的路径常量或脚本入口。
- 为 Zotero 读书卡标注闭环维护 `M-005-reading-card-annotation-sync` 机器预览和 `A-003-reading-card-note-publish` 写入审计常量。

## 4. 禁止行为

- 不把 `.researchos/outputs/machine/` 当作人读入口。
- 不把 ResearchOS 根目录当作具体科研项目成果库。
- 不无审批移动或删除治理资产。
- 不把审计结果直接视为修复完成。
- 不修改代码来适配文档结构，除非用户另行批准。

## 5. 自动审计边界

自动审计如需启用，应以当前 `docs/`、`corpus/`、`tools/zotero/write/`、活跃工具清单和根级权威文档为基准，并先说明：

1. 修改目的。
2. 当前检查逻辑。
3. 最小代码改动。
4. 不改代码时的影响。

经用户同意后再新建或修改代码。

## 6. 验收标准

- 根目录文档职责清楚。
- 输出资产、人读文档、共享事实源、机器留存和审计留存边界闭合。
- 命名规则同步到入口文档、runbook 和必要契约。
- `docs/` 是系统级人读入口，`corpus/` 是共享事实源入口。
