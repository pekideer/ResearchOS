# ResearchOS Capabilities

本文档是 ResearchOS 的能力索引。需要判断“这个科研助理能做什么”时，优先查看本文件。

如果你不想记 skill 名称，直接查看 `TRIGGERS.md`，按自然语言表达任务即可。

## 本文件职责

`CAPABILITIES.md` 只维护 ResearchOS 能力编号和能力边界。它不维护自然语言触发表达全集、不定义执行步骤、不记录工具契约细节，也不记录治理状态。

严格依赖关系：

```text
AGENTS.md 约束所有能力
README.md 只导航到本文件
CAPABILITIES.md 定义 C01-C12
TRIGGERS.md 使用 C01-C12 做自然语言路由
WORKFLOWS.md 使用 C01-C12 组织执行流程
QUALITY_GATES.md 使用 C01-C12 组织验收
```

## 统一能力编号

能力编号用于稳定连接 `CAPABILITIES.md`、`TRIGGERS.md`、`WORKFLOWS.md` 和 `QUALITY_GATES.md`。当用户用自然语言提出任务时，先在 `TRIGGERS.md` 找到能力编号，再进入对应工作流和质量检查。

所有能力默认先判断是否可以由 LLM 直接完成。只有需要获取本地语料、读取 Zotero、抽取 PDF、批量整理文件、生成机器中间产物或执行外部写入时，才进入工具层。工具不是 ResearchOS 的主体，而是为科研助理准备上下文和连接外部系统的补足层。

工具层不得自行调用通用语言模型 API，也不得用关键词或评分逻辑替代 LLM 完成研究语义分类。批量任务采用“工具准备带溯源语料包 → 当前 ChatGPT/Codex agent 判断 → 工具校验并应用结构化结果”的统一模式。

| 编号 | 能力名称 | 触发入口 | 流程入口 | 主要质量检查 |
|---|---|---|---|---|
| C01 | 语义路由与能力定位 | `TRIGGERS.md` 语义路由与能力定位 | `WORKFLOWS.md` 工作流 00 | 语义路由检查 |
| C02 | 项目地图与汇报导航 | `TRIGGERS.md` 项目地图与当前位置、汇报导航优化 | `WORKFLOWS.md` 工作流 00 | 项目地图检查、汇报导航检查 |
| C03 | 人工批注收件箱 | `TRIGGERS.md` 人工批注收件箱 | `WORKFLOWS.md` 工作流 0X | 人工批注检查 |
| C04 | 点子捕获与研究潜力评估 | `TRIGGERS.md` 点子捕获与研究潜力评估 | `WORKFLOWS.md` 工作流 0 | 点子潜力检查 |
| C05 | Zotero 文献读取与父文档维护 | `TRIGGERS.md` Zotero 检索与读取 | `WORKFLOWS.md` 工作流 1 | 来源检查、Zotero 父文档检查 |
| C06 | 论文阅读与读书卡 | `TRIGGERS.md` 单篇论文精读、Zotero 条目到读书卡流水线、读书卡与标注闭环 | `WORKFLOWS.md` 工作流 1、1A、1B、1C | 证据检查、来源检查、Zotero 读书卡标注闭环检查、输出检查 |
| C07 | 多篇文献矩阵与 PRISMA | `TRIGGERS.md` 文献检索路线、多篇文献综述矩阵、PRISMA 检索筛选状态 | `WORKFLOWS.md` 工作流 2、2A | 证据检查、来源检查 |
| C08 | 研究缺口到选题 | `TRIGGERS.md` Gap 到选题立项、科研选题凝练 | `WORKFLOWS.md` 工作流 2B、3 | 方法检查、证据检查 |
| C09 | 论文写作、论断证据与方法审查 | `TRIGGERS.md` 方法路线审查、论文 论断-证据 审计、论文记忆 构建 | `WORKFLOWS.md` 工作流 4 | 方法检查、证据检查、过度声称检查 |
| C10 | 结果叙事、润色与审稿回复 | `TRIGGERS.md` 图表结果叙事、学术润色、审稿回复 | `WORKFLOWS.md` 工作流 4、5 | 语言检查、输出检查、过度声称检查 |
| C11 | Zotero 文献库治理与新条目分诊 | `TRIGGERS.md` Zotero 文献库治理、Zotero 新条目分诊、项目级 Zotero Collection Overlay | `WORKFLOWS.md` 工作流 0A、2C、2D | Zotero 父文档检查、Zotero 写入检查 |
| C12 | ResearchOS 规则、命名和输出治理 | `TRIGGERS.md` 代码审计与功能闭环审计、命名规则治理、Obsidian 协同与双链治理、课题输出目录创建 | `WORKFLOWS.md` 工作流 0C、课题输出目录规范 | 命名治理检查、ResearchOS 治理仪表盘检查、代码与功能闭环检查 |

