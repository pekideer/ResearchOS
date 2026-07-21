# ResearchOS 工作流

本文档定义 ResearchOS 的标准科研流程。实际使用时可以只执行其中一部分。

本文件只承接 `TRIGGERS.md` 已路由出的能力编号和任务类型；不维护自然语言触发词全集、不重新定义能力边界、不复制工具契约正文。能力边界见 `CAPABILITIES.md`，触发表达见 `TRIGGERS.md`，验收标准见 `QUALITY_GATES.md`，工具边界见 `TOOL_CONTRACTS.md` 和 `TOOL_CONTRACTS/`。

复杂任务执行前，优先查看 `QUALITY_GATES.md` 和对应 `RUNBOOKS/`。涉及 Zotero 写入时，不在本工作流中直接执行，必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。

凡工作流需要读取 Zotero 元数据、PDF 或大段全文，必须先执行 `RUNBOOKS/zotero-library-parent-documents.md` 和 `RUNBOOKS/fulltext-cache-governance.md`：优先读取同步盘 SQLite 父文档和 规范化 PDF 文本；项目 文献集 层级和项目归属保持最新时，优先使用 `tools/zotero/zotero_fast_collection_sync.py`；只有需要补齐条目附件状态、全文缓存或 OCR 状态时，才通过 `tools/zotero/zotero_library_index.py` 更新父文档。

## 工作流总门禁：先判断任务层级

任何工作流开始前，先判断用户请求属于哪一层：

| 层级 | 进入条件 | 执行规则 |
|---|---|---|
| LLM 原生任务 | 已有语料足够，目标是理解、总结、比较、写作、润色、审查或对话 | 不新写代码，不先运行工具；直接使用对应 skill 和质量检查完成科研输出 |
| 语料准备任务 | 缺少 Zotero 条目、PDF 文本、项目目录上下文、SQLite 父文档或批量文件结构 | 只调用已有工具准备上下文；工具完成后回到 LLM 生成科研判断 |
| 外部写入任务 | 涉及 Zotero 写入、文件移动、批量改名、删除、外部 API 写入或系统设置 | 先暂停并转入审批规则；未经确认不执行写入 |
| ResearchOS 治理任务 | 目标是治理规则、能力、流程、契约、模板、工具边界或框架状态 | 只改框架层内容；具体课题成果仍写入用户指定项目路径 |

普通科研任务不得被默认解释为“需要开发新工具”。只有现有语料准备能力无法完成任务时，才按 `AGENTS.md` 的代码写入边界提出代码方案。

## 工作流 00：语义路由、项目地图与汇报导航

能力编号：`C01`、`C02`

目标：在任务开始时理解用户自然语言意图，在任务过程中定位项目当前位置，在任务结束时给出可继续推进的汇报尾部。

1. 用户请求模糊、跨多个能力或要求“判断下一步”时，先使用 `semantic-route-planner`。
2. 用户要求“当前项目全貌”“我走到哪一步”“从起点到现在做了什么”时，使用 `project-map-builder`，并读取用户开放权限内的项目入口、索引、过程记录和汇报文件。
3. 用户明确要求“恢复当前课题”“说明当前位置和下一步”或“构建项目地图”时，使用 `project-map-builder`；普通任务结尾不额外触发项目状态 skill。
4. 上下文恢复只执行 `docs/modes/AGENTS.local-research.md` 的唯一链；复杂任务或状态变化结束后更新 `run_state.json` 并追加一条 `run-log.jsonl` 最小记录。
5. 涉及文件、目录、编号或 Zotero 项目文献集命名时，先读取 `RUNBOOKS/naming-governance.md`，再决定新增或修改名称。
6. 语义路由只负责定位能力和路线；实际执行仍转入对应 skill、已有工具或工作流。
7. 项目地图中的未来路线必须标注为“基于当前材料的推断”，不得写成用户已决定事项。

主要输出：

- 语义路线：主意图、次级意图、推荐 skill 和工作流。
- 项目地图：蓝图、路线回溯、当前位置、未决问题和可能下一步。
- 汇报尾部：当前位置、路线推进、下一步建议和需要确认事项。

完成标准：

- 用户请求被映射到可执行 ResearchOS 能力路线。
- 项目当前位置和下一步建议有依据，且区分事实、推断和建议。
- 命名相关任务已回到统一命名规则，不新增分散规则。

## 工作流 0C：代码审计与功能闭环审计

能力编号：`C12`

目标：只读检查 ResearchOS 的规则、能力、工具契约和必要代码是否闭环，判断入口、核心逻辑、数据读写、输出、异常处理、测试和文档是否能支撑“科研助理运行框架”的用户目标。

1. 用户触发“检查代码问题”“检查功能闭环”“审计 ResearchOS 实现完整性”“检查工具契约和实现是否一致”等请求时，进入本工作流。
2. 先读取 `AGENTS.md`、`CAPABILITIES.md`、`TRIGGERS.md`、`WORKFLOWS.md`、`QUALITY_GATES.md`、`TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/00-index.md`、`README.md`、`PROJECT_STATE.md`、`EVALS.md` 和测试配置。
3. 识别功能入口：自然语言触发、工作流、skill、脚本、工具契约、测试入口和常用命令。
4. 对每个功能追踪链路：用户目标、入口、参数或配置、核心逻辑、数据读写、输出结果、失败处理、测试证据和文档说明。
5. 检查问题类型：科研助理定位偏移、工具必要性不足、功能正确性、闭环缺失、错误处理、数据一致性、安全风险、性能、幂等、重复实现、硬编码、测试缺口、文档实现不一致。
6. 默认只读，不修改文件，不运行会改写文件的 formatter、迁移、代码生成或修复命令；允许运行只读搜索、静态检查和不会改写源码的测试。
7. 输出总体结论、功能闭环表、代码问题清单、测试与验收缺口、治理计划和可执行检查命令。
8. 若用户后续明确要求修复，再按 P0/P1/P2 等级逐项执行；涉及代码修复时，必须先按代码写入边界汇报必要性并获得批准。

主要输出：

- 总体健康度判断
- 功能闭环表
- 代码问题清单
- 测试与验收缺口
- 治理优先级
- 可执行检查或测试命令

使用的质量检查：

- `代码与功能闭环检查`
- `输出检查`
- 涉及文件移动、Zotero 写入或外部 API 写入时，叠加对应安全检查。

