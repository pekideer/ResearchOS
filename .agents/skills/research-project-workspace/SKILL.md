---
name: research-project-workspace
description: 根据用户指定的研究课题目录，创建带编号前缀的 ResearchOS 输出文件夹。
---

## 目标

用于把 ResearchOS 的输出按具体研究课题归档，避免多个课题的读书卡、综述矩阵、论文草稿和审稿回复混在同一个目录中。

## 输入

- 用户指定的课题根目录。
- 或者用户指定的课题目录名，并由本机 `projects_root` 自动拼接。
- 可选：是否允许创建不存在的课题根目录。
- 可选：是否只预览目录，不实际创建。

## 工作流

1. 要求用户明确给出课题根目录，或给出 `--project-name`。
2. 若使用 `--project-name`，优先从本机配置读取 `projects_root`；若无配置，则使用 `00_ResearchOS` 的父目录。
3. 检查该目录是否存在。
4. 若目录不存在，只有在用户明确允许或传入 `--create-root` 时才创建。
5. 在课题根目录下创建编号化中文输出目录：
   - `01-课题入口/`
   - `02-证据材料/`
   - `03-文献矩阵/`
   - `03-文献矩阵/.internal/`
   - `03-文献矩阵/prisma/`
   - `04-决策记录/`
   - `05-论文稿件/`
   - `06-报告材料/`
   - `07-审稿回复/`
   - `08-写作材料/`
   - `09-计算工作区/`
   - `10-批注/`
   - `10-批注/processed/`
6. 创建 `10-批注/inbox.md` 和 `10-批注/review-log.md`，用于本课题人工阅读批注；已处理条目归档到 `10-批注/processed/`。
7. 默认创建 `.research/project_manifest.yml`、`.research/run_state.json` 和空的 `.research/run-log.jsonl`，形成可恢复项目；不覆盖已有状态文件。
8. 读书卡统一使用 `00_ResearchOS/templates/paper-reading-card.md`。默认采用集中主卡模式：主卡写入 `00_ResearchOS/corpus/reading-cards/cards/`，项目目录只保留阅读总表、团队追踪、项目指针和必要审计；若用户明确要求本地读书卡，必须在 manifest 中单独声明中文本地落点，不得再创建旧英文读书卡目录作为默认目录。
9. 不移动、不复制、不删除现有文件。
10. 输出已创建和已存在的目录清单。

## 输出

- 课题根目录路径。
- 路径来源：`--root`、本机配置或默认父目录。
- 已创建的目录。
- 已存在的目录。
- 后续建议保存的文件类型。
- 本课题人工批注入口：`10-批注/inbox.md`。
- `.research/` manifest、当前快照和最小运行日志入口。

## 质量规则

- 必须使用用户明确指定的目录，不能自行猜测课题目录。
- 不覆盖已有文件。
- 不移动、复制或删除 Zotero PDF。
- 不写入 Zotero。
- 对工作区外路径，执行前应确认权限边界。

## 安全规则

- 不覆盖已有文件。
- 不删除、移动或复制既有课题材料。
- 不把 API key、`.env`、Zotero 数据库或 PDF 文件写入课题目录；允许 `.research/fulltext_cache/` 保存抽取后的文本缓存。
- 目录不存在时，只有用户明确允许或传入 `--create-root` 才创建。
- `03-文献矩阵/prisma/` 可保存 PRISMA 检索、筛选、阅读状态和 Zotero 标签镜像计划，但不得保存 API key、Zotero 数据库、PDF 文件或可公开泄露的全文包。
- `.research/fulltext_cache/` 可保存项目内部文本缓存；不得保存 PDF 文件、API key、`.env` 或 Zotero 数据库，kit 导出必须剔除该目录。

## 完成条件

- 输出课题根目录、路径来源、已创建目录和已存在目录。
- `01-课题入口/`、`02-证据材料/`、`03-文献矩阵/`、`05-论文稿件/`、`07-审稿回复/`、`10-批注/` 已存在或 试运行 已列出。
- 读书卡落点已通过检查：默认集中主卡模式下 manifest 已声明集中主卡位置；若用户明确要求本地模式，manifest 已声明具体本地中文目录。
- `10-批注/inbox.md` 和 `10-批注/review-log.md` 已存在或 试运行 已列出。
- `.research/project_manifest.yml`、`.research/run_state.json` 和 `.research/run-log.jsonl` 已存在或试运行已列出。
- 未覆盖、移动、删除任何既有文件。
- 如路径权限不足或目录不存在，已给出明确原因和下一步。

## 用法

```powershell
python tools\project\create_project_workspace.py --root "$env:USERPROFILE\ResearchProjects\示例课题名称"
```

跨设备推荐：

```powershell
python tools\project\create_project_workspace.py --project-name "示例课题名称"
```

如果只想预览：

```powershell
python tools\project\create_project_workspace.py --project-name "示例课题名称" --dry-run
```

如果课题采用集中主卡和项目指针：

```powershell
python tools\project\create_project_workspace.py --project-name "示例课题名称" --reading-cards-mode centralized-links
```

只读审计现有课题读书卡落点：

```powershell
python tools\project\create_project_workspace.py --root "课题目录" --audit
```
