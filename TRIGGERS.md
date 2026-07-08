# ResearchOS Triggers

用户不需要记住 skill 名称。本文档只负责把自然语言表达映射到 `CAPABILITIES.md` 中的能力编号、优先 skill、工作流和质量检查；不定义能力边界、不展开执行细节、不复制质量标准正文。

严格依赖关系：

```text
CAPABILITIES.md 提供能力编号
TRIGGERS.md 将用户表达映射到能力编号
WORKFLOWS.md 承接执行
QUALITY_GATES.md 承接验收
TOOL_CONTRACTS.md / TOOL_CONTRACTS/ 仅在需要工具补足时介入
```

如果任务跨多个能力，应按 `WORKFLOWS.md` 串联执行。Zotero 相关任务默认只读，并且默认先读取 ResearchOS 共享事实源：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。任何写入必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。

## 使用原则

- 第一步先判断请求属于 `LLM 原生任务`、`语料准备任务`、`外部写入任务` 还是 `ResearchOS 治理任务`，再选择能力编号和 skill。
- 先判断用户真实任务，再选择对应 skill。
- 普通科研阅读、综述、选题、写作、润色、审查和对话默认由 LLM 完成；工具只在缺少本地语料、结构化数据或外部系统操作时补足。
- 材料不足时说明缺什么，不编造。
- 科研结论必须区分事实、推断、建议和假设。
- 默认使用简体中文；严禁无必要中英文混用。除文献原题名、DOI/URL、数据库/软件/API 名、文件名、路径、命令、字段名、skill 名、文献专门术语和领域共同认可缩写外，普通概念必须写成中文。

## 第一道路由

| 类型 | 典型表达 | 默认动作 |
|---|---|---|
| LLM 原生任务 | 精读、综述、找缺口、润色、审查、写回复、判断下一步、解释材料 | 读取已提供或已准备语料，直接进入对应 skill、工作流和质量检查 |
| 语料准备任务 | 读取 Zotero、抽取 PDF、构建上下文包、同步父文档、整理批量文本 | 只调用已有工具准备语料，完成后回到 LLM 生成科研判断或人读输出 |
| 外部写入任务 | 写入 Zotero、移动/删除/批量改名、修改系统设置、外部 API 写入 | 暂停直接执行，转入审批规则、runbook 和工具契约 |
| ResearchOS 治理任务 | 治理规则、收束文档、检查契约、审计工具、更新触发链路 | 只治理框架文档、工具边界和必要状态，不写入具体课题成果 |

## 统一安全边界

- Zotero 默认只读；任何写入、移动 PDF、修改文献集或标签，统一转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。
- 使用文献、PDF 或大段全文前，统一执行 `QUALITY_GATES.md` 的来源检查和 Zotero 父文档检查。
- 生成科研判断前，统一执行证据检查、方法检查或过度声称检查；不把未核查内容写成事实结论。
- 面向用户的 Markdown、YAML、HTML、报告和汇报统一执行语言检查与输出检查。
- 文件移动、批量删除、脚本/代码写入、外部 API 写入和系统级设置修改，均需单独确认；新增或修改代码前必须先汇报必要性、作用、复用替代、最小改动路径和风险。

## 语义路由与能力定位

能力编号：`C01`

### 触发表达

- 这个问题应该走哪个流程
- 帮我判断下一步
- 把我的请求拆成执行路线
- 快速定位能力模块
- 我这个需求属于哪个 skill
- 我说得比较乱，你先帮我归类

### 优先 skill

- `semantic-route-planner`

### 默认输出

- 用户主意图和次级意图
- 推荐 skill、工作流、runbook 和质量检查
- 需要先读取的上下文
- 风险边界和是否需要审批

### 完成标准

- 用户请求被转成可执行路线。
- 若能直接执行，已转入对应 skill；若不能直接执行，已说明缺少什么。

## 代码审计与功能闭环审计

能力编号：`C12`

### 触发表达

- 检查所有代码是否存在问题
- 检查 ResearchOS 所有代码是否有问题
- 检查功能是否闭环
- 帮我看功能实现有没有闭环
- 审计 ResearchOS 实现完整性
- 审计工具契约和实现是否一致
- 只读检查代码质量和测试缺口
- 检查入口、实现、测试和文档是否闭环

### 优先工作流