完成标准：

- 每个高优先级问题都有文件/行号、证据、影响和建议。
- 功能闭环表覆盖入口、核心逻辑、输出、失败处理、测试和文档。
- 未闭环功能标明阻断点和最小修复方向。
- 未经用户明确要求，不发生代码修复或批量改写。

## 工作流 0D：共享 corpus 发布与项目写入

能力编号：`C12`

1. 所有摄取、OCR、全文规范化、集中读书卡和索引更新先进入本机 `M-006` staging；不得把 staging 完成报告为共享 corpus 已更新。
2. 使用 `publish_corpus.py plan` 冻结允许区域、源哈希、目标基线、SQLite 健康状态和 `plan_hash`。计划阶段只读 corpus。
3. 真实 corpus 必须先审批一个精确金丝雀；批准前不运行 `apply --apply`。Corpus Publisher 角色只是必要条件，不替代本次用户批准。
4. apply 前重新校验计划和基线；逐文件同目录原子替换，release manifest 最后提交。verify 必须回读全部 manifest 文件；任一不符即视为未提交或混合版本。
5. rollback 使用发布时生成的精确计划，并单独审批。禁止将回滚扩展为目录清理。
6. 任一工具写项目文件前调用共用 `project_write_guard.py`；handoff 所有权或 Agent Core/corpus 锚点漂移时整体停止。

完成标准：发布计划、角色、基线、提交清单、回读和回滚证据闭环；项目写入入口在首个写操作前 fail-closed。

## 工作流 0X：人工批注收件箱

能力编号：`C03`

目标：让用户在项目/idea 本地固定文件中记录阅读想法、意见和疑问；未归属内容才进入全局入口。agent 后续读取这些条目，映射到对应文档位置，检查证据边界，并给出建议、更新或归档。

1. 用户优先在当前项目/idea 的 `10-批注/inbox.md` 追加批注条目；跨项目或暂时不知道归属时，写入 `.researchos/human-annotation-inbox/inbox.md`。可复制 `templates/annotations/inbox-entry.md`。
2. 用户触发“处理我的批注/读取我的阅读意见/根据批注更新文档”。
3. 使用 `human-annotation-inbox` 选择本地 inbox 或全局 inbox，读取 `status: new`、`status: needs-confirmation` 或用户指定条目。
4. 根据 `target_document`、`target_anchor`、引用片段、标题、IDEA ID、Zotero key 或关键词映射到目标文档位置。
5. 检查每条意见是否有证据、是否过度声称、是否与目标文档冲突、是否需要补文献/补数据/改写。
6. 输出映射结果、检查判断、建议更新和风险说明；目标位置不唯一时先要求确认。
7. 用户要求应用时，只对人工文档做最小改动；机器文件、CSV/JSON、Zotero 父文档和 规范化文本 只输出更新建议。
8. 更新同目录 `review-log.md`，并把已完成的 `mapped`、`suggested`、`applied`、`rejected` 或 `archived` 条目移动到同目录 `processed/YYYY-MM-processed.md`；`needs-confirmation` 条目保留在活跃 inbox。

主要输出：

- `<project-or-idea-root>/10-批注/inbox.md`
- `<project-or-idea-root>/10-批注/review-log.md`
- `<project-or-idea-root>/10-批注/processed/YYYY-MM-processed.md`
- `.researchos/human-annotation-inbox/inbox.md`（未归属入口）
- 被更新的目标人工文档（可选）
- 被更新的目标人工文档（可选）

完成标准：

- 每条批注都有明确映射结果或无法唯一映射的说明。
- 检查判断区分事实、推断、建议、假设和需要核查。
- 未经确认不更新目标位置不明确的文档。
- 用户原始意见保留在活跃 inbox 或 `processed/` 归档中，不被覆盖或丢弃。

## 工作流 0：点子捕获到研究潜力评估

能力编号：`C04`

目标：把碎片化想法、知识片段和灵感问题沉淀为可追踪的科研资产，并判断是否值得进入选题判断。

1. 用户显式触发：“记录这个点子”“评估这个想法”“碎片知识入库”等。
2. 使用 `idea-to-research-potential`，生成 `IDEA-YYYYMMDD-###` 点子卡。
3. 点子默认写入用户指定项目工作区；暂无项目归属时，写入 `00_ResearchOS` 平级的 `0.Inbox/02-unassigned-ideas/` 等待分流。
4. 根据 quick、scout、deep 分级生成 研究潜力简报；点子持久化由 skill、模板、项目工作区和平级 `0.Inbox/02-unassigned-ideas/` 承担。
5. `quick` 只做结构化和初筛；`scout` 增加本地材料、读书卡和 Zotero 只读线索，并先形成宽候选池；`deep` 才进入外部检索，未核查内容必须标注“需要核查”。
6. 点子探索期默认多纳入少排除：候选文献先按“直接相关、机制相邻、方法相邻、场景相邻、背景材料、暂不纳入”分层，保留能帮助判断大方向的边缘文献。
7. 每次新增检索、精读、综述矩阵、汇报或人工判断后，更新 `IDEA-..._live-direction.md`，作为供人快速查阅的实时研究方向文档。
8. 只有当候选池和初步矩阵显示存在可疑真问题时，才对值得继续推进或需要调整后再推进的候选点子转入 `gap-to-topic`；完成推进判断后再用 `research-question-framing` 凝练研究问题。

主要输出：

- `docs/capabilities/idea-to-research-potential.md`
- 点子成果默认写入用户指定项目工作区；无归属时进入平级 `0.Inbox/02-unassigned-ideas/`。
- 点子材料进入具体项目工作区或平级 `0.Inbox/02-unassigned-ideas/`。

完成标准：

- 点子有稳定 `IDEA-###` 编号，并出现在指定项目工作区或平级 `0.Inbox/02-unassigned-ideas/`。
- 简报包含所属方向、研究进展、候选研究缺口、潜力评分、是否值得继续推进的初步判断、建议方向和下一步行动。
- 来源记录或简报 已保留宽候选池和分层理由；不得只记录少数已精读核心文献。
- 实时方向文档反映最近一次材料更新或人工方向判断，包含当前理解、证据地图、阅读材料状态、未定问题和下一步节点。
- 不确定进展、文献线索和潜力判断均标注证据状态。
- 未发生 Zotero 写入，未编造文献或领域结论。

