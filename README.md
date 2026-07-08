# ResearchOS

ResearchOS 是一个给 Codex 使用的科研助理 agent。它不是论文模板合集，也不是让你再维护一套复杂代码的开发项目；它更像一个可以放在本地长期使用的科研工作台，让 Codex 知道应该怎样读文献、怎样恢复课题上下文、怎样写读书卡、怎样做综述矩阵，以及怎样在论文写作和审稿回复中守住证据边界。

它主要面向这些使用者：

- 正在做论文、课题、基金或长期文献积累的研究生、教师和科研人员。
- 已经在用 Zotero 管理文献，希望 AI 能读取本地文献库、PDF 文本和读书卡的人。
- 经常需要跨会话继续同一个课题，不想每次重新解释背景、文献状态和下一步的人。
- 希望 AI 帮忙做文献精读、综述、选题判断、方法审查、论文润色、结果叙事和审稿回复，但又担心它编造结论或过度拔高的人。

ResearchOS 能做的事包括：

- 为具体课题建立工作区，保存项目 manifest、材料索引、运行状态和下一步计划。
- 从 Zotero 父文档、规范化 PDF 文本或用户提供的材料中准备可追溯上下文。
- 生成单篇读书卡、跨文献综述矩阵、PRISMA 状态、研究缺口分析和选题判断。
- 辅助论文写作、论断-证据审计、方法设计审查、结果与讨论组织、学术润色和审稿回复。
- 把人工批注、碎片想法和项目进展沉淀到本地项目文件中，让后续对话能继续接上。

如果你已经使用 Zotero，ResearchOS 的一个重要价值是把 Zotero 从“文献仓库”接到“AI 可用的科研上下文”。Zotero 仍然负责保存文献、PDF、标签和文献集；ResearchOS 默认只读地使用本地生成的 Zotero 父文档和规范化全文，让 Codex 可以基于真实文献材料工作。公开仓库不会保存你的 Zotero 数据库、PDF、全文缓存或个人读书卡。

ResearchOS 不是具体科研项目仓库。你的真实课题、读书卡、综述矩阵、论文草稿、审稿意见和项目进展应写入自己的项目目录；这个仓库只保存通用的 agent 规则、skills、工作流、质量检查、模板和工具边界。

## Pull 后即用

ResearchOS 的公开仓库首先是一个可直接使用的科研助理框架，而不是要求用户维护的代码开发项目。用户 pull 到本地后，推荐直接在 Codex 中用自然语言调用：

```text
初始化 ResearchOS 本机环境。
为这个课题建立 ResearchOS 工作区：<课题路径>
继续当前课题，先恢复上下文。
为这篇文献生成读书卡。
根据这些读书卡整理综述矩阵和真实研究缺口。
```

第一次使用只需要理解三层结构：

1. ResearchOS 仓库保存通用规则、skills、工作流、质量检查、模板和工具契约。
2. 本地私有配置保存当前项目指针、本机路径映射和个人环境信息，不进入 GitHub。
3. 具体课题成果写入课题目录，不写入 ResearchOS 根目录。

快速开始见 `QUICKSTART.md`；隐私和公开发布边界见 `PRIVACY.md`。

## 项目定位

- 沉淀通用科研助理工作流，而不是保存某篇论文或某个课题的全部材料。
- 通过模板、参考规则和 Codex skills 约束科研表达，减少空泛拔高和无依据推断。
- 优先让 Codex 使用已准备好的语料进行理解、对话、写作和审查；只有缺少本地语料、结构化数据或外部系统操作时才调用工具。
- 在本地实例中，可以通过 ResearchOS Zotero SQLite 索引和规范化 PDF 文本作为文献管理、阅读、综述和治理的父文档；公开仓库不保存真实 Zotero 数据库、PDF 全文或个人读书卡。任何 Zotero 写入都必须另走 Web API 审批流程。

## 与 Zotero 的关系

本项目不替代 Zotero。Zotero 仍然是文献库、PDF、标签、文献集和 note 的主系统。

ResearchOS 的日常 Zotero 访问读取 `corpus/` 共享事实源：

```text
corpus/zotero/M-001-zotero-library/zotero_library.sqlite
corpus/fulltext/zotero-library-normalized/
```

`corpus/` 是本地共享事实源入口。公开 GitHub 仓库默认只保留 `corpus/README.md` 等说明文件；真实 SQLite、规范化全文、读书卡和索引由每个用户在本地生成或维护，并由 `.gitignore` 排除。

Local API 只读读取条目和附件信息主要用于 `tools/zotero_library_index.py sync/watch` 维护父文档：

