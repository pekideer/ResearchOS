# ResearchOS Local Research Agent Rules

本文档用于本机长期科研工作流。它补充根目录 `AGENTS.md`，目标是让 agent 在多个会话之间恢复课题上下文、避免误把通用 ResearchOS 框架当成具体课题，并持续围绕当前研究问题推进。

## 适用场景

- 用户说“当前课题”“研究进展”“继续上次”“这 21 篇文献”“阅读卡”“论文进展”“周汇报”“项目记忆”等。
- 用户在 `00_ResearchOS` 通用框架目录中发起任务，但真实材料位于同级或其他课题目录。
- 用户提供或提到尚未明确课题归属的材料；这类材料应进入与 `00_ResearchOS` 平级的 `0.Inbox/`。
- 用户要求从已有 `.research/`、读书卡、综述矩阵、论文草稿或进展文件恢复上下文。

## 上下文恢复顺序

执行具体科研任务前，按以下顺序恢复上下文：

1. 读取当前工作区根 `AGENTS.md`，确认通用安全规则、语言规则、skill 路由和 Zotero 规则。
2. 若用户给出课题路径，优先使用该路径作为 `project_root`。
3. 若用户未给出课题路径，先查找 OneDrive 同步的项目登记文件，再查找本机私有登记文件：
   - `00_ResearchOS\.researchos\active_project.yml`
   - `00_ResearchOS\.researchos\project_registry.yml`
   - `%USERPROFILE%\.researchos\active_project.yml`
   - `%USERPROFILE%\.researchos\project_registry.yml`
4. 路径映射优先读取本机机器配置，再使用同步登记文件中的相对路径：
   - `%USERPROFILE%\.researchos\machine_config.json`
   - 若无机器配置，则默认把 `00_ResearchOS` 的父目录作为 `projects_root`。
   - 未归属入口默认为 `00_ResearchOS` 父目录下的兄弟目录 `0.Inbox/`。
   - 示例格式见 `configs/project_registry.example.yml` 和 `configs/active_project.example.yml`。
5. 若登记文件不存在或不充分，在 ResearchOS 父目录下扫描一级子目录中的 `.research/project_manifest.yml`，并结合最近修改时间、课题名、`reading_plan.md`、`priority-cards/`、`project_overview_and_plan.md` 判断候选课题。
6. 找到候选课题后，必须读取以下文件中存在的部分：
   - `.research/project_manifest.yml`
   - `.research/project_overview_and_plan.md`
   - `.research/material_index.md`
   - `02-literature-matrix/reading_plan.md`
   - `02-literature-matrix/reading-summary-table.md`
   - `02-literature-matrix/gap-analysis-and-technical-route.md`
   - 最近的论文计划、周汇报、审稿回复或 `.paper/` memory。
7. 只有在无法唯一定位课题或候选课题存在冲突时，才向用户提问；提问应具体到候选路径或缺失文件。

## Memory 文件规则

- 本机 memory 只能用于恢复工作上下文，不替代当前文件事实。
- 优先读取轻量索引和摘要，不直接读取大量全文：
  - `00_ResearchOS\.researchos\project_registry.yml`
  - `00_ResearchOS\.researchos\active_project.yml`
  - `%USERPROFILE%\.researchos\project_registry.yml`
  - `%USERPROFILE%\.researchos\active_project.yml`
  - 课题目录 `.research/project_manifest.yml`
  - 课题目录 `.research/project_overview_and_plan.md`
  - 课题目录 `.research/material_index.md`
  - 课题目录 `.paper/` 下的 论断、图表、证据和修订记忆。
- memory 中的信息如果与当前课题文件冲突，以当前课题文件为准，并说明冲突。
- 不在 memory 中保存 API key、Zotero 数据库路径、Zotero storage 路径、PDF 缓存、未公开全文或可恢复敏感数据。

## Project Context Gate

处理文献精读、综述矩阵、gap、论文写作或方法审查前，必须确认：

- `project_root` 是具体课题目录，不是 `00_ResearchOS` 通用框架目录。
- 已读取 `.research/project_manifest.yml` 或明确说明其不存在。
- 如果任务涉及文献，已检查 `01-reading-cards/`、`01-reading-cards/priority-cards/`、`02-literature-matrix/reading_plan.md` 和阅读总表。
- 如果任务涉及论文，已检查 `03-manuscript/`、`.paper/`、项目进展文件或用户指定草稿。
- 输出优先写入具体课题目录，不写入 `00_ResearchOS/.researchos/outputs/`；维护 ResearchOS 框架本身的人读说明写入 `docs/`，共享事实源写入 `corpus/`，执行证据写入 `.researchos/outputs/archive/`。
- 尚未明确课题归属的人工材料写入 `0.Inbox/`，而不是 `00_ResearchOS/.researchos/outputs/`；明确归属后再迁移到具体课题目录。

## 不失焦规则

- 每次开始长任务时，先用 3-6 行中文说明当前课题、当前目标、已知材料、缺口和本轮输出。
- 对大型任务先使用已有读书卡、矩阵、项目计划和 memory，不从 Zotero 或互联网重新发散检索，除非用户要求补充检索。
- 不把“候选文献”当成“已精读文献”；不把“项目设想”写成“已验证结论”。
- 若发现任务正在偏离当前论文或课题阶段，应提醒用户并给出收敛方案。
- 长任务结束时，建议更新或生成课题目录下的 `.research/run_state.json`、`team_tracking.md`、阅读总表或 `.paper/revision_history.yml`，但只在用户要求或任务本身需要时写入。

## Zotero 与本地文件边界

- Zotero 默认只读，遵守根 `AGENTS.md` 和 `POLICIES/ZOTERO_READONLY_POLICY.md`。
- 已有读书卡和课题矩阵优先于重新从 Zotero 搜索。
- 只有当读书卡缺失、PDF 文本缺失或用户要求核查原文时，才调用 Zotero Local API 定位 PDF 和抽取文本。
- 不移动、不复制、不重命名 Zotero PDF；不读取或修改 `zotero.sqlite`。
