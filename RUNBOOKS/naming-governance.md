# Naming Governance

本手册集中管理 ResearchOS 中不同对象的命名规则。目标是避免读书卡、点子、课题目录、科研助理产出文档、Zotero 项目文献集、机器留存和过程记录各自形成分散规则，导致文件混乱、索引断裂和后续脚本难以定位。

## 1. 总原则

- 可读名称优先于机器 key；机器 key 放在元数据、机器表或审计字段。
- 同一类对象只保留一个主命名规则；现有文件按主命名规则审计和修正。
- 人工文档名称应说明主题和用途，机器产物名称应说明编号、能力和格式。
- 日期使用对象首次建立日期，不用迁移日期替代。
- Zotero 条目 key 不作为人读文件名的主显示名，除非同名冲突且无更好短名。
- 新增命名规则前，先检查本手册、`RUNBOOKS/output-asset-governance.md` 和 `RUNBOOKS/obsidian-zotero-codex-governance.md`。

## 2. 集中读书卡

集中读书卡主库固定为：

```text
corpus/reading-cards/cards/
```

读书卡文件名统一为：

```text
RC-###_ZoteroKey_短题名.md
```

短题名用于文件定位，不替代卡内完整论文题名。短题名应优先使用中文可读表达，保留能区分文献的对象、方法或核心变量；英文文献不得直接使用机器截断的英文长题名。短题名中不写 `精读`、`阅读卡`、日期等过程词，除非作者名可帮助区分同主题文献，可以保留第一作者姓氏。

每张主卡必须包含 YAML 头部，至少记录 `card_id`、`zotero_key`、`project_id`、`title`、`fulltext_status`、`source` 和 `normalized_at`。

## 3. ResearchOS 自身文件

ResearchOS 自身文件分为规则文档、操作手册、模板、工具脚本和低层运行留存。系统级人读文档进入 `docs/`，共享事实源进入 `corpus/`，低层运行留存进入 `.researchos/outputs/machine/` 或 `.researchos/outputs/archive/`。

根级规则文档使用全大写英文名，保持少量稳定入口：

```text
AGENTS.md
README.md
CAPABILITIES.md
TRIGGERS.md
WORKFLOWS.md
QUALITY_GATES.md
TOOL_CONTRACTS.md
PROJECT_STATE.md
```

`docs/`、`RUNBOOKS/`、`POLICIES/`、`TOOL_CONTRACTS/` 和 `templates/` 下的人读说明使用小写英文短横线命名，文件名表达主题和用途：

```text
zotero-library-parent-documents.md
output-asset-governance.md
project-workspace-capability-map.md
research-project-manifest.yml
```

命名例外只允许稳定入口和外部约定文件：

- `POLICIES/*.md` 可保留全大写下划线文件名，例如 `API_KEY_POLICY.md`、`ZOTERO_WRITE_POLICY.md`，因为它们是被多处规则和流程引用的策略入口。
- `docs/modes/AGENTS.*.md` 可保留 `AGENTS.<mode>.md`，因为它们是 Codex 模式规则覆盖层，不是普通说明文档。
- 根级分发、评测和运行模板可保留既有约定名，例如 `DISTRIBUTION.md`、`EVALS.md`、`RUN_STATE_TEMPLATE.md`、`.env.example` 和 `.gitignore`。工具依赖清单优先放在 `tools/requirements/`，例如 `base.txt` 和 `ocr.txt`。
- 各目录内部的 `README.md` 可作为目录索引文件保留。

工具脚本使用小写英文下划线命名：

```text
zotero_ai_governance.py
sync_reading_summary_table.py
```

低层运行留存目录可使用：

```text
docs/reports/<name>/
.researchos/outputs/machine/M-###-name/
.researchos/outputs/archive/A-###-name/
```

编号含义：

- `M-###`：机器运行产物、试运行计划和执行记录。
- `A-###`：外部写入审批证据、执行前/执行后和回滚材料。

新增低层留存目录前，必须同步更新：

- `tools/researchos_outputs.py`
- `RUNBOOKS/output-asset-governance.md`
- 必要时更新 `TOOL_CONTRACTS.md` 和 `TOOL_CONTRACTS/` 对应专题契约

ResearchOS 自身治理产物进入 `docs/governance/`。

## 3A. 科研助理产生的人读文档

科研助理为具体项目产生的人读文档必须进入具体项目工作区。命名采用“编号-用途-可读主题”的形式：

```text
01-reading-cards/RC-###_短题名.md
02-literature-matrix/LM-###_用途说明.md
03-manuscript/MS-###_稿件部分.md
04-reviewer-response/RR-###_回复主题.md
```

系统级报告进入 `docs/reports/<主题>/`，使用小写英文短横线命名；具体项目报告不得长期放在 ResearchOS 根目录。

## 4. 课题目录

标准课题目录结构：

```text
课题目录/
  .research/
  annotations/
  01-reading-cards/
  02-literature-matrix/
    prisma/
  03-manuscript/
  04-reviewer-response/
```

课题内编号规则：

- 读书卡人工参阅编号：`RC-###`
- 提醒编号：`TODO-###`
- 文献矩阵或阅读总表：`LM-###`
- 研究情报报告：`RI-###`

机器中间产物优先放：

```text
02-literature-matrix/.internal/
.research/fulltext_cache/
```

## 5. 点子与项目指针

点子稳定编号：

```text
IDEA-YYYYMMDD-###
```

点子若仍处于临时探索阶段，进入平级 `0.Inbox/02-unassigned-ideas/`；一旦升级为培育课题或正式项目，应进入与 `00_ResearchOS/` 平级的项目工作区：

```text
用户指定项目工作区/01-课题入口-YYYYMMDD.md
项目根目录/01-点子入口-YYYYMMDD.md
```

`.researchos/active_ideas.md` 只保存换端恢复指针，不保存完整人读正文。

## 6. Zotero 项目文献集覆盖层

固定一级目录：

```text
00.科研项目
```

具体项目目录：

```text
NN-项目性质中文缩写-项目简称
```

常见项目性质：

- `纵向`
- `横向`
- `培育`
- `论文`
- `其他`

用途子文献集：

```text
编号-中文简写-EnglishSlug
```

示例：

```text
02-综述-review
03-引言-intro
04-方法-method
```

## 7. 批注与过程记录

批注条目：

```text
ANNO-YYYYMMDD-###
```

处理归档：

```text
annotations/processed/YYYY-MM-processed.md
```

执行日志和审计记录进入对应项目的 `.internal/`、ResearchOS `.researchos/outputs/archive/` 或 `.researchos/outputs/machine/`；需要人读时在 `docs/` 或项目工作区建立索引。

## 8. 命名审查清单

新增或迁移文件前检查：

- 这个对象属于人读、机器、审计留存、课题还是 Zotero 覆盖层？
- 是否已有同类命名规则？
- 文件名是否包含可读主题、用途和建立日期？
- 机器 key 是否只出现在元数据、机器表或审计字段？
- 是否需要同步索引、入口页、工具契约或输出路径常量？
- 是否会造成同一材料在多个位置重复维护？

## 完成标准

- 新对象名称能让人判断主题、用途和位置。
- 同类对象命名一致，脚本可稳定定位。
- 主命名规则已同步到新增和现有活跃文件。
- 命名规则变更已同步到入口文档、runbook 和必要工具契约。