- `WORKFLOWS.md` 的“工作流 0C：代码审计与功能闭环审计”

### 默认入口

- `AGENTS.md`
- `CAPABILITIES.md`
- `TRIGGERS.md`
- `WORKFLOWS.md`
- `QUALITY_GATES.md`
- `TOOL_CONTRACTS.md`
- `TOOL_CONTRACTS/00-index.md`
- `README.md`
- `PROJECT_STATE.md`
- `tools/`
- `.agents/skills/`
- `tests/`、`EVALS.md` 和可用测试配置
- 模板：`templates/researchos-code-closure-audit-prompt.md`

### 默认输出

- 总体健康度判断
- 功能闭环表
- 代码问题清单
- 测试与验收缺口
- 治理优先级
- 可执行检查或测试命令

### 安全提醒

- 执行 `QUALITY_GATES.md` 的代码与功能闭环检查；默认只读，修复需用户明确要求。

### 完成标准

- 已说明读取了哪些入口、源码、测试和契约。
- 每个问题都有文件/行号、证据、影响和建议。
- 功能闭环判断覆盖入口、核心逻辑、数据读写、输出、失败处理、测试和文档。

## 项目地图与当前位置

能力编号：`C02`

### 触发表达

- 当前项目全貌
- 我现在走到哪一步
- 从起点到现在做了什么
- 根据已有文件推测下一步路线
- 建立项目蓝图
- 回溯这个项目的发展路线

### 优先 skill

- `project-map-builder`

### 默认入口

- `.researchos/active_ideas.md`
- `.researchos/project_registry.yml`
- `docs/README.md`
- 具体点子或课题入口页
- `PROJECT_STATE.md` 和相关过程记录

### 默认输出

- 项目/点子一句话定位
- 当前蓝图
- 从起点到当前位置的路线
- 当前阶段
- 未决问题
- 可能下一步路线

### 完成标准

- 已说明读取了哪些入口和过程记录。
- 当前位置和下一步预测区分事实、推断和建议。

## 汇报导航优化

能力编号：`C02`

### 触发表达

- 优化汇报格式
- 汇报末尾告诉我当前位置和下一步
- 每次总结后给下一步建议
- 根据本次对话推测我想做什么
- 把报告写得更像可继续推进的工作台

### 优先 skill

- `report-context-navigator`

### 默认输出

- 本次完成内容
- 实际检查结果
- 当前位置
- 下一步建议
- 需要确认的事项

### 完成标准

- 汇报尾部能说明当前阶段、路线推进和 1-3 条具体下一步。
- 不把推测写成用户已决定的事项。

## 命名规则治理

能力编号：`C12`

### 触发表达

- 统一命名规则
- 这些文件怎么命名
- 命名规则太分散
- 收束目录/编号/文件名规则
- 建立命名规范
- 检查命名是否混乱

### 优先入口

- `RUNBOOKS/naming-governance.md`

### 默认输出

- 对象类型判断
- 应采用的命名规则
- 与现有规则的冲突
- 是否需要同步索引、路径常量、工具契约或入口页

### 完成标准

- 新命名规则不与已有规则冲突。
- 人读名称、机器 key、日期、编号和审计留存路径边界清楚。

## Obsidian 协同与双链治理

能力编号：`C12`

### 触发表达

- 用 Obsidian 管理 Markdown
- 默认用 Obsidian 打开 md
- 建立双链知识体系
- 建立 Zotero 和 Obsidian 跳转
- 整理读书卡、进展报告和研究报告的 Obsidian 入口
- 构建 Zotero + Obsidian + Codex 科研工具链

### 优先入口

- `RUNBOOKS/obsidian-zotero-codex-governance.md`

### 默认输出

- Obsidian vault 配置或使用说明
- 面向人阅读的入口页、方向页或课题入口页
- Zotero 链接与 Obsidian 双链的治理建议
- 必要时更新 `AGENTS.md`、模板或相关 runbook

### 安全提醒

- 执行 `RUNBOOKS/obsidian-zotero-codex-governance.md` 和统一安全边界；不得把 ResearchOS 根目录当作长期 Obsidian vault。

### 完成标准

- 人工入口能导航到读书卡、报告、流程文档和项目状态。
- 文献链接可回到 Zotero，内部知识链接可在 Obsidian 中形成双链。
- 未发生未经批准的 Zotero 写入或系统级默认程序修改。

