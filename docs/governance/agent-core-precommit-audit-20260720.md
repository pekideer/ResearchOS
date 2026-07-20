# ResearchOS Agent Core 提交前深度审计

- 日期：2026-07-20
- 范围：Agent Core 规则、能力路由、skills、工具契约、关键代码、测试与跨端接力
- 审计性质：框架治理；未连接或写入 Zotero，未修改项目成果或项目 `.research/`；经单独批准对真实 `corpus/` 执行一次冻结计划金丝雀

## 1. 总体结论

本轮修复后，Agent Core 的 LLM-first 定位、C01-C12 路由、Zotero 读写隔离、完整本机 staging、受角色约束的 corpus 发布、跨端角色与项目 handoff 主链保持一致，未发现仍需阻止本地提交的 P0/P1 实现缺口。Python 编译、差异格式检查和 120 项单元测试通过。

当前结论是“可进入人工提交审阅”，不是“所有外部权限已经由本地代码替代”。共享 `corpus/` 已有 Corpus Publisher 发布器，已识别项目写入口已接入共用 `check-write`，直接 corpus 写入入口已改为 staging 或 fail-closed。真实 corpus 金丝雀已在发布端完成并通过本机回读；仍需外部保证的是远端 Git 权限、同步盘服务端单写者权限、同步后的跨端复核、真实项目换端金丝雀和每次 Zotero Web API 审批。

## 2. 智能体可实现的功能

| 能力 | 可实现功能 | 主入口 |
|---|---|---|
| C01 | 将模糊、多目标请求拆成可执行能力路线 | `semantic-route-planner` |
| C02 | 恢复当前课题、构建项目地图、说明当前位置和下一步 | `project-map-builder` |
| C03 | 处理人工批注收件箱，映射并审查修改意见 | `human-annotation-inbox` |
| C04 | 捕获碎片想法，建立 IDEA 资产并做初步潜力判断 | `idea-to-research-potential` |
| C05 | 读取/维护 Zotero 父文档、规范化全文和只读上下文 | `zotero-literature-access` |
| C06 | 单篇精读、集中读书卡、标注回流和受控 note 计划 | `paper-deep-reading`、读书卡相关 skills |
| C07 | 检索路线、PRISMA、跨文献矩阵和深度研究情报报告 | 检索、矩阵、情报报告 skills |
| C08 | 从候选缺口判断立项价值，再凝练研究问题、假设和变量 | `gap-to-topic`、`research-question-framing` |
| C09 | 方法设计审查、论断-证据审计和论文记忆 | 方法、证据、论文记忆 skills |
| C10 | 结果叙事、学术润色和审稿回复 | 写作相关 skills |
| C11 | Zotero 库治理、项目文献集计划、新增条目完整治理 | Zotero 治理相关 skills |
| C12 | ResearchOS 规则、工具契约、命名、输出和功能闭环治理 | 工作流 0C、治理 runbooks |

跨能力的基础功能还包括：本机运行区生命周期、OCR 显式安装门禁、终端分域角色、共享 corpus 快照、manifest-committed corpus 发布、项目写入权交接与写前检查、Git pre-push 防误操作，以及经审批的 Zotero Web API 写入与回滚工具。

## 3. 代码与语义的作用边界

| 层 | 允许职责 | 禁止越界 |
|---|---|---|
| 当前 ChatGPT/Codex agent | 理解研究问题；判断主题、方法、对象、证据含义、单位对应、中文机构名、研究缺口、collection 用途和 tags；写作与审查 | 不编造文献、数据、实验、引文或结论；论断不得超过证据 |
| 确定性代码 | 读取/规范化语料；处理路径、哈希、版本、状态和结构化格式；生成证据包；校验并应用 agent 结构化结果；执行受控外部读写 | 不调用通用模型 API；不以关键词、评分或聚类脚本替代科研语义判断；不把候选直接提升为结论 |
| 高风险写入工具 | 在具体冻结计划、审批、金丝雀、版本检查、回读和回滚约束下执行窄范围写入 | 不因脚本存在、历史批准或 dry-run 存在而自动取得本轮授权 |

本轮新增的 DOI 规范化、中文单位显示格式、卡片/note 互斥、版本快照和 handoff 锚点比较均属于确定性校验；实际单位翻译、keeper 选择、项目用途和科研结论仍由 agent 或用户判断。

## 4. 必须遵守的规则与写入边界