## 工作流 0A：项目级 Zotero Collection Overlay

能力编号：`C11`

目标：在固定一级目录 `00.科研项目` 下，为具体课题创建项目 文献集，把文献从“主题归属”进一步组织为“项目用途”。

1. 输入课题名称、关键词、技术细节、种子 条目 key 或已有读书卡/矩阵。
2. 使用 `project-collection-overlay`，先只读查询 Zotero 父文档和 规范化文本。
3. 固定一级目录默认命名为 `00.科研项目`，除非用户明确要求修改，否则不随具体课题变化。
4. 在一级目录下创建具体课题目录，命名为 `NN-<项目性质中文缩写>-<项目简称>`，项目性质中文缩写可用 `纵向`、`横向`、`培育`、`论文`、`其他`。
5. 在具体课题目录下按用途分配子文献集，命名采用“编号-中文简写-English slug”，例如 `02-综述-review`、`03-引言-intro`、`04-方法-method`。
6. 每个条目 输出项目用途、目标子文献集、证据理由和需复核标记。
7. 只生成 试运行写入计划；如要写 Zotero，转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。

主要输出：

- `project-collection-plan.md`
- `project-collection-hierarchy.json`
- `project-collection-item-assignments.csv`
- `project-collection-write-plan-dry-run.json`

完成标准：

- 项目文献集是覆盖层，不替代主题文献集。
- 每条候选条目 的项目用途可回溯到 条目 key、标签、文献集、全文片段或用户说明。
- 未审批前未发生 Zotero 写入。

## 工作流 0B：深度研究情报报告

能力编号：`C07`、`C08`

目标：围绕课题方向、技术细节或兴趣点，结合本地库和外部数据库路线/导出结果，形成面向人工阅读的研究报告。

1. 使用 `research-intelligence-report` 确认研究边界和输出目录。
2. 用 `literature-search-map` 生成中英文关键词、检索式、数据库路线和排除标准。
3. 用 Zotero 父文档、文献集/标签和规范化文本 读取库内相关条目。
4. 如用户提供 EI、Scopus、Web of Science 等导出结果，读取并去重；若未提供，只输出可执行检索式和待导出说明。
5. 用 `literature-matrix` 形成核心证据矩阵；必要时用 `gap-to-topic` 评估候选研究缺口。
6. 输出人工阅读研究报告，并单列“针对现有库的条目、需要补足的材料”。

主要输出：

- `RI-###-research-intelligence-report.md`
- `RI-###-evidence-matrix.csv`
- `RI-###-local-library-coverage.csv`
- `RI-###-missing-materials.csv`
- 可选：`RI-###-search-strings.md`、外部结果规范化表

完成标准：

- 报告明确区分事实、推断、建议、假设和需要核查。
- 不把“现有库没有”直接写成领域空白。
- 缺材料建议具体到数据库、关键词、文献类型、用途和优先级。

## 工作流 1：从 Zotero 到单篇读书卡

能力编号：`C05`、`C06`

目标：把 Zotero 中的一篇文献转化为结构化读书卡。

读书卡版式、元数据位置、引用显示、作者单位和期刊等级规则唯一以 `RUNBOOKS/reading-card-governance.md` 为准；本工作流只定义从 Zotero 父文档到单篇精读的执行顺序。

1. 先查询 ResearchOS 共享事实源：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite`。
2. 搜索或确认候选条目 key 后，用 `tools/zotero/build_zotero_library_context_packet.py --profile content` 构建题录和规范化文本内容上下文包。
3. 优先读取 SQLite 中 `text_normalized_cache_path` 指向的规范化 PDF 文本；如路径因跨设备变化失效，按当前 `corpus/fulltext/zotero-library-normalized/ITEMKEY__ATTACHMENTKEY.txt` 回退。
4. 仅在父文档缺失、过期或 PDF 文本状态为缺失/失败/needs_ocr 时，通过工作流 1C 的本机 staging 调用 `sync` / `ocr-needed` / `normalize-text-cache`；验证后再进入 corpus 发布流程。
5. 旧项目 `.research/fulltext_cache/` 仅可只读兼容；新增项目局部文本进入 `02-证据材料/全文缓存/`，并应从父文档派生或能回溯到父文档。
6. 使用 `tools/reading_cards/build_affiliation_semantic_packet.py` 或同等缓存片段准备首页题录区证据。
7. 用 `paper-deep-reading` 完成第 1–6 节语义判断和第 7 节证据回执；批处理脚本不得替代该判断。
8. 调用 `tools.reading_cards.reading_card_contract.validate_reading_card`；只有 `deep_read_complete=true` 才能报告全文精读完成。
9. 保存前确认落点：默认先写本机 staging，发布后进入 `corpus/reading-cards/cards/`；项目目录只保留指针、阅读总表或团队追踪链接。
10. 如需维护项目级阅读总表，运行 `tools/reading_cards/sync_reading_summary_table.py`。

命令入口：

- 普通阅读优先使用 `tools/zotero/build_zotero_library_context_packet.py --profile content`、`tools/reading_cards/build_fulltext_cache_packet.py` 和 `tools/reading_cards/build_affiliation_semantic_packet.py`。
- 阅读总表同步使用 `tools/reading_cards/sync_reading_summary_table.py`。
- 父文档缺失、过期或排障时，才使用 `zotero-literature-access` 的 Local API 工具；完整参数和禁止行为见 `TOOL_CONTRACTS/01-zotero-parent-documents.md`。

使用的质量检查：

- `Zotero 父文档检查`
- `来源检查`
- `证据检查`
- `输出检查`

主要输出：

- Zotero 条目 元信息
- PDF 附件 key 和 PDF 路径
- PDF 文本抽取结果
- 单篇读书卡
- 可选：`03-文献矩阵/LM-004_reading-summary-table.md`

完成标准：

- 读书卡满足 `RUNBOOKS/reading-card-governance.md`，且统一契约返回 `valid=true`；全文精读返回 `deep_read_complete=true`。
- 如同步阅读总表，每行能回溯到读书卡路径和 Zotero 条目 key。
- 论文结论区分事实、推断、建议和假设。
- 未写入 Zotero，未移动或复制 Zotero PDF。

## 工作流 1A：读书卡同步项目级阅读总表

能力编号：`C06`

目标：在生成或更新每篇读书卡后，同步一张可筛选的大表，用于跨文献浏览、写作素材管理、评分、PRISMA 状态追踪和 Zotero 回溯。

1. 读书卡文末 `## 7. 元数据（折叠）` 尽量填写 `zotero_item_key`、`generated_at`、`read_status`、`importance`、`planned_use`、`topic_relevance`、`tags`、`journal_abbrev`、`publication_tags`、`rating_5`、`evidence_strength`、`one_paragraph_review`、`prisma_record_id`、`prisma_stage` 和 `gap_ids`。
2. `topic_relevance` 只接受用户或当前 agent 的明确判断；缺失时保持为空或待判断，汇总脚本不得根据 tags 或方向默认值自动补齐。
3. 读书卡正文保留 `## 一段话综述`，用一段话压缩“背景 + 目的 + 方法 + 结论 + 意义”。
4. 运行同步脚本，按课题 manifest 或项目登记确认读书卡来源；默认读取 `corpus/reading-cards/cards/` 中的集中主卡及项目链接，不把缺失的旧本地读书卡目录当作有效输入。
5. 脚本生成或更新人工活动总表 `03-文献矩阵/04-阅读总表/LM-004_reading-summary-table.html`，并按课题方向生成 `03-文献矩阵/04-阅读总表/分主题阅读总表/LM-004_reading-summary-table-<code>.html`；方向优先来自 `.research/project_manifest.yml` 的 `topic_directions` 或 `.research/topic_directions.csv`，若未配置则从读书卡 `tags` 中的 `T数字_方向名` 自动发现；同时生成 Markdown 备用表，并在 `03-文献矩阵/.internal/` 生成 CSV 镜像和 `reading-summary-reminders.csv`。
6. 如已有总表，脚本按 Zotero 条目 key、读书卡路径或题目匹配既有行；读书卡中明确填写的字段可更新总表，读书卡缺失字段不覆盖既有人工填写内容。
7. 这张表不替代 `literature-review-matrix.csv`：它偏阅读管理和写作素材汇总；完整综述矩阵仍负责研究对象、方法、指标、solved problem、real 研究缺口 和 pseudo 研究缺口。
8. 所有需要人工打开参阅的条目使用 `RC-###` 编号；提醒使用 `TODO-###` 编号，便于逐条处理。
9. `Zotero引用链接` 跳转 Zotero 母条目；人工表中的文献显示标签优先用 `Author(year)`，`Zotero PDF链接` 只有在读书卡或 PRISMA records 提供 PDF 附件 key 时生成。条目 key 放在机器镜像、元数据或审计字段；若人工表确需显示 条目 key，本身也必须是可点击 `zotero://select/library/items/KEY` 链接。
10. HTML 中“卡”按钮使用本地文件链接。