## 人工批注收件箱

能力编号：`C03`

### 触发表达

- 处理我的批注
- 读取我的阅读意见
- 我在 inbox 里写了想法
- 把我的标记映射到文档
- 检查这些意见是否成立
- 根据我的批注更新对应报告/读书卡/简报/实时方向文档
- 清理批注收件箱

### 优先 skill / 工作流

- `human-annotation-inbox`
- 后续按目标文档类型串联 `claim-evidence-audit`、`academic-polishing`、`literature-matrix`、`idea-to-research-potential` 或 `paper-memory-builder`

### 默认入口

- 项目/idea 本地优先：`<project-or-idea-root>/annotations/inbox.md`
- 全局未归属入口：`.researchos/human-annotation-inbox/inbox.md`
- 模板：`templates/human-annotation-inbox-entry.md`

### 默认输出

- 批注到目标文档位置的映射结果
- 每条意见的检查判断、风险和建议更新
- 同目录 `annotations/review-log.md` 或 `.researchos/human-annotation-inbox/review-log.md`
- 已处理条目归档到同目录 `processed/`
- 可选：同目录 `.internal/annotation-action-plan.csv`

### 安全提醒

- 执行 `QUALITY_GATES.md` 的人工批注检查；目标位置不唯一时先列候选，不直接更新。

## 点子捕获与研究潜力评估

能力编号：`C04`

### 触发表达

- 记录这个点子
- 评估这个想法
- 把这个想法入库
- 碎片知识入库
- 判断这个点子的研究潜力
- 把这个想法变成研究方向
- 给这个点子形成要点汇报

### 优先 skill / 工作流

- `idea-to-research-potential`
- 后续按需要串联 `literature-search-map`、`gap-to-topic`、`research-question-framing`

### 必要输入

- 用户原始想法或知识片段。
- 可选：关联课题目录、已有文献、Zotero 条目 key、时间和资源约束。

### 默认输出

- `IDEA-YYYYMMDD-###` 稳定编号
- 点子卡
- 来源记录
- 研究潜力简报
- 指定项目工作区中的点子入口、判断索引或研究简报
- 暂无归属时的平级 `0.Inbox/02-unassigned-ideas/`

### 安全提醒

- 执行点子潜力检查和统一安全边界；未核查进展必须标注“需要核查”。

### 完成标准

- 点子已入全局 点子索引。
- 简报 区分事实、推断、建议、假设和需要核查项。
- 若建议继续推进，已说明如何进入 `gap-to-topic`。

## Zotero 检索与读取

能力编号：`C05`

### 触发表达

- 从 Zotero 搜索……
- 帮我找 Zotero 里关于……的论文
- 读取这个 条目 key
- 找这篇文献的 PDF
- 抽取这篇 PDF 的文本
- 读取全文 / 读取 PDF 全文 / 读取大段材料
- 根据 Zotero 生成读书卡

### 优先入口

- `tools/build_zotero_library_context_packet.py`，先从 SQLite 父文档和 规范化 PDF 文本 构建上下文包。
- 父文档缺失、过期或需要同步时，再使用 `zotero-literature-access` / `tools/zotero_library_index.py` 做只读维护或排障。
- 如需生成读书卡，后续调用 `paper-deep-reading`

### 必要输入

- 检索词、标题、作者、DOI 或 Zotero 条目 key，至少其一

### 默认输出

- 候选文献列表
- 条目 key
- 元信息
- 子条目和 PDF 附件 key
- 规范化 PDF 文本 状态、附件 key 和缓存路径
- 父文档上下文包路径
- 父文档或项目全文缓存 命中情况；命中时不重复抽取 PDF

### 安全提醒

- 执行来源检查、Zotero 父文档检查和统一安全边界；Local API 只作为父文档维护或排障入口。

### 完成标准

- 输出可复查的 条目 key、PDF 附件 key、父文档/规范化文本路径、文本来源或明确失败原因

## Zotero 文献库治理

能力编号：`C11`

### 触发表达

- 整理我的 Zotero
- 看看 Zotero 分类乱不乱
- 检查 Zotero 文件夹分类
- 按研究方向分类
- 找主题相近的文献
- 找可能重复的文献
- 哪些 标签需要统一
- 生成 Zotero 文献库治理矩阵
- 读取 Zotero 条目的全部字段