1. 默认使用简体中文；代码、路径、字段和必要专名保留原文。
2. 区分事实、推断、建议、假设和需要核查项；不编造科研材料。
3. 不读取、打印或修改 `.sandbox-secrets`；公开仓库不含真实课题、Zotero 数据、全文、PDF、密钥、本机配置或个人缓存。
4. Zotero 默认只读；不得直接读取/修改 `zotero.sqlite`，不得移动、复制、删除或重命名 Zotero PDF。
5. Zotero 写入只走 Web API，且每次都需要具体计划、人工确认、代理检查、金丝雀、分批、回读和回滚；删除还需单独批准。
6. 文件迁移、删除、批量改名、系统设置和外部 API 写入需要单独授权；本轮授权仅覆盖 Agent Core 最小优化。
7. 具体科研成果写入项目工作区；共享事实源进入 `corpus/`；项目持久控制面进入项目 `.research/`；可重建运行材料进入本机 `.researchos/`。
8. 长期同步文件只使用相对路径、占位根或 `root_key + project_relative_path`；本机绝对路径只进入机器私有配置和机器内部记录。
9. Framework Maintainer、Corpus Publisher、Project Writer、Zotero Writer 分域授权；一种角色不自动取得另一种写入权。
10. ResearchOS 自修改必须有当前任务明确授权，并遵循必要性、现有工具关系、文档替代、最小改动和风险说明。本轮已获得该授权。
11. 当前会话只在 Agent Core 工作区及产品指定临时/可视化位置内写入；越出受管可写范围、运行受限外部动作或执行破坏性操作时必须另行申请权限。
12. “提交前检查”不等于授权 Git commit/push。本轮只修改并验证工作区；暂存、提交和推送需用户继续明确要求。

## 5. 跨端接力实现

1. Agent Core 通过 Git 对齐；本地 `terminal_role.json` 区分 framework/corpus/Zotero 角色，pre-push hook 防止 follower 误推送。
2. Shared Corpus 通过 `corpus_snapshot.py` 计算内容哈希；SQLite、全文、读书卡和索引先写本机 staging，再由唯一 Corpus Publisher 按冻结计划发布。跨 Junction 采用逐文件原子替换、最终 release manifest 提交和逐文件回读的语义原子模型。
3. 项目通过 `.research/handoff.yml` 保存项目身份、状态修订号、活动写入端、Agent Core commit、corpus 快照、最近完成步骤和下一步。
4. 原端 `release` 必须显式记录最新 `last_completed` 与 `next_action`；新端 `claim` 只有在目标终端、framework commit、snapshot ID 和 content hash 全部匹配时才可计划接管。
5. `check-write` 同时检查活动写入端和实时 commit/corpus 锚点；漂移时停止，不再静默覆盖交接锚点。
6. 已识别的项目写入口在首个写操作前调用共用门禁；新项目初始化后立即 bootstrap handoff，旧项目缺少 handoff 时停止。
7. Zotero Writer 权限与项目接力分离；换端不恢复任何历史 Zotero 写入批准。

当前限制：本地 hook 不能替代远端分支保护；同步盘跨 Junction 不提供单一文件系统事务，因此消费者必须以 release manifest 回读结果为准。真实换端仍需按“交出—同步—只读核对—接管—单条金丝雀”执行。本轮真实 corpus 金丝雀已在发布端提交，但执行时 OneDrive 同步进程未运行，因此不能把本机验证表述为跨端同步闭环。

## 6. 本轮发现与修复

| 等级 | 问题 | 修复结果 |
|---|---|---|
| P1 | `claim` 会用新端实时锚点覆盖交出时锚点，无法阻止 commit/corpus 漂移 | 改为严格比较并阻断；`check-write` 同样校验实时锚点 |
| P1 | `release` 不更新最近完成步骤和下一步，handoff 可长期保留旧进度 | 两字段改为 release 必填，并纳入 handoff 校验 |
| P1 | `run` 默认写 staging，但后续 `audit/semantic-*` 默认回到共享 corpus，形成资产集错位 | 非 run 命令在 staging 存在时自动沿用同一资产集；不完整 staging 直接阻断 |
| P1 | staging 已有卡片时不再吸收共享主库新增卡，可能形成身份重复 | 按 item key 补入缺失卡，同一 item key 不复制第二张 |
| P1 | staging 的全文/OCR/规范化路径仍可能回落到真实 corpus | `run` 的完整文本链改写到 `M-006/staging/corpus/fulltext/`，直接共享写入 fail-closed |
| P1 | 共享 corpus 缺少受 Corpus Publisher 约束的发布闭环 | 新增冻结计划、源/基线哈希、SQLite 检查、逐文件原子替换、最终 manifest、verify 和精确 rollback |
| P1 | 项目写入口没有统一执行 `check-write` | 新增共用项目写门禁并接入工作区、材料、语料包、PRISMA、阅读总表、期刊/元数据和 PDF 抽取入口 |
| P1 | 多处旧规则仍允许向项目 `.research/fulltext_cache/` 写缓存 | 统一为旧目录只读兼容；新增派生文本进入 `02-证据材料/全文缓存/` 或本机 staging，不迁移、不删除旧文件 |
| P1 | 文档把 staging 更新表述成集中主库完成 | 增加 `corpus_publication_required` 状态，并统一 workflow、quality gate、skill 和 tool contract |
| P2 | `target_terminal` 在 claim 后仍保留为当前终端，状态语义不清 | claim 后清空 target，活动写入端由 `active_writer_terminal` 单独表示 |
| P2 | Runtime README 仍声称存在已删除的本地 HTML 服务 | 更新为当前 runtime/role/snapshot/handoff 工具范围 |
| P2 | README 仍称语义聚合由内部实现包承担 | 改为当前 agent 判断、代码校验结构化结果 |
| P2 | 治理状态仍称跨端角色与 handoff 尚未实现、skill 数为 22 | 更新为当前已实现边界、剩余外部强制缺口和 23 个 skill |