- 默认 API 地址：`http://localhost:23119/api/`
- 默认 user ID：`0`
- Local API 流程只读，不写入、不删除、不改标签、不移动 PDF
- 如用户明确批准写入，只能通过 `POLICIES/ZOTERO_WRITE_POLICY.md` 规定的 Web API 试运行、人工确认、金丝雀测试 和小批量流程执行
- 不直接读取或修改 `zotero.sqlite`

## 与具体科研项目的关系

具体课题、实验代码、原始数据、读书卡、综述矩阵、研究报告、论文投稿材料和项目治理结果必须放在独立项目目录中。ResearchOS 只保存可复用的方法论、模板、skills、参考规则、工具契约、语料准备流程、必要的机器父文档和 ResearchOS 自身治理记录。

尚未明确课题归属、但需要人工查看和后续归档的材料，放在 `00_ResearchOS` 的平级兄弟目录 `0.Inbox/`：

```text
0.Inbox/
00_ResearchOS/
具体课题目录/
```

`0.Inbox/` 推荐包含 `01-unassigned-literature/`、`02-unassigned-ideas/`、`03-unassigned-materials/`、`04-to-triage/` 和 `.internal/`。明确归属后，再迁移到具体课题目录的 `01-reading-cards/`、`02-literature-matrix/`、`03-manuscript/`、`04-reviewer-response/` 或 `05-ai-code-workspace/`。

## 初始化步骤

普通用户优先按 `QUICKSTART.md` 使用自然语言初始化。只有需要 OCR、Zotero 父文档维护或本地批量语料准备时，才需要运行下面的环境准备命令。

```powershell
cd "$env:USERPROFILE\ResearchOS"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_local_python_env.ps1 -Python "C:\Path\To\python.exe"
```

Python 环境和依赖默认安装到本机 `%LOCALAPPDATA%\ResearchOS\python-envs\zotero-ocr`，不要安装到 OneDrive/同步盘内。同步盘保存 ResearchOS 规则文档、`docs/` 人读说明、`corpus/` 共享事实源、模板、skills、必要脚本和 ResearchOS 自身治理记录；具体科研成果仍应写入用户指定项目路径。如果当前环境不能访问外网，请先使用已有 Python 环境运行不依赖第三方库的检查，或在联网环境中准备依赖缓存后再安装。

## 跨设备路径配置

OneDrive、坚果云、Dropbox、NAS 或本地磁盘在不同电脑上可能挂载到不同盘符或父目录。ResearchOS 内部脚本默认不依赖固定路径。

推荐规则：

1. 在 `00_ResearchOS` 内运行脚本时，脚本会自动定位 ResearchOS 根目录。
2. 使用 `--project-name` 时，脚本优先读取本机配置中的 `projects_root`。
3. 如果没有本机配置，默认把 `00_ResearchOS` 的父目录当作 `projects_root`。
4. 未归属入口固定按 `00_ResearchOS` 父目录拼接 `0.Inbox`，即与 `00_ResearchOS` 平级。
5. 如需显式配置本机路径，优先在用户主目录创建：

```text
%USERPROFILE%\.researchos\machine_config.json
```

内容可参考：

```json
{
  "researchos_root": "C:\\Users\\YOUR_NAME\\ResearchOS",
  "projects_root": "C:\\Users\\YOUR_NAME\\ResearchProjects",
  "zotero_api_base": "http://localhost:23119/api",
  "zotero_user_id": "0"
}
```

模板文件位于 `configs/machine_config.example.json`。不建议把真实机器配置写入通用文档；项目内 `.local/` 也已被忽略，但跨设备时更推荐使用用户主目录下的机器配置。

## 维护 Zotero 父文档

构建或更新 Zotero 同步盘 SQLite 索引库，并可选启用 OCR：

```powershell
python tools\zotero_library_index.py sync
python tools\zotero_library_index.py sync --ocr
python tools\zotero_library_index.py summary --recover-stale
python tools\zotero_library_index.py normalize-text-cache --overwrite
```

从父文档构建阅读/治理上下文包：

```powershell
python tools\build_zotero_library_context_packet.py --item-key ITEMKEY --include-text
python tools\build_zotero_library_context_packet.py --query "radiant cooling" --limit 20
```

## 常用入口

README 只保留入口级命令和文档指针；完整参数、失败处理和禁止行为以 `WORKFLOWS.md`、`TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/00-index.md` 和对应 `RUNBOOKS/` 为准。

