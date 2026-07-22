# Project State

## 当前阶段

ResearchOS 是 Codex 科研助理运行框架。它维护科研场景、触发规则、质量标准、上下文恢复、语料准备流程和必要工具边界；具体科研成果写入用户指定项目路径。

当前治理重点是 LLM-first 行为闭环：ResearchOS 代码只准备语料、执行确定性格式/状态校验和受控外部读写；研究语义判断由当前 ChatGPT/Codex agent 完成。Zotero 全库 PDF 文本、期刊词典和读书卡流水线继续作为可恢复的语料准备层。

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
| 本机运行区 | `.researchos/`，只保存可清理运行材料和待晋升详细证据 |
| 项目持久状态 | 项目 `.research/`，保存 manifest、状态、交接、决策、审批和精简审计 |

## 当前边界

- Zotero 默认只读；写入 Zotero 必须走 Web API 审批、试运行、金丝雀测试、分批执行和回滚计划。
- 本地共享事实源默认使用 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`；公开仓库不提交真实父文档和全文。
- 本地集中读书卡主库可使用 `corpus/reading-cards/cards/`，索引位于 `corpus/reading-cards/indexes/`；公开仓库不提交真实读书卡和索引。
- 系统级人读说明和报告进入 `docs/`。
- 具体项目读书卡、综述矩阵、研究报告、论文草稿和审稿回复进入用户指定项目工作区。
- 本机机器产物、缓存、日志和详细执行暂存进入 `.researchos/`，不得成为唯一正式证据。
- 项目审批、执行结论和精简回滚凭据进入项目 `.research/`；全库共享语料发布审计随共享语料保存。
- 未归属人工材料进入与 `00_ResearchOS/` 平级的 `0.Inbox/`。

## 当前已稳定能力

- `C01-C12` 能力编号、自然语言触发路由、标准工作流、质量门禁和工具契约层。
- Zotero 父文档与规范化全文读取。
- 集中读书卡命名、YAML 头部、项目索引和期刊等级词典映射。
- Zotero governance 主入口：`tools/zotero/zotero_ai_governance.py`；内容标签与库结构使用分离证据/schema，只生成 agent 语料包并校验结果，不调用语言模型 API。
- Zotero 通用 tags/collection membership 写入入口：`tools/zotero/write/execute_zotero_item_mutation_plan.py`；审批快照发生任一漂移时全批零写入。
- 高风险 Zotero 写入工具审批隔离：`tools/zotero/write/`。
- Zotero 读书卡标注闭环：集中读书卡为主版本，Zotero 子笔记经审批发布，PDF annotation 只读回流并进入受控生成区。
- Zotero 全库摄取入口：`tools/reading_cards/zotero_library_pipeline.py` 支持全库、增量和显式 item key；默认先写本机 `M-006` staging，后续语义处理和审计沿用同一 staging，共享 `corpus/` 发布仍需 Corpus Publisher 独立完成。
- Zotero 条目到语义读书卡入口：`zotero-reading-card-pipeline`；代码只准备首页证据，单位由 `semantic-packet -> 模型/人工判断 -> semantic-apply -> audit --strict` 形成，未经语义结果不得作为完成或发布。
- 单篇精读与 Zotero 批量编排已分层：`paper-deep-reading` 负责单篇科研语义，`zotero-reading-card-pipeline` 负责范围、语料、staging 和审计；统一 `researchos-reading-card/v2` 契约校验正文结构、来源回执和条件化第 6 节，Zotero note 计划 schema v2 冻结同一契约回执。
- 网络分流：Zotero Local API 始终直连；EasyScholar 和经审批的 Zotero Web API 使用各电脑自己的环境变量或未跟踪 `.local/machine_config.json`，共享代码不保存代理 host/port，Web API 无代理时停止。
- 23 个独立 skill；新增 `zotero-incremental-curator` 编排增减/重键、精读卡、中文单位、note 互斥和 metadata 计划，点子、检索、深度报告、立项判断和研究问题边界保持分开。
- 唯一上下文恢复链：`active_project.yml` 定位、`project_manifest.yml` 稳定事实、`run_state.json` 当前快照、`run-log.jsonl` 最小历史。
- 精简根规则和紧凑路由：`AGENTS.md` 只保留最高约束，`TRIGGERS.md` 使用单表路由，专题边界按需读取。
- 首次运行先做只读就绪检查；普通科研任务不以 Python、OCR 或 Zotero 配置为前置条件。
- OCR 依赖缺失时默认停止，只有用户明确批准并传入 `--install` 才安装；阅读汇总使用静态相对链接，不依赖本地打开服务。
- 阅读汇总的主题相关性只接受用户或当前 agent 的明确判断，缺失时保持为空，不从标签或项目默认值推断。
- 跨端本地门禁：终端分域角色、Git pre-push guard、共享 corpus 快照、项目 handoff、共用项目写门禁和 manifest-committed corpus 发布器已实现。真实 corpus 金丝雀 `corpus-74add221724a0848` 已在发布端完成 4 文件原子发布、manifest 回读、SQLite 检查和两条读书卡严格审计；同步盘进程未运行，跨端同步后复核仍待完成。

## 下一步

1. OneDrive 同步恢复后，对 release `corpus-74add221724a0848` 只执行 manifest/hash/SQLite 回读，最好再由另一终端只读核验；不得重复 `apply`。
2. 选择一个真实项目执行不删除旧文件的换端金丝雀，验证所有权交出、接管、写前检查和状态回写。
3. corpus 跨端复核通过后，提炼 `20260720-card-dedup-repair` 最小证据并写关闭标记；完整修复备份按默认 30 天保留期治理，迁移前不删除旧文件。