## 7. 功能闭环与剩余缺口

| 功能链 | 入口 | 核心逻辑 | 输出/失败处理 | 测试/文档 | 结论 |
|---|---|---|---|---|---|
| LLM-first 路由 | `TRIGGERS.md` | C01-C12 → workflow/skill | 不明确时才进入语义路由 | 治理测试、根文档 | 闭环 |
| Zotero 只读父文档 | Local API/父文档工具 | 只读同步、全文状态、规范化缓存 | Local API/PDF/OCR 错误显式保留 | 专题契约与测试 | 闭环 |
| 增量读书卡 staging | pipeline `run` | 本机 DB/卡片 staging、版本/身份/语义校验 | 不完整 staging 阻断，明确待发布 | pipeline 测试、工作流 1C/1D | 本机闭环 |
| 共享 corpus 发布 | `publish_corpus.py` | 冻结差异、角色/基线/SQLite 校验、manifest-committed 发布 | verify 与精确 rollback；未批准时只生成计划 | 专题契约与 3 项测试 | 发布端真实金丝雀通过；同步后跨端复核待执行 |
| Zotero note/metadata 写入 | `tools/zotero/write/` | 计划、金丝雀、版本、回读、回滚 | 任一失败停止 | 写入契约与测试 | 审批后闭环 |
| 跨端项目接力 | `project_handoff.py`、`project_write_guard.py` | bootstrap/release/claim/check-write 与目标越界检查 | 状态、锚点、所有权或路径漂移阻断 | handoff/guard 测试与契约 | 本地闭环；真实换端金丝雀待执行 |
| Framework 推送权限 | terminal role + pre-push | maintainer 检查 | follower 本地阻断 | 角色测试 | 本地闭环；远端保障外置 |

## 8. 验证证据

- `python -m compileall -q tools tests`：通过。
- `git diff --check`：通过。
- `python -m unittest discover -s tests`：120/120 通过。
- 完整测试需在正常本机临时目录权限下运行；受限 Windows 沙箱会对 `tempfile` 产生 `PermissionError`，该现象已通过正常权限复测排除为代码失败。
- 脱敏临时目录已完成 corpus apply、verify、角色拒绝和 rollback 金丝雀。
- 真实 staging 的 4 文件冻结计划已获单独批准并发布：SQLite、2 张读书卡和主索引；0 个计划外文件、0 删除。release ID 为 `corpus-74add221724a0848`，计划哈希为 `74add221724a08485c61ec87390680fd19f19802b7ff3418e6af5e85c9b370e3`。
- 发布后 manifest 4/4 文件大小和 SHA-256 回读一致，SQLite `PRAGMA quick_check` 通过；条目 `9AV3KVW9`、`59EFV4W9` 的数据库、卡片、主索引和 pipeline 状态严格审计通过。
- 首次受限执行在 Junction 目标创建临时文件时异常循环，未改变 corpus 或 manifest；中断现场保留在本机 A-004 archive 的 `corpus-74add221724a0848-interrupted-sandbox/`。获目标目录写权限后按同一冻结计划成功执行，未启动 OneDrive 进程。
- 本轮未安装依赖、未访问 Zotero Web API、未执行 Zotero 写入、未修改真实项目工作区；尚未完成同步后或另一终端的只读复核。

## 9. 过程资产与审计文件治理