| 任务 | 默认入口 | 详细规则 |
|---|---|---|
| 从父文档读取条目或检索上下文 | `python tools\build_zotero_library_context_packet.py --item-key ITEMKEY --include-text` | `WORKFLOWS.md` 工作流 1、`RUNBOOKS/zotero-library-parent-documents.md` |
| Zotero 父文档维护或排障 | `tools/zotero_library_index.py`、`tools/zotero_fast_collection_sync.py` | `RUNBOOKS/zotero-library-parent-documents.md`、`TOOL_CONTRACTS/01-zotero-parent-documents.md` |
| 单篇读书卡与阅读总表 | `paper-deep-reading`、`tools\sync_reading_summary_table.py` | `WORKFLOWS.md` 工作流 1、1A，`RUNBOOKS/reading-card-governance.md` |
| PRISMA 状态与综述矩阵 | `tools\build_prisma_status_outputs.py`、`literature-matrix` | `WORKFLOWS.md` 工作流 2、2A |
| Zotero 文献库治理 | `zotero-library-governance` | `WORKFLOWS.md` 工作流 2C，写入另见 `POLICIES/ZOTERO_WRITE_POLICY.md` |
| 课题输出目录创建 | `research-project-workspace` | `WORKFLOWS.md` 课题输出目录规范 |
| 本机 OCR 环境和 watcher | `tools\build_local_python_env.ps1`、`tools\start_zotero_library_watcher.ps1` | `TOOL_CONTRACTS/01-zotero-parent-documents.md`、`TOOL_CONTRACTS/07-runtime-ocr-local-env.md` |

直接读取 Zotero Local API、定位 PDF 或抽取 PDF 文本不是普通阅读和治理任务的默认入口；只有父文档缺失、过期、路径失效或排障时才使用，且不得读取或修改 `zotero.sqlite`。

Zotero 父文档、规范化全文和主要人读报告使用 `corpus\` 与 `docs\reports\` 入口；`.researchos\outputs\machine\` 是低层机器留存区。

## 目录说明

- `.agents/skills/`：Codex skills，定义科研任务的触发场景、输入、流程、输出和质量规则。
- `tools/zotero_local_api_cli.py`：Zotero Local API 只读排障和 PDF 文本抽取合并入口。
- `tools/zotero_ai_governance.py`：Zotero 文献库治理矩阵、聚类和报告主入口；方向聚合、文献集计划和标签计划由内部实现包承接。
- `tools/create_project_workspace.py`：根据用户指定课题目录或课题名创建编号化输出目录。
- `.agents/utils/`：跨设备路径解析等共享工具。
- `docs/`：人读说明、治理过程文档、能力映射、系统级报告和模式说明。
- `corpus/`：共享事实源和语料，包含 Zotero SQLite 父文档、规范化全文、集中读书卡和索引。
- `configs/`：机器配置示例。真实机器配置建议放在 `%USERPROFILE%\.researchos\machine_config.json`。
- `templates/`：读书卡、综述矩阵、PRISMA 状态库、论文大纲、审稿回复表和 论断-证据审计表模板。
- `templates/reading-summary-table.html`：读书卡同步宽表模板，面向跨文献浏览、评分、PRISMA 状态、人工参阅编号和 Zotero 条目/PDF 点击跳转管理。
- `templates/reading-summary-table.md`：Markdown 备用表模板。
- `templates/prisma-*`：PRISMA 检索日志、筛选状态数据库和 Zotero 标签镜像 规则模板。
- `templates/gap-to-topic-*`：`topic_dossier.md` 和 `gaps.yml` 输出模板。
- `templates/paper-memory-*`：`.paper/` 记忆模板，用于论断、图表、证据和修订历史索引。
- `templates/research-*`：`.research/` 状态模板，用于 project manifest、run state、experiment matrix、data dictionary 和 open questions。
- `docs/references/`：中文/英文学术表达、工程论文逻辑、科研诚信和 Zotero 工作流说明。
- `docs/references/zotero-library-governance.md`：Zotero 文献库治理、分类规则和写入审批规则。
- `.researchos/outputs/machine/`：低层机器留存区。
- `.researchos/outputs/archive/`：外部写入执行证据、审批记录和回滚材料。
- `local-cache/`：本地缓存说明目录。默认不保存 Zotero PDF、密钥或数据库。

## 根目录文档职责表

根目录 Markdown 文档只承担入口、索引、规则和状态职责；具体操作细节优先放在 `docs/`、`RUNBOOKS/`、`POLICIES/`、`templates/`、`.agents/skills/` 或治理产物中。

文档依赖层采用单向链路，禁止在多个根文档中维护同一套规则：

```text
AGENTS.md（最高规则）
  -> README.md（人工导航，不定义新规则）
  -> CAPABILITIES.md（能力编号权威）
  -> TRIGGERS.md（自然语言到能力编号的路由）
  -> WORKFLOWS.md（标准执行流程）
  -> QUALITY_GATES.md（验收标准）
  -> TOOL_CONTRACTS.md / TOOL_CONTRACTS/（仅工具补足时介入）
  -> docs/、RUNBOOKS/、POLICIES/、templates/、.agents/skills/、corpus/（专题细则、执行材料和共享事实源）

