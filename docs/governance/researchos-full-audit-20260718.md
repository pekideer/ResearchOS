# ResearchOS 全面代码、规则与过程文件审计（2026-07-18）

## 1. 审计范围与边界

本次审计覆盖根级规则与状态文档、`TRIGGERS.md`、`WORKFLOWS.md`、`QUALITY_GATES.md`、`TOOL_CONTRACTS/`、本轮变更涉及的 skills、Python 工具和测试，以及 `.researchos/outputs/`、`.researchos/tmp/` 和未跟踪过程文件。

本次没有读取或修改 `.sandbox-secrets`，没有连接或写入 Zotero，没有移动 Zotero PDF，也没有修改外部项目工作区。高风险写入脚本只做静态审查。

## 2. 总体结论

- P0：0 项。
- P1：原发现 3 项，现已全部治理并通过回归测试；当前未解决 P1 为 0 项。
- P2：原发现 3 项，现已全部治理；当前未解决 P2 为 0 项。
- Python 语法检查通过。
- 沙箱外完整单元测试：73/73 通过；专项 P1/P2 回归测试：20/20 通过。
- 已跟踪 Markdown 相对链接检查：0 个失效链接。
- `git diff --check`：通过。
- 公开候选文件未发现真实 API key、本机代理值、真实 Zotero 数据库、PDF 或规范化全文进入 Git 候选范围。

当前规则、实现、测试、契约和治理状态已经形成一致的提交候选。过程性归档继续留在被忽略的 `.researchos/outputs/`，不进入公开提交。

## 3. P1 治理结果

### P1-1 项目文献集互斥规则已落实到执行脚本

- 规则证据：`.agents/skills/project-collection-overlay/SKILL.md` 与 `QUALITY_GATES.md` 已要求 `00-待分配-triage` 和 `01-07` 稳定用途严格互斥，并要求“先加入并核验，再移出 00”。
- 实现结果：`execute_project_collection_overlay_write.py` 统一使用互斥分配预览和写后条件；单条、金丝雀和批量路径均先加入并读回核验全部目标用途，再移出本项目 triage，且保留无关 collection。
- 安全边界：批量回滚计划在首个外部写入前落盘；加入阶段失败立即停止，不执行 triage 移除；最终同时检查目标缺失和 triage 残留。
- 测试证据：新增 4 个完全离线测试，覆盖先加后移、无关 collection 保留、混合目标拒绝和加入阶段失败停止。

### P1-2 `audit --strict` 已改为活跃 item key 集合审计

- 实现结果：严格审计按 `active_keys - state_keys`、`active_keys - affiliation_keys` 和 `active_keys - card_keys` 分别计算缺失项，新增 `missing_affiliation_state`，历史或软删除记录不能抵消活跃条目的缺失状态。
- 测试证据：新增历史状态行掩盖、缺失单位状态和缺失卡片的集合级回归用例。

### P1-3 语义结果与批量卡片写入已具备异常回滚

- 实现结果：新增本地文件写入回滚守卫；读书卡、单位词典和主索引在写前保存原内容，新建文件记录为空状态。SQLite 保持事务到最后提交，任一异常会关闭并回滚数据库，同时恢复已替换文件或移除本轮新建文件。
- 并发边界：写入仍受现有 writer lock 保护；若文件恢复本身失败，会提升为明确的“不完整回滚”错误，不会静默报告成功。
- 测试证据：故障注入测试验证已有文件恢复和本轮新建文件删除。

## 4. P2 治理结果

### P2-1 新工具契约登记已补齐

- `TOOL_CONTRACTS/00-index.md` 已登记 `zotero_library_pipeline.py`。
- `TOOL_CONTRACTS/04-reading-cards-prisma.md` 已移除重复的 `card_common.py`，并补充语义证据包、受控本地写入和启发式候选不得发布的边界。

### P2-2 当前治理状态已同步

- `current-governance-status.md` 已同步为 22 个独立 skill，并登记 `zotero-reading-card-pipeline` 的职责和稳定工具入口。

### P2-3 Web API 代理解析已统一

- 共享 `zotero_web_api.py` 现在提供单一 `normalize_proxy()`；项目文献集执行器复用该 helper，不再维护第二份规范化逻辑。
- 无 scheme 的本机配置会补为 `http://`；审计输出仍只保留脱敏来源与 host/port，不打印凭据或完整代理 URL。
- 新增代理来源和无 scheme 规范化测试。

## 5. 已完成的过程文件整理

| 原位置 | 新位置 | 分类 |
|---|---|---|
| `docs/governance/project-folder-governance-20260711/` | `.researchos/outputs/archive/A-004-project-folder-governance/20260711-three-project-migration/` | 外部项目文件迁移的计划、执行、哈希与回滚证据 |
| `.researchos/outputs/machine/deep-reading-checkpoints/` | `.researchos/outputs/machine/M-006-zotero-ingestion-pipeline/deep-reading-checkpoints/` | 全文摄取/精读检查点 |
| `.researchos/tmp/*` | `.researchos/outputs/machine/M-099-legacy-task-process-files/` | 历史任务专用中间文件，待后续按项目迁出或另行审批清理 |
| 本轮 `.tmp/pycache-audit`、`.tmp/test-temp` | 已清理 | 可再生测试缓存 |

上述归档目录均被 `.gitignore` 排除，不进入公开提交。`M-099` 只用于保留此前散落的中间文件，不是新的稳定功能入口。

## 6. 提交准备

本轮建议作为一个治理提交候选暂存以下相互依赖的内容：

- ResearchOS 自修改门禁、读书卡流水线和项目文献集互斥规则。
- 对应的工具实现、共享 helper、契约、runbook、状态入口和离线测试。
- Local API 强制绕过代理及 Web API 代理配置一致性修复。
- 本审计报告。

过程性归档、机器运行物和测试缓存不暂存。当前仅完成提交准备，不执行 commit、push 或任何 Zotero 写入。