本轮在提交前对本机运行区执行了只读归属、体积和引用审计，并重新生成 `.researchos/cleanup-plan.json`。现行保留策略给出的结果是 `candidate_count: 0`，因此未应用清理、未删除文件。

| 资产 | 数量/体积 | 当前归属 | 处理结论 |
|---|---:|---|---|
| `.researchos/audit-staging/20260720-card-dedup-repair/` | 47 文件，约 111.4 MB | 读书卡去重修复的工作副本、备份和 SQLite | 缺少 `cleanup-state.json`；发布端金丝雀虽已通过，但跨端同步复核和最小证据晋升未完成，继续保护 |
| `.researchos/audit-staging/cscec3-sync-governance-20260720/` | 11 文件，约 99.6 KB | 项目治理前后备份 | 缺少关闭与晋升标记，继续保护 |
| `.researchos/outputs/machine/M-006-zotero-ingestion-pipeline/` | 1662 文件，约 40.6 MB | 当前 staging、快照和 corpus 冻结发布计划 | 发布端金丝雀通过；同步后复核完成前继续保护 |
| `.researchos/outputs/machine/M-005-reading-card-annotation-sync/` | 41 文件，约 368 KB | annotation/note 本机审计与备份 | 与外部写入证据有关，完成晋升核对前保留 |
| `.researchos/outputs/archive/A-003-reading-card-note-publish/` | 85 文件，约 357 KB | 已执行 Zotero 写入的回读和 rollback 证据 | 不作为提交内容；任务闭环和必要摘要晋升前保留 |
| `.researchos/outputs/archive/A-004-corpus-publication/` | 成功发布包 7 文件、约 27.6 MB；中断现场 1 文件、约 5.8 KB | 本次 corpus 金丝雀的冻结计划、发布清单、完整修复前副本和 rollback 计划 | 不作为提交内容；跨端同步复核和最小证据晋升前保留 |
| `.researchos/tmp/` | 4 个普通文件，约 23.9 KB，另有空目录 | 当日测试、探针和一次性执行脚本 | 未满 7 天；只有获得精确保留期覆盖批准后才能删除 |

已识别但尚未获保留期覆盖批准的精确候选：

- 7 个空测试/Office 临时目录：`openai-docs-cache/`、`pipeline-fixture/`、`precommit-unittest/`、`soffice_convert_r8k817l3/`、`soffice_profile_9ucq7olh/`、`test-runtime/`、`test-temp/`。
- `manual-probe/`：2 个文件，共 6 bytes。
- `__pycache__/`：1 个可再生 `.pyc`，13,822 bytes。
- `execute_approved_note_deletes.py`：10,089 bytes；Git 跟踪文件中无引用，未命中凭据模式，执行审计已进入 `A-003`，但仍受 7 天保留期约束。
- 孤立 SQLite sidecar：`zotero_library_20260720_readonly.sqlite-wal` 为 0 bytes、`.shm` 为 32,768 bytes，对应主数据库不存在；因位于 `audit-staging/` 顶层而被策略判为受保护的无效 scope。

正式提交范围只包括 Agent Core 规则、契约、skill、工具、测试、模板和本审计报告；`.researchos/`、真实 corpus、项目材料、运行快照和 rollback 证据均不进入 Git。

## 10. 提交建议

当前可进入人工 diff 复核、暂存和提交。允许表述为“发布端真实 corpus 金丝雀已发布并通过本机回读”，不得表述为“跨端同步闭环完成”。rollback、项目换端金丝雀、Git 提交和推送均需相应的后续明确授权。

## 11. 后续同步复核恢复入口

恢复本次工作时先读取本节和 `PROJECT_STATE.md`，不要重新生成计划或重复执行 `apply`。

- 已提交 release：`corpus-74add221724a0848`
- 冻结计划：`.researchos/outputs/machine/M-006-zotero-ingestion-pipeline/corpus-publication-plan.json`
- 共享提交记录：`corpus/zotero/M-001-zotero-library/current-corpus-release.json`
- 本机发布与回滚证据：`.researchos/outputs/archive/A-004-corpus-publication/corpus-74add221724a0848/`
- 只读复核命令：`python tools/runtime/publish_corpus.py verify --corpus-root corpus`
- 复核重点：release ID、plan hash、4 个文件哈希、SQLite `quick_check`，以及 `9AV3KVW9`、`59EFV4W9` 的数据库—卡片—主索引一致性。
- 完成条件：OneDrive 同步完成后本端再次回读通过，并尽可能由另一终端对同一 manifest 只读核验；在此之前不得删除 `20260720-card-dedup-repair`。