PROJECT_STATE.md 只记录状态；EVALS.md 只验证规则；二者不反向定义能力、流程或安全边界。
```

| 文档 | 层级职责 | 允许定义 | 不允许定义 |
|---|---|---|---|
| `AGENTS.md` | 最高规则层 | 身份定位、安全边界、代码写入边界、语言规则、任务分层门禁 | 具体 skill 清单、工具参数、状态流水 |
| `README.md` | 人工导航层 | 项目定位摘要、目录导航、常用入口指针 | 新规则、第二套路由、详细工具契约 |
| `CAPABILITIES.md` | 能力编号层 | `C01-C12`、能力边界、场景入口 | 自然语言触发表达的完整清单、执行细则 |
| `TRIGGERS.md` | 自然语言路由层 | 触发表达、能力编号映射、优先 skill、默认输出 | 质量标准正文、工具契约正文 |
| `WORKFLOWS.md` | 执行流程层 | 标准步骤、任务串联、输出建议 | 工具实现细节、安全策略全文 |
| `QUALITY_GATES.md` | 验收层 | 证据、来源、方法、语言、输出和治理检查 | 能力清单、自然语言触发词 |
| `TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/` | 工具边界层 | 工具用途、输入输出、允许/禁止行为、风险分级 | 科研结论、能力定位、用户路由 |
| `RUNBOOKS/` | 专题操作层 | 复杂流程细则和排障步骤 | 全局最高规则 |
| `POLICIES/` | 策略层 | 安全、科研诚信、写入审批、语言策略 | 工作流状态流水 |
| `templates/`、`.agents/skills/` | 执行材料层 | 输出模板、skill 输入流程输出 | 根目录级治理规则 |
| `PROJECT_STATE.md` | 状态记录层 | 当前阶段、已完成、下一步 | 新规则、新能力、新安全边界 |
| `EVALS.md` | 评测层 | eval 输入、预期输出、失败判定 | 新工作流或工具契约 |

能力编号的权威索引见 `CAPABILITIES.md` 的“统一能力编号”；触发表达、工作流和质量检查均应使用同一编号互相定位。

## 推荐阅读顺序

1. `AGENTS.md`：确认最高规则、安全边界和任务分层。
2. `CAPABILITIES.md`：确认能力编号和能力边界。
3. `TRIGGERS.md`：把用户自然语言映射到能力编号、skill 和工作流。
4. `WORKFLOWS.md`：执行标准流程。
5. `QUALITY_GATES.md`：执行验收。
6. 需要工具时再读 `TOOL_CONTRACTS.md`、`TOOL_CONTRACTS/` 和对应 `RUNBOOKS/`、`POLICIES/`。
7. 需要了解当前治理进度时再读 `PROJECT_STATE.md`；它只提供状态，不提供新规则。

## 自然语言调用

你不需要记 skill 名称，可以直接描述任务。常见表达、能力编号、优先 skill、工作流和默认输出统一维护在 `TRIGGERS.md`。

## 安全边界

- 全局安全规则见 `AGENTS.md`。
- Zotero 写入审批见 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。
- 读书卡、PRISMA、输出资产和 Obsidian 规则分别见 `RUNBOOKS/reading-card-governance.md`、`RUNBOOKS/prisma-literature-screening.md`、`RUNBOOKS/output-asset-governance.md` 和 `RUNBOOKS/obsidian-zotero-codex-governance.md`。
- 科研结论、来源、语言和输出验收见 `QUALITY_GATES.md`。

## 后续扩展计划

1. 用更多真实 Zotero 文献验证搜索、读取、PDF 定位和文本抽取流程。
2. 继续用扫描版 PDF 验证可选 OCR 流程，补充 Tesseract 安装和语言包排查说明。
3. 增加跨项目的文献矩阵索引。
4. 增加面向具体学科或论文类型的扩展 skills。
5. 增加读书卡与 Zotero note 的手动回填规范，仍不由默认脚本自动写入 Zotero note。