命令入口：使用 `tools/reading_cards/sync_reading_summary_table.py`；完整参数和输出约束见 `TOOL_CONTRACTS/04-reading-cards-prisma.md`。

输出建议：

- `03-文献矩阵/LM-004_reading-summary-table.html`
- `03-文献矩阵/04-阅读总表/分主题阅读总表/LM-004_reading-summary-table-<code>.html`
- `03-文献矩阵/LM-004_reading-summary-table.md`
- `03-文献矩阵/.internal/reading-summary-table.csv`
- `03-文献矩阵/.internal/reading-summary-reminders.csv`

使用的质量检查：

- `来源检查`
- `证据检查`
- `输出检查`

完成标准：

- HTML 宽表优先展示人工参阅编号、题目、作者、年份、一段话综述、相关程度、读书卡、Zotero 条目链接、Zotero PDF 链接、期刊缩写、评价、PRISMA 字段、阅读状态和 标签；总表显示全部课题方向，`reading-summary-tables/` 下每个方向单独成表，标题区显示对应课题方向，并在标题下方提供本地 HTML 跳转导航。表格容器自身固定高度并横向滚动，避免必须滚到整页底部才能左右移动。点击表头可排序；表头分隔线可拖拽调整列宽，同一路径下的列宽由浏览器本地记忆。
- `一段话综述` 来自读书卡明确字段或正文小节；脚本不自动编写科研结论。
- 缺失的一段话综述、与主题相关性、评分、期刊缩写或 PRISMA 字段会进入 reminders。
- 不面向人工日常阅读的 CSV 镜像、提醒、候选池、种子矩阵等机器产物应放入 `.internal/`。

## 工作流 1B：Zotero 读书卡与人工标注闭环

能力编号：`C05`、`C06`、`C11`

目标：把集中读书卡作为对应 Zotero 条目下的阅读笔记，并将 Zotero 原生 PDF 高亮和评论以可追溯证据回流读书卡。

1. 使用 `zotero-reading-card-annotation-sync`，确认目标 item key 已映射到唯一集中读书卡。
2. 先运行 `tools/zotero/zotero_annotation_sync.py` 的只读 dry-run；从题录 children 定位 PDF attachment，并通过一次全局 `itemType=annotation` 分页枚举按 `parentItem` 过滤目标标注。
3. 用户确认范围后加 `--write-mirror`，只写 ResearchOS 父文档的 `annotations` 表；全局枚举或目标条目读取失败时不执行相关 attachment 的软删除。
4. 运行 `tools/reading_cards/sync_zotero_annotations_to_cards.py` 生成读书卡受控区预览；原文摘录、人工判断、定位线索和需要核查分开显示。
5. 用户要求应用后才加 `--write-cards`，并必须显式给出至少一个 `--item-key`；工具只能替换唯一且配对正确的 `researchos:zotero-annotations` 起止标记内内容。
6. 需要在 Zotero 中阅读读书卡时，运行 `tools/zotero/write/publish_reading_card_note.py --card ...` 生成 live dry-run 和 HTML 预览。
7. 用户必须确认具体 `approved-plan-candidate.json`；随后只用 `--write --canary --approved-plan ...` 执行单条创建或版本安全更新。
8. 用户在 Zotero 中检查条目归属、排版、链接和同步结果；未确认前不得扩大批量。

主要输出：

- 父文档 `annotations` 与 `reading_card_zotero_notes` 表。
- 读书卡 `6.99 人工阅读标注（Zotero 同步）` 生成区。
- `.researchos/outputs/machine/M-005-reading-card-annotation-sync/`。
- `.researchos/outputs/archive/A-003-reading-card-note-publish/`。

使用的质量检查：

