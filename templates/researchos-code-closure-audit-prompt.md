# ResearchOS 代码审计与功能闭环审计 Prompt

请对 ResearchOS 做一次“代码问题 + 功能闭环”只读审计。不要修改文件。

## 只读边界

- 不修改代码、配置、文档或测试。
- 不运行会改写文件的 formatter、迁移、代码生成或修复命令。
- 可以运行只读搜索、静态检查和不会改写源码的测试。
- 发现问题后只输出证据和建议；如果需要修复，必须由用户另行明确要求。

## 必读材料

先读取并说明读取范围：

- `AGENTS.md`
- `CAPABILITIES.md`
- `TRIGGERS.md`
- `WORKFLOWS.md`
- `QUALITY_GATES.md`
- `TOOL_CONTRACTS.md`
- `README.md`
- `PROJECT_STATE.md`
- `EVALS.md`
- `tools/`
- `.agents/skills/`
- `tests/` 和测试配置

## 审计维度

按功能链路检查：

`用户目标 -> 入口 -> 参数或配置 -> 核心逻辑 -> 数据读写 -> 输出结果 -> 失败处理 -> 测试证据 -> 文档说明`

重点识别：

- 功能正确性
- 功能闭环缺失
- 错误处理不足
- 数据一致性问题
- 安全与权限风险
- 性能问题
- 幂等和重复执行风险
- 重复实现
- 硬编码路径或硬编码业务规则
- 测试缺口
- 文档、工具契约和实现不一致

## 汇报格式

请按以下结构输出：

一、总体结论

- 当前项目是否具备可运行、可维护、可验收的基础闭环。
- 最大风险是什么。
- 建议先处理哪三类问题。

二、功能闭环表

| 功能 | 入口 | 核心逻辑 | 输出 | 失败处理 | 测试证据 | 文档证据 | 闭环状态 | 风险 | 建议 |
|---|---|---|---|---|---|---|---|---|---|

三、代码问题清单

| 等级 | 类型 | 文件/行号 | 证据 | 影响 | 建议 |
|---|---|---|---|---|---|

四、测试与验收缺口

- 缺哪些单元测试。
- 缺哪些集成测试。
- 缺哪些端到端验收。
- 哪些命令可以作为回归检查。

五、治理计划

- P0：立即处理。
- P1：短期补齐。
- P2：中期重构。
- 暂不处理但记录风险。

## 验收命令建议

```powershell
rg -n "检查代码问题|检查功能闭环|代码审计与功能闭环审计|工具契约和实现是否一致" AGENTS.md TRIGGERS.md CAPABILITIES.md WORKFLOWS.md QUALITY_GATES.md
rg -n "docs/governance/24|docs/governance/25|H-006|M-006|A-006|outputs[/\\]machine[/\\]M-001|outputs[/\\]machine[/\\]M-003" README.md PROJECT_STATE.md QUALITY_GATES.md RUNBOOKS TOOL_CONTRACTS.md TOOL_CONTRACTS WORKFLOWS.md TRIGGERS.md docs
python -B -m py_compile tools\researchos_outputs.py tools\zotero\zotero_ai_governance.py
```