## 总体能力

ResearchOS 的能力按六个科研助理场景域理解；具体细目以“统一能力编号”中的 `C01-C12` 为准，避免在多个入口维护重复清单。

1. 文献事实源与语料准备：以同步盘 SQLite 和规范化 PDF 文本作为默认事实源，为 LLM 阅读、综述和治理准备可回溯上下文。
2. 文献阅读、综述矩阵与 PRISMA：由 LLM 完成精读、比较、缺口判断和报告写作，工具只负责整理条目、全文和状态库。
3. 点子、研究缺口与选题设计：把用户想法转成可判断的研究问题、候选缺口、贡献边界和可行性路线。
4. 论文写作、证据审计与审稿回复：围绕用户材料和证据边界完成写作、润色、方法审查、论断-证据审计和回复策略。
5. 项目上下文、汇报导航与人读知识体系：恢复指定项目路径下的上下文，生成当前位置、下一步和人读入口，不把具体成果沉积到 ResearchOS 根目录。
6. ResearchOS 规则、质量检查与工具契约：维护科研助理运行框架自身的规则、触发、流程、契约、评测和边界。

## 任务分层

| 任务类型 | 判断标准 | 默认处理 |
|---|---|---|
| LLM 原生任务 | 已有语料足够，目标是理解、总结、推理、写作、润色、审查或对话 | 直接进入对应 skill、工作流和质量检查 |
| 语料准备任务 | 缺少 PDF 文本、Zotero 元数据、SQLite 父文档、项目目录上下文或批量文件结构 | 调用已有工具准备上下文，再回到 LLM 完成科研判断 |
| 外部写入任务 | 涉及 Zotero 写入、文件移动、批量改名、删除、系统设置或外部 API 写入 | 单独审批，进入对应 policy、runbook 和工具契约 |
| ResearchOS 治理任务 | 目标是治理规则、流程、契约、模板、工具边界或框架状态 | 只改框架文档或已批准的最小实现，不写入具体项目成果 |

## 科研助理场景入口

| 任务 | 使用 skill | 输入 | 输出 |
|---|---|---|---|
| 自然语言语义路由 | `semantic-route-planner` | 用户原始自然语言请求、当前上下文、能力索引和触发路由 | 主意图/次级意图判断、推荐 skill、工作流、runbook、质量检查和执行路线 |
| 项目地图构建 | `project-map-builder` | 项目入口、`docs/` 治理记录、`.researchos` 指针、过程记录、用户开放文本 | 项目蓝图、起点到当前位置路线、当前阶段、未决问题和可能下一步 |
| 项目上下文与汇报导航 | `project-map-builder` | 项目指针、manifest、运行状态和用户明确的导航请求 | 恢复摘要、当前位置、路线推进、下一步建议和需要确认事项 |
| 命名规则治理 | `RUNBOOKS/naming-governance.md` | 对象类型、已有目录/文件、命名冲突或新增命名规则需求 | 统一命名规则、命名审查清单、目录/编号/文件名建议 |
| 从 Zotero 或 PDF 准备阅读语料 | `zotero-literature-access`、`zotero-library-governance`、既有工具契约 | 条目 key、查询词、项目目录、父文档状态 | 可回溯上下文包、规范化文本、缺失材料说明；科研判断仍由 LLM 完成 |
| 单篇论文精读 | `paper-deep-reading` | 论文文本、题录信息、页码范围 | 读书卡、可引用观点、局限性和需要核查内容 |
| Zotero 条目到语义读书卡 | `zotero-reading-card-pipeline` | 一个或多个 item key、新增范围或全库范围、父文档和规范化文本 | 期刊状态、第一作者单位语义结果、集中初筛读书卡、严格覆盖审计和可选发布预检 |
| Zotero 读书卡与标注闭环 | `zotero-reading-card-annotation-sync` | 集中读书卡、item key、Zotero 原生 annotation、批准的 note 计划 | Zotero 读书卡子笔记、annotation 镜像、受控标注区和金丝雀审计 |
| 设计检索路线 | `literature-search-map` | 研究主题、对象、关键词 | 中英文关键词、检索式、数据库路线和引用追踪策略 |
| 撰写深度研究情报报告 | `research-intelligence-report` | 课题方向、技术细节、库内证据、可选外部数据库导出 | 人工阅读研究报告、证据矩阵、库内覆盖和需补足材料清单 |
| 处理人工批注收件箱 | `human-annotation-inbox` | 项目/idea 本地 `10-批注/inbox.md`、全局 inbox、目标文档路径或锚点 | 批注映射、检查判断、建议更新、review log 和 processed 归档 |
| 碎片想法到研究潜力评估 | `idea-to-research-potential` | 用户点子、可选课题目录 | 项目工作区或 `0.Inbox/02-unassigned-ideas/` 中的点子卡、来源记录和研究简报 |
| 多篇文献综述矩阵 | `literature-matrix` | 多篇读书卡、文献摘要或已有矩阵 | append-only 文献矩阵、真实研究缺口、伪研究缺口、选题建议 |
| 研究缺口到选题立项 | `gap-to-topic` | 候选研究缺口、综述矩阵、读书卡、数据条件 | `topic_dossier.md`、`gaps.yml`、是否仍有研究空间、是否有明确贡献、是否具备完成条件 |
| 科研选题凝练 | `research-question-framing` | 研究兴趣、gap、数据条件 | 研究问题、假设、变量、验证路径 |
| 论文记忆 构建 | `paper-memory-builder` | 论文草稿、图表、证据、返修材料 | `.paper/论断s.yml`、`.paper/figures.yml`、`.paper/evidence_artifacts.yml` |
| 论文逻辑审计 | `claim-evidence-audit` | 论文段落、图表或结果 | 论断-evidence 表、风险等级、修改建议 |
| 方法路线审查 | `methods-design-review` | 研究问题、数据、模型、指标 | 方法匹配性、对照组、鲁棒性建议 |
| 图表结果叙事 | `results-figure-narrative` | 图表、数据趋势、实验设计 | Results 事实、Discussion 解释、过度推断提醒 |
| 学术润色 | `academic-polishing` | 中文或英文论文文本 | 修改版、修改理由、含义风险提醒 |
| 审稿回复 | `reviewer-response` | 审稿意见、稿件修改内容 | 回复草稿、修改策略、补实验/补图/补引用判断 |
| 创建课题输出目录 | `research-project-workspace` | 课题目录路径或课题名 | 编号化输出文件夹 |
| ResearchOS 规则与工具边界治理 | `WORKFLOWS.md` 工作流 0C | ResearchOS 项目根目录、治理规则、工具契约、用户指定重点 | 规则问题清单、功能闭环表、工具必要性判断、测试缺口和治理优先级 |