- `证据检查`
- `Zotero 父文档检查`
- `Zotero 写入检查`
- `Zotero 读书卡标注闭环检查`
- `输出检查`

完成标准：

- Zotero annotation 读取未修改 Zotero、PDF 或原始数据库。
- 标注可回溯到 item、attachment、页码和 annotation key。
- 读书卡其他正文未被同步程序覆盖。
- 真实 note 写入具有来源受限的具体批准计划、版本检查、写后身份/归属/标签/内容核验、执行前后证据和独立回滚计划。

## 工作流 1C：Zotero 条目到语义读书卡流水线

能力编号：`C05`、`C06`、`C11`

主 skill：`zotero-reading-card-pipeline`

目标：响应“生成某条阅读卡并同步到 Zotero”“处理新增条目”“全库生成读书卡”等自然语言，对一个、多个、新增或全库条目连续完成父文档、PDF 文本、期刊词典、第一作者单位语义识别、集中初筛读书卡和审计；真实 Zotero 笔记发布另行进入工作流 1B 的审批边界。

1. 按 `load_workspace_dependencies -> Zotero Local API 探测 -> sync -> 条件校验` 的顺序更新父文档；Zotero 不可用时停止，不扩大为直接读取 `zotero.sqlite`。
2. 代理地址属于机器私有配置：优先继承各电脑自己的 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`，也可写入未跟踪的 `.local/machine_config.json` 的 `proxy` 段；共享脚本、自动任务和仓库配置不得写死代理 host/port。`127.0.0.1`、`localhost`、`::1` 始终加入直连名单。
3. 原始抽取文本写入 `corpus/fulltext/zotero-library/`，AI 规范化文本写入 `corpus/fulltext/zotero-library-normalized/`；普通抽取后只对 `needs_ocr` 队列执行受限 OCR，超页数、book/thesis 默认跳过并保留原因；缺 PDF 和抽取错误保留明确状态，不伪装为成功。
4. 期刊词典只对 `journalArticle` 的期刊名称查询；`待查询`、`未收录`、`查询失败，待重试` 和 `不适用` 必须显式区分，禁止用裸 `?` 代替状态。
5. 流水线只记录首页文本是否可用和证据路径，初始状态为 `not_processed`；不得用正则单位候选填充读书卡字段。
6. 运行 `semantic-packet`，从 SQLite 指向的规范化全文提取第 1–3 页并生成带 `item version + input hash` 的批次。模型按首页题录提示词亲自判断作者、作者标号、单位标号、第一作者对应的第一个一级单位和国家；首页为封面时检查后续页。
7. 模型输出 `semantic_confirmed`、`semantic_needs_check`、`semantic_not_found` 或 `source_unavailable` 结果。先用 `semantic-apply` 默认预检，校验 item version、证据哈希、页码、原始片段和来源；通过后才用 `--write-local` 更新 SQLite 与读书卡。
8. 无卡条目可生成 `auto_initial_screening` 骨架；它只陈述题录、摘要原文和材料状态，不作科研结论，也不生成未映射的第 6 节。
9. 对要求精读或增量治理中全文可用的条目，逐条调用 `paper-deep-reading`；编排工具不覆盖人工/精读正文、annotation 区或项目用途。
10. 每张卡调用共享 `reading_card_contract`。全文精读需同时满足声明、正文实质内容、全文来源与页码、第 6 节项目结构；不能再用两个头部字段替代完成判定。
11. 增量模式以 `item version + pipeline version` 判定是否准备新语料；显式 `--item-key` 可触发单条同一流程。语料变更后必须重新生成语义回执。
12. 完成本地卡后运行 `audit --strict --curation-strict`。单位待处理或读书卡合同错误均阻断完成报告。
13. `run` 只写本机 `.researchos/outputs/machine/M-006-zotero-ingestion-pipeline/staging/`；共享更新只能由 Corpus Publisher 发布。用户要求同步 Zotero 时转入工作流 1B，发布预检和写前检查再次验证同一合同。

命令入口：

- 全库/首次运行：`python tools/reading_cards/zotero_library_pipeline.py run --scope all`
- 日常增量：`python tools/reading_cards/zotero_library_pipeline.py run --scope new`
- 单条自然语言触发对应命令：`python tools/reading_cards/zotero_library_pipeline.py run --item-key ITEMKEY`
- 生成待语义处理批次：`python tools/reading_cards/zotero_library_pipeline.py semantic-packet --scope pending --batch-size 20`
- 语义结果预检：`python tools/reading_cards/zotero_library_pipeline.py semantic-apply --results RESULTS.jsonl`
- 写入本地父文档和读书卡：`python tools/reading_cards/zotero_library_pipeline.py semantic-apply --results RESULTS.jsonl --write-local`
- 严格覆盖率审计：`python tools/reading_cards/zotero_library_pipeline.py audit --strict`

完成标准：

- 活跃条目、流水线状态和集中读书卡可按 item key 对齐。
- 文本成功、OCR、缺 PDF、抽取错误分别计数；成功记录有可访问的原始与规范化文本路径。
- 期刊字段无裸 `?`；单位只有 `semantic_confirmed` 或 `manual_confirmed` 可作为确定事实显示，其余状态明确说明语义未决、未找到或来源不可用。
- 请求范围满足数量守恒，不存在未说明的候选或未处理条目；确定单位均有原始片段、页码、来源和证据哈希。
- 现有人工读书卡正文未被模板覆盖；自动初筛卡没有未映射项目借鉴章，也没有把摘要改写成全文结论；旧式第 6 节、空项目块或含义不明的“本课题”会被合同阻断。
- 默认 staging 运行已明确报告 `corpus_publication_required`；未完成 Corpus Publisher 发布和共享快照校验时，不报告共享父文档或集中主卡已更新。
- 未写入 Zotero，未复制、移动、删除或重命名 Zotero PDF。

## 工作流 1D：Zotero 增量完整治理

能力编号：`C05`、`C06`、`C11`

主 skill：`zotero-incremental-curator`

目标：把“发现新增或变化”推进到可审计的完整语义资产，而不是停在初筛占位卡。

1. 同步前后分别冻结 Local API 顶层条目 `key + version` 快照；意外变化时废弃旧语义结果并重新取证。
2. 运行工作流 1C 的本机 staging 同步，随后按 DOI 与 item key 审计重键、活动/删除条目同 DOI、多卡同 key 和同 DOI 多活动卡；未完成 Corpus Publisher 发布时把共享语料状态标为待发布。
3. 对本次范围逐个父条目审计 ResearchOS 读书卡 note 数。`>1` 时冻结 keeper/删除计划并停止发布；真实删除必须单独批准并逐条回读。
4. 单位原文证据与显示值分开：当前 agent 识别作者对应关系和一级机构，显示值统一为 `中文一级机构，中文国家`；代码只验证格式和证据状态。
5. 有全文的新条目必须使用 `paper-deep-reading` 完成语义正文与证据回执，并由共享合同确认 `deep_read_complete=true`；两个精读标记本身不是完成证据。无全文时明确阻断。
6. 当前 agent 逐条判断 collection 与 tags，分别生成 dry-run。项目用途不明确时保持 triage，不用阅读状态推断用途。
7. 运行 `audit --strict --curation-strict --item-key ...`，再为缺失/需更新的唯一读书卡 note 生成 live dry-run。真实 Zotero 写入仍走工作流 1B 或相应 metadata 写入审批、金丝雀和回读。

验收：增减、重键、卡片互斥、精读状态、中文单位、collection、tags、note 与共享语料发布均有明确的完成/待审批/待发布/阻断状态；“占位卡已创建”不等于“精读完成”。

## 工作流 2：从多篇文献到 只追加 综述矩阵

能力编号：`C07`

目标：把多篇读书卡转化为可比较的综述矩阵。

1. 先检查是否已有 `literature-review-matrix.csv`。
2. 收集同一课题下的读书卡、笔记、文末元数据或 Zotero 父文档元信息；若需要 PDF 全文，先用 `tools/zotero/build_zotero_library_context_packet.py --profile content` 或 `02-证据材料/全文缓存/` 生成证据包；旧 `.research/fulltext_cache/` 只读兼容。PDF 重新抽取只作为父文档和缓存均缺失时的最后手段。
3. 统一元信息字段：标题、作者、年份、DOI、条目 key。
4. 使用 `literature-matrix` 比较研究对象、方法、数据、指标和结论。
5. 只追加新增文献行，不覆盖已有人工确认字段。
6. 区分真实研究缺口 和伪研究缺口。
7. 保存到课题目录下的 `03-文献矩阵/`。

输出建议：

- `literature-review-matrix.csv`
- `gap-analysis.md`
- `topic-suggestions.md`
- 追加日志 或新增行说明

使用的质量检查：

- `证据检查`
- `来源检查`
- `过度声称检查`
- `输出检查`

主要输出：

- 文献矩阵
- 研究缺口分析
- 选题建议

完成标准：

- 每个真实研究缺口均由矩阵中的文献证据支撑。
- 伪研究缺口与证据不足的判断明确分开。
- 不把“当前材料未覆盖”直接写成“领域空白”。
- 未知字段使用 `?`。
- 如已有矩阵，更新必须保持 只追加。

## 工作流 2A：PRISMA 检索、筛选和阅读状态数据库

能力编号：`C07`

目标：在文献综述过程中维护可复查的 PRISMA 主状态，并把少量状态镜像到 Zotero 标签。

1. 在课题目录下使用 `03-文献矩阵/prisma/`。
2. 用 `templates/prisma/search-log.csv` 记录每次检索的数据库、检索式、筛选条件和导出文件。
3. 用 `templates/prisma/records.csv` 维护每条候选文献的 PRISMA 阶段、筛选决策、排除原因、阅读状态、重要性和计划用途。
4. 读书卡使用 `templates/literature/paper-reading-card.md`。全部元数据保存在文末 `## 7. 元数据（折叠）`。
5. 主状态以读书卡文末元数据块和 `prisma-records.csv` 为准；Zotero 只镜像 `rs:*` 标签。
6. 运行 `tools/reading_cards/build_prisma_status_outputs.py` 生成提醒、PRISMA 计数和 `zotero-tag-mirror-plan.json`。
7. 如需要真正写入 Zotero 标签，必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md`，按试运行、人工确认、金丝雀测试和小批量执行。

命令入口：使用 `tools/reading_cards/build_prisma_status_outputs.py`；完整参数和输出约束见 `TOOL_CONTRACTS/04-reading-cards-prisma.md`。

输出建议：

- `prisma-search-log.csv`
- `prisma-records.csv`
- `prisma-reminders.csv`
- `prisma-flow-counts.json`
- `zotero-tag-mirror-plan.json`

使用的质量检查：

- `来源检查`
- `证据检查`
- `Zotero 写入检查`
- `输出检查`

完成标准：

- 每条进入综述的文献保留 Zotero 条目 key 或明确来源。
- 被排除文献有 `Screening Decision` 和必要的 `Exclude Reason`。
- 读书卡有生成时间戳 `generated_at`。
- Zotero 写入只存在于 mirror 计划；未审批前不执行写入。

## 工作流 2B：从 研究缺口到可立项选题

能力编号：`C08`

目标：判断候选研究缺口是否仍有研究空间、是否可能形成明确贡献、以现有条件是否做得出来。

1. 输入 `literature-review-matrix.csv`、`gap-analysis.md`、读书卡或用户给出的候选研究缺口。
2. 使用 `gap-to-topic` 为每个候选研究缺口分配稳定 `gap_id`。
3. 判断这个问题是否仍有研究空间：该研究缺口是否仍未被当前材料充分解决。
4. 判断是否可能形成明确贡献：该研究缺口是否能形成区别于已有研究的贡献。
5. 判断以现有条件是否做得出来：用户数据、实验、模型、指标和时间是否支撑验证。
6. 输出 `topic_dossier.md` 和 `gaps.yml`。
7. 只有 `go` 或 `revise` 的 研究缺口 进入 `research-question-framing`。

输出建议：

- `topic_dossier.md`
- `gaps.yml`

使用的质量检查：

- `证据检查`
- `方法检查`
- `过度声称检查`
- `输出检查`

主要输出：

- 三项推进判断结果：是否仍有研究空间、是否可能形成明确贡献、以现有条件是否做得出来
- 继续推进 / 修改后推进 / 暂缓 / 放弃 决策
- 下一步补读、补证据或收窄边界建议

完成标准：

- 每个研究缺口均有证据来源和推进判断。
- 暂不值得推进的研究缺口标记为暂缓、修改后推进或放弃。
- 不确定内容用 `?` 或“需要核查”。

## 工作流 2C：Zotero 文献库治理

能力编号：`C11`

目标：盘点 Zotero 中文献条目、文献集、标签 和期刊信息，形成可排序的治理矩阵，并输出分类整理建议。

1. 检查 ResearchOS Zotero 父文档是否存在且可读：SQLite 索引和 规范化 PDF 文本 目录。
2. 从 SQLite 导出顶层条目、文献集、标签、附件、PDF 文本状态和 规范化文本路径。
3. 生成字段清单，判断哪些字段对科研、分类和治理有用。
4. 读取文献集，建立文件夹层级路径。
5. 读取 顶层条目，提取元信息、文献集、标签、期刊、年份、DOI 和 规范化文本 可用性。
6. 先选择互斥任务：`content-tags` 只处理文献自身内容标签，`library-structure` 只处理领域和文献集结构；同时需要时分两条管线运行。
7. 内容标签语料必须物理排除当前 tags、collection、项目名称和项目用途；筛选范围只决定 item keys，不构成语义证据。文献库结构任务才可把当前状态放在独立 `current_state` 字段。
8. 当前 ChatGPT/Codex agent 读取任务专属语料并输出结构化结果；`build-plan --task ...` 只校验该任务的字段、命名空间和条目映射。代码不得调用模型 API，也不得依据关键词直接产出语义结论。
9. 内容标签 agent 结果表达“从文献内容可成立的完整目标集合”；随后才与当前 Zotero tags 做确定性对账。已有任意 `#` 标签不等于充分，机器 tags 和 `rs:*` 不计入内容标签充分性；`rs:*` 由集中读书卡状态单独确定。
10. 基于 agent 判断和校验后的矩阵输出治理报告和可审批的只读语义计划。
11. 默认不写入 Zotero；若用户明确要求写入，转到 `POLICIES/ZOTERO_WRITE_POLICY.md`。
12. 写入前必须把语义结果、当前 tags/collection 状态及独立读书卡状态对账为冻结 item mutation plan：绑定来源包哈希，逐条冻结完整版本/tags/collection keys/预期写后状态；全批任一漂移时在任何 PATCH 前整体停止。

