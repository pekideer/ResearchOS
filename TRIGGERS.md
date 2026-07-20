# ResearchOS 自然语言路由

本文件只把用户表达映射到能力编号、一个主 skill、工作流和质量检查。能力边界以 `CAPABILITIES.md` 为准，执行细节在 skill/`WORKFLOWS.md`，验收细节在 `QUALITY_GATES.md`。只有路由仍不确定时才读取 `docs/capabilities/skill-boundaries.md`。

## 第一道路由

先判断任务层级：

1. 材料已足够：直接进入 LLM 原生任务和对应主 skill。
2. 缺本地材料：只调用已有工具准备语料，再回到主 skill。
3. 涉及 Zotero、文件迁移、删除、批量改名或外部 API 写入：先进入审批流程。
4. 治理 ResearchOS 本身：只修改规则、skill、流程、模板和必要工具，不把课题成果写入框架根目录。

明确请求直接路由；只有主意图不清、多目标冲突或不知道下一步时才使用 `semantic-route-planner`。

## 紧凑路由表

| 用户主要意图 | 编号 | 主 skill / 入口 | 工作流 | 主要检查 |
|---|---|---|---|---|
| 判断该走哪个能力、拆解多目标请求 | C01 | `semantic-route-planner` | 00 | 语义路由 |
| 继续当前课题、恢复上下文、定位进展、项目地图、明确要求汇报导航 | C02 | `project-map-builder` | 00 | 项目地图、汇报导航 |
| 处理阅读批注、映射意见、更新批注文档 | C03 | `human-annotation-inbox` | 0X | 人工批注 |
| 记录碎片想法、建立 IDEA、初步潜力判断 | C04 | `idea-to-research-potential` | 0 | 点子潜力 |
| 父文档缺失/过期、Local API 排障、定位 PDF | C05 | `zotero-literature-access` | 1 | 来源、Zotero 父文档 |
| 单篇论文精读、仅生成本地读书卡 | C06 | `paper-deep-reading` | 1、1A | 证据、来源、输出 |
| 为某个或多个明确 Zotero 条目抽取全文、识别第一作者单位、生成或更新读书卡 | C05、C06、C11 | `zotero-reading-card-pipeline` | 1C、1B | 证据、Zotero 父文档、输出、写入 |
| 检查 Zotero 库增减并把新增条目完整推进到精读卡、中文单位、父条目 note 互斥、collection 与 tags 计划；每日完整增量治理 | C05、C06、C11 | `zotero-incremental-curator` | 1D、1B、0A | 证据、Zotero 父文档、collection/tags 语义、输出、写入 |
| 仅把已有读书卡发布为 Zotero 笔记、仅同步 PDF 高亮/批注并回流读书卡 | C06、C11 | `zotero-reading-card-annotation-sync` | 1B | 证据、Zotero 父文档、写入 |
| 关键词、检索式、数据库路线、候选发现 | C07 | `literature-search-map` | 2A | 来源、输出 |
| 多篇文献比较、综述矩阵、研究缺口线索 | C07 | `literature-matrix` | 2 | 证据、来源 |
| PRISMA 检索、筛选和阅读状态 | C07 | `WORKFLOWS.md` 工作流 2A | 2A | 来源、输出 |
| 综合库内外证据写深度研究报告 | C07、C08 | `research-intelligence-report` | 0B | 证据、来源、方法 |
| 判断研究缺口或选题是否值得做 | C08 | `gap-to-topic` | 2B | 证据、方法 |
| 把通过判断的选题变成问题、假设、变量和验证路径 | C08 | `research-question-framing` | 3 | 方法 |
| 审查方法、数据、模型、指标、对照和鲁棒性 | C09 | `methods-design-review` | 4 | 方法、证据 |
| 审计论文论断与证据是否匹配 | C09 | `claim-evidence-audit` | 4 | 证据、过度声称 |
| 明确建立/更新 `.paper/` 论文记忆 | C09 | `paper-memory-builder` | 4 | 证据、输出 |
| 根据图表事实组织结果与讨论 | C10 | `results-figure-narrative` | 4 | 证据、过度声称 |
| 保持技术含义的中英文学术润色 | C10 | `academic-polishing` | 4 | 语言、过度声称 |
| 拆解审稿意见并起草逐条回复 | C10 | `reviewer-response` | 5 | 证据、输出 |
| 整理整个 Zotero 库的主题、文献集和标签 | C11 | `zotero-library-governance` | 2C | Zotero 父文档、写入 |
| 检查和分诊 Zotero 新条目 | C11 | `WORKFLOWS.md` 工作流 2D | 2D | Zotero 父文档、写入 |
| 为明确课题生成 Zotero 项目文献集覆盖层计划 | C11 | `project-collection-overlay` | 0A | Zotero 写入 |
| 创建或审计课题输出目录 | C12 | `research-project-workspace` | 课题输出目录规范 | 命名、输出 |
| 代码/功能闭环审计 | C12 | `WORKFLOWS.md` 工作流 0C | 0C | 代码与功能闭环 |
| 发布共享 corpus、检查项目写入权、跨端写入接力 | C12 | `WORKFLOWS.md` 工作流 0D | 0D | corpus 发布与项目写入 |
| 文件命名、目录编号和命名冲突 | C12 | `RUNBOOKS/naming-governance.md` | 专题手册 | 命名 |
| Obsidian、双链和人读入口 | C12 | `RUNBOOKS/obsidian-zotero-codex-governance.md` | 专题手册 | 输出、命名 |

## 易混淆边界

- 点子记录 → `idea-to-research-potential`；检索式 → `literature-search-map`；深度综合报告 → `research-intelligence-report`；立项判断 → `gap-to-topic`；问题和变量 → `research-question-framing`。
- `.paper/` 只在明确建记忆或复杂多轮返修时创建；普通润色、审计、结果叙事和审稿回复不自动触发它。
- 父文档正常时，普通阅读不触发 `zotero-literature-access`。
- Zotero 标注回流由 `zotero-reading-card-annotation-sync` 处理；本地批注文件仍由 `human-annotation-inbox` 处理。
- 普通任务结尾不触发项目地图；只有用户明确要求恢复、定位或导航时使用 `project-map-builder`。
- 每个请求默认只有一个主 skill；辅助 skill 不重复生成主输出。

## 上下文与安全

- “当前课题”“继续上次”“研究进展”先读 `docs/modes/AGENTS.local-research.md`，执行唯一恢复链。
- Zotero 默认只读并优先使用父文档；任何写入必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。
- 命名、Obsidian、读书卡、父文档和外部写入只读取相关专题手册，不加载全部规则。
- 具体科研成果写入用户指定项目工作区；ResearchOS 根目录只保存通用框架和自身治理材料。

## 完成标准

- 已确定一个主能力和主 skill/入口。
- 已说明必要输入、输出位置和主要质量检查。
- 只有确实需要时才加载辅助 skill、工具契约或专题手册。
- 高风险动作已停在审批边界。