### 优先 skill

- `zotero-library-governance`

### 必要输入

- SQLite 父文档和 规范化文本 目录可读
- 只有父文档缺失、过期或需要同步时，才要求 Zotero Local API 可访问
- 可选：分类规则文件、筛选范围、输出目录

### 默认输出

- 原始字段 JSON
- 字段用途清单
- 文献治理矩阵
- 主题聚类报告
- 相似文献对
- 治理报告
- 只读治理计划

### 安全提醒

- 执行 Zotero 父文档检查、Zotero 写入检查和统一安全边界；相近主题不等于重复文献。

### 完成标准

- 计划可人工审批，且未发生 Zotero 写入

## Zotero 新条目分诊

能力编号：`C11`

### 触发表达

- 检查 Zotero 新增条目
- 看看最近加入 Zotero 的文献
- 监控 Zotero 新文献
- 把新条目加入待读
- 给新加入的文献做分类建议
- 找出父文档还没同步的新条目

### 优先入口

- `WORKFLOWS.md` 的“工作流 2D：Zotero 新条目分诊”
- `tools/zotero_new_item_monitor.py`
- 后续可串联 `zotero_library_index.py`、`project-collection-overlay`、`paper-deep-reading`

### 必要输入

- ResearchOS Zotero 父文档水位线，默认来自 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite`
- Zotero Local API 只读可访问
- 可选：分类规则、目标项目文献集或用户指定的待读规则

### 默认输出

- `docs/reports/zotero-new-item-monitor/new-items-report.md`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/new-items-report.csv`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/new-items-latest.jsonl`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/new-item-classification-plan.csv`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/zotero-new-item-write-plan-dry-run.json`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/monitor_state.jsonl`

### 安全提醒

- 这是父文档规则的受控例外：只读顶层条目元数据，不读取 PDF、不抽取全文、不写入 Zotero。

### 完成标准

- 新条目报告说明水位线、访问边界和新增数量。
- 每个新条目有发现、报告、分类、父文档同步、写入审批、读书卡或排除状态之一。
- 分类计划列出需人工复核项。
- 未发生 Zotero 写入、PDF 读取或 PDF 移动复制。

## 项目级 Zotero Collection Overlay

能力编号：`C11`

### 触发表达

- 为当前课题创建项目文献集
- 在 `00.科研项目` 下给这个课题建项目文献集
- 把这些文献加入课题文献集
- 按课题用途细分 Zotero 文献集
- 区分 idea/研究缺口、综述、引言引用、方法来源、成果谋划
- 为“光谱选择性材料位置效应研究”建立项目文献集

### 优先 skill / 工作流