命令入口：

- 普通内容治理优先使用 `tools/zotero/build_zotero_library_context_packet.py --profile content`；库结构治理才使用 `--profile library`，并由 `zotero-library-governance` skill 路由到对应任务。
- 父文档维护或排障时，才使用带 `--allow-local-api` 的 Local API 工具。
- 完整参数、输出文件和禁止行为见 `TOOL_CONTRACTS/02-zotero-library-governance.md`；写入边界见 `TOOL_CONTRACTS/03-zotero-web-api-write.md`。

输出建议：

- `zotero_items_raw.json`
- `zotero_field_inventory.csv`
- `zotero_field_inventory.md`
- `zotero_library_matrix.csv`
- `zotero_library_matrix.json`
- `zotero_similar_pairs.csv`
- `zotero_topic_clusters.md`
- `zotero_topic_cluster_plan.json`
- `zotero_governance_report.md`
- `zotero_governance_plan.json`

使用的质量检查：

- `Zotero 父文档检查`
- `Zotero 写入检查`
- `来源检查`
- `输出检查`

主要输出：

- 字段盘点
- 文献治理矩阵
- 主题聚类报告
- 只读治理计划

完成标准：

- 所有建议保留 条目 key 和依据。
- 相近主题、疑似重复和写入建议清楚区分。
- 默认没有任何 Zotero 写入；写入请求已隔离到 Web API 金丝雀测试 流程。

