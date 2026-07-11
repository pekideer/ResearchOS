---
name: semantic-route-planner
description: 优化 ResearchOS 对用户自然语言的语义理解、任务分流和能力组合；当用户表达模糊、多目标、跨文献/选题/写作/Zotero/Obsidian/项目治理流程，或需要“判断该用哪个 skill/工作流”“把我的口语请求拆成可执行路线”“快速定位能力模块和流程”时使用。
---

## 目标

把用户口语化、开放式或跨任务的请求，转成 ResearchOS 可执行的能力路线。该 skill 不替代具体执行型 skill，而是先判断用户真正想达成的目标，再选择、组合和排序后续 skill、工作流、runbook 与质量检查。

## 输入

- 用户原始自然语言请求。
- 当前上下文：活跃项目、活跃点子、最近任务、已生成文件、用户明确偏好。
- ResearchOS 路由文档：`TRIGGERS.md`、`CAPABILITIES.md`、`WORKFLOWS.md`。
- 可选：`.researchos/active_ideas.md`、`.researchos/project_registry.yml`、`PROJECT_STATE.md`。
- 可选：用户指定的目标文件、Zotero 条目、Obsidian vault 文档或课题目录。

## 工作流

1. 保留用户原话，不先改写成内部字段。
2. 判断请求的主意图：检索、阅读、矩阵、选题、方法、写作、审稿回复、Zotero 治理、项目地图、命名治理、批注处理或输出格式优化。
3. 判断是否存在次级意图，例如先读材料再判断选题、先定位当前项目再写报告、先整理新条目再生成读书卡。
4. 查询 `TRIGGERS.md` 和 `CAPABILITIES.md`，列出候选 skill 和工作流；若存在多个候选，按最能闭环用户目的的能力优先。
5. 判断是否需要先恢复上下文：当前课题、继续上次、研究进展只转交 `project-map-builder`，由它执行 `AGENTS.local-research.md` 的唯一恢复链；不要在路由阶段自行扫描项目材料。
6. 输出执行路线：主 skill、辅助 skill、读取材料、输出位置、质量检查和是否需要审批。
7. 若用户请求本身已经足够明确，不要过度规划；直接转入对应执行型 skill。

## 路由判断

- “我想做什么”“帮我判断下一步”“这属于哪个流程”：优先本 skill。
- “当前课题/继续上次/进展在哪”：串联 `project-map-builder`。
- “最后汇报里告诉我我在哪、下一步做什么”：转交 `project-map-builder` 的汇报导航输出；普通任务结尾不额外触发 skill。
- “这些文件怎么命名/统一命名规则”：读取 `RUNBOOKS/naming-governance.md`。
- “检查 Zotero 新增文献”：走 Zotero 新条目分诊，不走普通库治理。
- “整理 Zotero 分类”：走 `zotero-library-governance`。
- “建立课题项目文献集”：走 `project-collection-overlay`。

## 输出

- 用户意图判断。
- 推荐能力路线。
- 需要读取的上下文或文件。
- 预期输出。
- 风险边界和是否需要用户确认。
- 若继续执行，进入对应 skill 或工作流。

## 质量规则

- 不把用户模糊表达强行收窄成单一科研结论。
- 不编造用户没有提供的项目背景、文献状态或历史进展。
- 涉及 Zotero 写入、文件迁移、批量修改时，必须标出审批边界。
- 输出给用户时使用自然中文，不暴露 `open`、`gate`、`core` 等内部流程词。
- 能从本地文档发现的事实先读取，不向用户询问。

## 完成条件

- 已明确用户主意图和次级意图。
- 已给出可执行的 ResearchOS 能力路线。
- 已说明使用哪些 skill、工作流、runbook 和质量检查。
- 若存在高风险操作，已标注审批或只读边界。