- `project-collection-overlay`
- 先只读串联 `zotero-library-governance` 或 `tools/build_zotero_library_context_packet.py`
- 如用户确认写入，再转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`

### 必要输入

- 课题名称或项目名称。
- 项目性质；不确定时先用 `其他` 或 `培育` 标记，并在方案中提示人工确认。
- 至少一个筛选依据：关键词、技术细节、种子 条目 key、已有文献集/标签、读书卡或用户指定条目。

### 默认输出

- 固定一级目录、具体课题目录和用途子文献集层级。
- 条目到项目子文献集的分配计划。
- 每个条目 的项目用途和证据理由。
- 试运行写入计划；不自动写入 Zotero。

### 安全提醒

- 执行 Zotero 写入检查和统一安全边界；项目文献集是覆盖层，不替代主题文献集。

### 完成标准

- 每条候选条目有项目用途、目标项目文献集 和可复查理由。
- 需复核条目已单独标记。

## 深度研究情报报告

能力编号：`C07`、`C08`

### 触发表达

- 撰写深度研究报告
- 调研这个方向
- 结合库内文献和 Scopus / EI / Web of Science 做报告
- 分析这个技术细节的研究现状
- 这个兴趣点有哪些研究机会
- 当前库还缺哪些材料
- 输出面向人员阅读的研究报告

### 优先 skill / 工作流

- `research-intelligence-report`
- 串联 `literature-search-map`、`zotero-library-governance`、`literature-matrix`
- 对明确 研究缺口 可继续串联 `gap-to-topic` 和 `research-question-framing`

### 必要输入

- 研究主题、技术细节、兴趣点或候选课题。
- 可选：目标数据库、时间范围、项目目录、种子文献、外部数据库导出结果。

### 默认输出

- 人工阅读研究报告。
- 库内覆盖条目表。
- 证据矩阵。
- 外部数据库检索式或导入结果分析。
- “针对现有库的条目、需要补足的材料”建议清单。

### 安全提醒

- 执行来源检查、证据检查和统一安全边界；未导入的外部结果只能作为检索路线。

### 完成标准

- 结论可回溯到 Zotero 条目 key、规范化文本、矩阵行或外部导入记录。
- 已明确事实、推断、建议、假设和需要核查项。

## 单篇论文精读

能力编号：`C06`

### 触发表达

- 精读这篇论文
- 生成读书卡
- 分析这篇文献对我的课题有什么用
- 读取 Zotero 条目 key 后生成读书卡
- 识别作者单位 / 第一作者单位 / 第一单位
- 修正读书卡单位字段

### 优先 skill

- `paper-deep-reading`
- 先用 `tools/build_zotero_library_context_packet.py` 从父文档构建题录和 规范化文本 上下文
- 单位识别优先使用父文档 规范化文本 的首页片段；如课题 `.research/fulltext_cache/<cards-root-name>/ITEMKEY.txt` 已由父文档派生，也可复用该片段
- 如父文档和项目 缓存均缺失，才调用 `zotero-literature-access` 或 `tools/zotero_library_index.py` 维护父文档

### 必要输入

- 论文 PDF 文本、Zotero 条目 key、标题/摘要，三者至少其一
- 若任务涉及作者/单位识别，优先需要父文档 规范化文本；项目 `.research/fulltext_cache/<cards-root-name>/ITEMKEY.txt` 只作为可复用局部缓存

### 默认输出

- 一句话定位
- 研究问题
- 方法路线
- 数据/模型/实验条件
- 关键变量
- 主要结论
- 创新性判断
- 局限性
- 可迁移价值

### 安全提醒

- 执行证据检查、来源检查和 Zotero 父文档检查；不得编造 DOI、数据、图表或作者结论。

### 完成标准

- 读书卡优先保存到具体课题目录 `01-reading-cards/`；无课题目录时先要求确认项目路径。

## 文献检索路线

能力编号：`C07`

### 触发表达

- 帮我设计检索式
- 这个方向应该怎么搜文献
- 给我中英文关键词
- 设计 Web of Science / Scopus / Google Scholar 检索路线
- 我该从哪些种子文献开始

### 优先 skill

- `literature-search-map`

### 必要输入

- 研究主题、研究对象、初步问题或已知关键词

### 默认输出

- 中文关键词
- 英文关键词
- 同义词
- 数据库建议
- 检索式
- 种子文献策略
- 引用追踪策略
- 排除标准

### 安全提醒

- 执行来源检查；不声称某个数据库覆盖全部文献。

### 完成标准

- 检索式可复制到目标数据库试用，且范围边界清楚

## 多篇文献综述矩阵

能力编号：`C07`

### 触发表达

- 把这些文献做成矩阵
- 汇总这些读书卡
- 比较这些论文的方法和指标
- 找真实研究缺口 和伪研究缺口
- 这些文献可以分成哪几类

### 优先 skill

- `literature-matrix`

### 必要输入

- 多篇读书卡、摘要、题录或全文摘录；若需要全文，优先使用 Zotero 父文档 规范化文本，其次复用由父文档派生的 `.research/fulltext_cache/`

### 默认输出

- 文献矩阵表
- 研究对象分类
- 方法分类
- 指标分类
- 已解决问题
- 真实研究缺口
- 伪研究缺口
- 选题建议

### 安全提醒

- 执行证据检查和过度声称检查；研究缺口必须由矩阵支持。

### 完成标准

- 矩阵可保存到 `02-literature-matrix/`，每个研究缺口有来源支撑
- 如已有矩阵，只追加新增文献行，未知字段用 `?`

## PRISMA 检索筛选状态

能力编号：`C07`

### 触发表达

- 引入 PRISMA 方法
- 建一个 PRISMA 数据库
- 记录文献筛选流程
- 生成 PRISMA 图的数据
- 标记哪些文献已读、重要、用于 intro 或综述
- 把 ResearchOS 状态同步成 Zotero 标签

### 优先工作流

- `WORKFLOWS.md` 中的“工作流 2A：PRISMA 检索、筛选和阅读状态数据库”

### 必要输入

- 课题目录，或已有 `prisma-records.csv`
- 可选：读书卡路径、Zotero 条目 key、检索日志

### 默认输出

- `prisma-records.csv`
- `prisma-search-log.csv`
- `prisma-reminders.csv`
- `prisma-flow-counts.json`
- `zotero-tag-mirror-plan.json`

### 安全提醒

- 执行来源检查、证据检查和 Zotero 写入检查；Zotero 只镜像已审批的 `rs:*` 标签。

### 完成标准

- 阅读卡片有 `generated_at`
- PRISMA 筛选决策和排除原因可复查
- 未审批前不发生 Zotero 写入

## Gap 到选题立项

能力编号：`C08`

### 触发表达

- 这个 研究缺口 能不能做
- 把这个 研究缺口 变成选题
- 判断这个选题是否值得继续
- 这个 研究缺口 是不是已经被解决了
- 输出 topic_dossier.md 和 gaps.yml
- 判断这个问题是否仍有研究空间、是否可能形成明确贡献、以现有条件是否做得出来

### 优先 skill

- `gap-to-topic`
- 通过或可修订后，再调用 `research-question-framing`

### 必要输入

- 候选研究缺口、综述矩阵、读书卡、用户材料或数据/实验条件

### 默认输出

- `topic_dossier.md`
- `gaps.yml`
- 这个问题是否仍有研究空间
- 是否可能形成明确贡献
- 以现有条件是否做得出来
- 继续推进 / 修改后推进 / 暂缓 / 放弃 决策

### 安全提醒

- 执行方法检查、证据检查和过度声称检查；证据不足时用 `?` 或“需要核查”。

### 完成标准

- 每个研究缺口有 `gap_id`、证据来源、三项判断结果和清晰决策

## 科研选题凝练

能力编号：`C08`

### 触发表达

- 帮我凝练研究问题
- 这个选题是否可行
- 把这个想法变成科研问题
- 提炼核心假设
- 明确自变量、因变量、控制变量
- 设计验证路径

### 优先 skill

- `research-question-framing`
- 如还没有完成推进判断，先调用 `gap-to-topic`

### 必要输入

- 研究兴趣、初步题目、文献 研究缺口、数据条件或实验条件

### 默认输出

- 研究对象
- 研究问题
- 核心假设
- 自变量
- 因变量
- 控制变量
- 验证路径
- 创新性风险
- 可完成性判断

### 安全提醒

- 执行方法检查；假设必须可验证，不把愿景写成研究问题。

### 完成标准

- 研究问题边界清楚，变量和验证路径可执行
- 如来自候选研究缺口，保留 `gap_id` 和推进判断结果

## 方法路线审查

能力编号：`C09`

### 触发表达

- 帮我审查方法路线
- 我的数据够不够
- 模型是否合理
- 指标能否支持结论
- 对照组是否充分
- 需要哪些鲁棒性分析

### 优先 skill

- `methods-design-review`

### 必要输入

- 研究问题、核心假设、数据、模型、指标或实验设计

### 默认输出

- 研究问题是否匹配方法
- 数据是否足够
- 模型是否合理
- 指标是否支持结论
- 对照组是否充分
- 鲁棒性/敏感性分析建议

### 安全提醒

- 执行方法检查；区分必要验证和增强验证。

### 完成标准

- 每条方法风险都说明会影响哪一个结论

## 论文 论断-证据 审计

能力编号：`C09`

### 触发表达

- 检查这段有没有过度声称
- 这个论断有证据吗
- 做 论断-证据 表
- 这段讨论是不是推过头了
- 检查摘要/引言/结论的逻辑

### 优先 skill

- `claim-evidence-audit`

### 必要输入

- 论文段落、图表、实验结果、统计指标或引用证据

### 默认输出

- 论断
- 证据
- 证据类型
- 风险等级
- 是否过度声称
- 修改建议

### 安全提醒

- 执行证据检查和过度声称检查；没有证据的论断必须标高风险。

### 完成标准

- 每个关键 论断 都有证据状态、风险等级和可执行修改建议

## 图表结果叙事

能力编号：`C10`

### 触发表达

- 根据这些图写 结果
- 帮我解释这些图
- 图表应该怎么组织叙事
- 哪些写 结果，哪些写 讨论
- 这张图能说明什么，不能说明什么

### 优先 skill

- `results-figure-narrative`

### 必要输入

- 图表、数据趋势、统计结果、实验设计或指标定义

### 默认输出

- 每张图回答什么问题
- 图中最重要趋势
- 可写入 结果 的事实
- 可写入 讨论 的解释
- 不能过度推断的地方

### 安全提醒

- 执行证据检查和过度声称检查；结果只写图表直接支持的事实。

### 完成标准

- 结果和讨论 边界清楚，图表顺序服务于研究问题

## 论文记忆 构建

能力编号：`C09`

### 触发表达

- 构建论文记忆
- 整理 论断 / 图 / 证据
- 先把稿件做成可复用索引
- 多轮修改前先建 .paper
- 给审稿回复准备论断和证据索引

### 优先 skill

- `paper-memory-builder`
- 后续可调用 `claim-evidence-audit`、`results-figure-narrative`、`academic-polishing`、`reviewer-response`

### 必要输入

- 论文草稿、图表清单、结果说明、证据材料或返修稿

### 默认输出

- `.paper/manuscript_map.yml`
- `.paper/论断s.yml`
- `.paper/figures.yml`
- `.paper/evidence_artifacts.yml`
- `.paper/revision_history.yml`

### 安全提醒

- 执行证据检查和输出检查；`.paper/` 记忆是索引，不替代原始稿件或数据。

### 完成标准

- 论断、图/表 和 证据材料 能相互引用，后续写作类 skill 可复用

## 学术润色

能力编号：`C10`

### 触发表达

- 润色这段
- 改成学术英语
- 改成中文学术表达
- 降低论断强度
- 不改变技术含义地修改
- 改摘要/引言/讨论/结论

### 优先 skill

- `academic-polishing`

### 必要输入

- 待润色文本和目标语言

### 默认输出

- 修改版
- 修改理由
- 保留或调整的术语说明
- 含义变化风险

### 安全提醒

- 执行语言检查和过度声称检查；润色不得改变技术含义。

### 完成标准

- 修改版可直接替换或对照使用，含义风险已标注

## 审稿回复

能力编号：`C10`

### 触发表达

- 帮我回复审稿意见
- 拆解 reviewer comment
- 这条意见怎么改
- 写 回复信
- 判断是否需要补实验/补图/补引用
- 做审稿回复表

### 优先 skill

- `reviewer-response`

### 必要输入

- 审稿意见、稿件修改内容或用户说明

### 默认输出

- 审稿意见拆解
- 修改策略
- 回复草稿
- 稿件修改位置
- 是否需要补实验/补图/补引用

### 安全提醒

- 执行证据检查、语言检查和过度声称检查；不承诺未完成实验。

### 完成标准

- 每条回复都对应审稿意见和稿件修改位置

## 课题输出目录创建

能力编号：`C12`

### 触发表达

- 给这个课题创建输出目录
- 为某个课题建立 ResearchOS 文件夹
- 创建 reading-cards / literature-matrix / manuscript / reviewer-response
- 按课题名创建目录
- 换电脑后根据 project-name 找课题目录

### 优先 skill

- `research-project-workspace`

### 必要输入

- 课题根目录或 project name

### 默认输出

- `01-reading-cards/`
- `02-literature-matrix/`
- `03-manuscript/`
- `04-reviewer-response/`

### 安全提醒

- 执行输出检查和统一安全边界；目录不存在时必须有明确创建授权。

### 完成标准

- 输出目录已创建或 试运行 清楚列出将创建目录

## 模糊请求路由

能力编号：`C01`

- “帮我整理文献”：优先判断是 Zotero 文献库治理，还是多篇文献综述矩阵。
- “帮我看这篇论文”：优先使用单篇论文精读。
- “帮我写论文”：先判断是大纲、结果叙事、逻辑审计、润色，还是返修回复。
- “帮我找方向”：优先使用文献矩阵和研究问题凝练。
- “这个 研究缺口 能不能做”：优先使用 `gap-to-topic`。
- “多轮改稿前先整理”：优先使用 `paper-memory-builder`。
- “帮我查 Zotero”：优先使用 Zotero 只读检索与读取。