## 工作流 2D：Zotero 新条目分诊

能力编号：`C11`

目标：发现 Zotero 中晚于 ResearchOS 父文档水位线的新顶层条目，准备元数据语料供当前 agent 分诊，再决定是否同步父文档、生成读书卡、加入项目文献集或进入 Zotero 写入审批流程。

该工作流是父文档规则的受控例外：为了发现父文档尚未同步的新条目，可以只读访问 Zotero Local API 顶层条目元数据；不得读取 PDF、附件文件或全文缓存，不得抽取全文，不得写入 Zotero。

1. 检查 ResearchOS 父文档水位线，默认读取 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 中已有顶层条目的最新添加时间。
2. 使用 `tools/zotero/zotero_new_item_monitor.py check` 只读查询 Zotero Local API 顶层条目，找出晚于水位线的新条目。
3. 生成新增条目报告，人工版写入 `docs/reports/zotero-new-item-monitor/new-items-report.md`，机器 CSV/JSON 和状态写入低层留存区 `.researchos/outputs/machine/M-004-zotero-new-item-monitor/`。
4. 当前 ChatGPT/Codex agent 读取 `new-items-latest.jsonl` 和人工报告，结合用户目标判断研究方向、方法、对象、相关性和后续动作；监控代码不执行关键词分类，也不自动生成研究标签或文献集建议。
5. 对需要进入父文档的新条目，使用 `sync-selected` 或 `tools/zotero/zotero_library_index.py sync` 同步元数据到父文档；如后续需要全文，仍按父文档维护流程处理 PDF 文本状态。
6. 用 `monitor_state.jsonl` 追加记录确定性运行状态，保留既有状态。建议状态包括：`detected`、`reported`、`metadata_synced`、`write_approved`、`zotero_written`、`card_created`、`assigned_to_project_collection`、`excluded`、`needs_review`；agent 语义判断进入人读报告或经审批计划，不由监控脚本伪装为机器事实。
7. 若需要真正写入 Zotero 文献集或标签，必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`，完成试运行、人工确认、金丝雀测试、分批执行和回滚计划。
8. 若需要生成读书卡，转入“工作流 1：从 Zotero 到单篇读书卡”；读书卡必须优先使用同步后的父文档和规范化文本，不能因为监控报告存在就直接读取 PDF。

命令入口：使用 `tools/zotero/zotero_new_item_monitor.py`；完整子命令、状态字段和禁止行为见 `TOOL_CONTRACTS/02-zotero-library-governance.md`。

输出建议：

- `docs/reports/zotero-new-item-monitor/new-items-report.md`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/new-items-report.csv`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/new-items-latest.jsonl`
- `.researchos/outputs/machine/M-004-zotero-new-item-monitor/monitor_state.jsonl`

使用的质量检查：

- `Zotero 父文档检查`
- `Zotero 写入检查`
- `来源检查`
- `输出检查`

完成标准：

- 每个新条目至少有 `detected_at` 和 `reported_at` 或明确说明为何未报告。
- 分类建议明确标注“仅基于元数据”，并列出需人工复核项。
- 父文档同步状态、写入审批状态、读书卡状态和项目文献集归属状态至少有一个后续状态或 `needs_review`。
- 未审批前未发生 Zotero 写入；未读取 PDF、未抽取全文、未移动或复制 Zotero PDF。

## 工作流 3：从值得推进的候选选题到研究问题

能力编号：`C08`

目标：把已经判断为值得推进的候选选题转化为可验证研究问题。

1. 输入 `topic_dossier.md`、`gaps.yml`、综述矩阵和 研究缺口分析。
2. 检查候选选题是否已有推进判断。
3. 使用 `research-question-framing` 明确研究对象。
4. 提出核心假设。
5. 识别自变量、因变量、控制变量。
6. 设计验证路径。
7. 判断创新性风险和可完成性。

输出建议：

- `research-question.md`
- `variables-and-hypotheses.md`
- `validation-plan.md`

使用的质量检查：

- `方法检查`
- `证据检查`
- `过度声称检查`
- `输出检查`

主要输出：

- 研究问题
- 变量与假设
- 验证路径
- 与 `gap_id` 的对应关系

完成标准：

- 研究问题可被数据、实验或理论分析验证。
- 变量尽量可观测、可计算或可控制。
- 创新性风险和完成风险已说明。
- 保留 `gap_id` 和推进判断。

## 工作流 4：从研究问题到论文草稿

能力编号：`C09`、`C10`

目标：围绕研究问题组织论文大纲和主要段落。

1. 使用 `methods-design-review` 审查方法路线。
2. 使用 `results-figure-narrative` 组织图表结果。
3. 使用 `paper-memory-builder` 建立 `.paper/` 记忆。
4. 使用 `claim-evidence-audit` 检查摘要、引言、讨论和结论。
5. 使用 `academic-polishing` 做保守润色。
6. 保存到课题目录下的 `05-论文稿件/`。

必须执行的检查：

- 论断-证据 检查。
- 过度声称检查。
- 润色不得改变技术含义。
- 不新增未经证实的结果、图表、引用或结论。

输出建议：

- `manuscript-outline.md`（结构模板：`templates/writing/manuscript-outline.md`）
- `.paper/论断s.yml`
- `.paper/figures.yml`
- `.paper/evidence_artifacts.yml`
- `methods-review.md`
- `claim-evidence-audit.md`
- `polished-sections.md`

使用的质量检查：

- `方法检查`
- `证据检查`
- `过度声称检查`
- `语言检查`
- `输出检查`

主要输出：

- 方法审查
- 图表叙事
- `.paper/` 记忆
- 论断-证据 审计
- 保守润色文本

完成标准：

- 每个关键 论断 均有证据状态和风险等级。
- 结果与讨论 边界清楚。
- 论断、图/表 和 证据材料 能相互引用。
- 修改版不改变技术含义。

## 工作流 5：返修和审稿回复

能力编号：`C10`

目标：把审稿意见转化为逐条回复和稿件修改计划。

1. 如已有稿件，先使用或更新 `paper-memory-builder` 的 `.paper/` 记忆。
2. 使用 `reviewer-response` 拆解审稿意见。
3. 判断每条意见是否需要补实验、补图、补引用或文字修改。
4. 起草回复。
5. 标注稿件修改位置。
6. 执行 论断-证据 检查和 过度声称检查。
7. 确认回复不承诺未完成实验，不改变技术含义。
8. 保存到课题目录下的 `07-审稿回复/`。

输出建议：

- `reviewer-response-table.md`
- `response-letter.md`
- `revision-checklist.md`
- `.paper/revision_history.yml`

使用的质量检查：

- `证据检查`
- `过度声称检查`
- `语言检查`
- `输出检查`

主要输出：

- 审稿回复表
- 回复信
- 修改清单
- 修订历史

完成标准：

- 每条回复对应审稿意见和稿件修改位置。
- 回复中的 论断、图和证据 id 与 `.paper/` 记忆 一致。
- 不伪造新增实验、数据、图表或引用。
- 对无法采纳意见给出技术理由或替代处理。

## 课题输出目录规范

能力编号：`C12`

当某项研究已经有独立课题目录时，优先把输出写入该课题目录。

标准目录结构：

```text
课题目录/
  .research/
  01-课题入口/
  02-证据材料/
  03-文献矩阵/
    prisma/
  04-决策记录/
  05-论文稿件/
  06-报告材料/
  07-审稿回复/
  08-写作材料/
  09-计算工作区/
  10-批注/