## 治理与质量保障入口

以下表格只列入口文档，不再维护第二套能力清单；能力归属以 `C01-C12` 为准。

| 入口 | 说明 | 对应文档 |
|---|---|---|
| 路由入口 | 将用户口语化请求映射到能力编号、工作流和 skill | `TRIGGERS.md` |
| 流程入口 | 承载标准执行步骤和输出结构 | `WORKFLOWS.md` |
| 验收入口 | 检查证据、来源、方法、Zotero 读写、语言和输出结构 | `QUALITY_GATES.md` |
| 工具入口 | 明确脚本用途、输入、输出、允许行为、禁止行为和失败处理 | `TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/00-index.md` |
| 安全入口 | 管理科研诚信、输出语言、API key 和 Zotero 写入审批 | `POLICIES/` |
| 操作手册入口 | 承载复杂任务细则，避免根目录文档过重 | `RUNBOOKS/` |
| 测试入口 | 检查 skill 稳定性、科研诚信和可复核输出 | `EVALS.md` |
| 状态模板入口 | 支持长任务中断后的状态恢复 | `RUN_STATE_TEMPLATE.md`、`templates/project-state/run-state.md` |
| 项目工作区能力映射 | 固化能力、基础功能文件和项目目录作用 | `docs/capabilities/project-workspace-capability-map.md` |

`.research/` manifest 建议使用 `templates/project-state/project-manifest.yml`、`templates/project-state/run-state.json`、`templates/project-state/experiment-matrix.yml`、`templates/project-state/data-dictionary.yml` 和 `templates/project-state/open-questions.md`。

PRISMA 综述状态建议使用课题目录 `03-文献矩阵/prisma/`，并从 `templates/prisma/records.csv`、`templates/prisma/search-log.csv` 和 `templates/prisma/zotero-tag-map.yml` 初始化。主状态保存在 `prisma-records.csv` 和读书卡文末元数据；Zotero 只镜像 `rs:*` 标签。

## 自然语言入口

自然语言示例、触发表达、能力编号、优先 skill、工作流和默认输出统一维护在 `TRIGGERS.md`。本文件只维护能力地图，不再维护第二套 prompt 清单。

若需要设计新的可复用 prompt，应优先放入对应 `templates/` 或 skill 文档，并在 `TRIGGERS.md` 中登记触发关系。

## 安全边界

- 全局安全规则见 `AGENTS.md`。
- Zotero 写入审批见 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。
- 科研诚信、来源、语言和输出验收见 `QUALITY_GATES.md` 与 `POLICIES/`。
- 本文件只保留能力索引，不维护完整安全规则副本。