```

示例：

```text
<projects_root>\示例课题名称\
  .research/
  01-课题入口/
  02-证据材料/
  03-文献矩阵/
    prisma/
  04-决策记录/
  05-论文稿件/
  06-报告材料/
  07-审稿回复/
  08-写作材料/
  09-计算工作区/
  10-批注/
```

创建入口：使用 `research-project-workspace` skill；完整参数和跨设备路径规则见 `TOOL_CONTRACTS/05-project-workspace.md` 与 `docs/modes/AGENTS.local-research.md`。

跨设备说明：

- `--project-name` 会基于本机 `projects_root` 拼接课题目录。
- 本机配置优先读取 `%USERPROFILE%\.researchos\machine_config.json`。
- 如果没有配置，则默认使用 `00_ResearchOS` 的父目录作为 `projects_root`。
- 仍然支持 `--root` 传入完整路径，适合一次性特殊目录。
- `.research/` manifest 可使用 `templates/project-state/project-manifest.yml`、`templates/project-state/run-state.json`、`templates/project-state/experiment-matrix.yml`、`templates/project-state/data-dictionary.yml` 和 `templates/project-state/open-questions.md`。manifest 必须声明读书卡落点模式：默认 `centralized_links` 对应集中主卡和项目指针；如确需项目本地读书卡，必须显式声明中文本地落点。

使用的质量检查：

- `输出检查`

主要输出：

- 课题根目录
- `.research/` manifest 建议
- 已创建目录
- 已存在目录

完成标准：

- 不覆盖、不移动、不删除既有文件。
- 目录创建结果可复查。
- 读书卡落点与项目登记、manifest 和实际目录一致。
