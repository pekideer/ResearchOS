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
5. 在课题根目录下创建编号化输出目录：
   - `annotations/`
   - `annotations/processed/`
   - `annotations/.internal/`
   - `02-literature-matrix/`
   - `02-literature-matrix/prisma/`
   - `03-manuscript/`
   - `04-reviewer-response/`
   - 默认创建 `01-reading-cards/`；若明确采用集中主卡模式，则不要求本地 `01-reading-cards/`，而是在 manifest 中声明 `reading_cards_mode: "centralized_links"`。
6. 创建 `annotations/inbox.md` 和 `annotations/review-log.md`，用于本课题人工阅读批注；已处理条目归档到 `annotations/processed/`。
7. 如用户需要长任务恢复或跨会话交接，建议在课题目录下维护 `.research/` manifest；模板见 `templates/research-project-manifest.yml` 等。
8. 读书卡统一使用 `00_ResearchOS/templates/paper-reading-card.md`。读书卡落点必须二选一并写入 manifest：本地模式使用 `01-reading-cards/`；集中主卡模式使用 `00_ResearchOS/corpus/reading-cards/` 与项目指针，不得同时声明集中库又把缺失的 `01-reading-cards/` 当作有效落点。
9. 不移动、不复制、不删除现有文件。
10. 输出已创建和已存在的目录清单。

## 输出

- 课题根目录路径。
- 路径来源：`--root`、本机配置或默认父目录。
- 已创建的目录。
- 已存在的目录。
- 后续建议保存的文件类型。
- 本课题人工批注入口：`annotations/inbox.md`。
- 可选 `.research/` manifest 文件建议。

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
- `02-literature-matrix/prisma/` 可保存 PRISMA 检索、筛选、阅读状态和 Zotero 标签镜像计划，但不得保存 API key、Zotero 数据库、PDF 文件或可公开泄露的全文包。
- `.research/fulltext_cache/` 可保存项目内部文本缓存；不得保存 PDF 文件、API key、`.env` 或 Zotero 数据库，kit 导出必须剔除该目录。

## 完成条件

- 输出课题根目录、路径来源、已创建目录和已存在目录。
- `annotations/`、`02-literature-matrix/`、`02-literature-matrix/prisma/`、`03-manuscript/`、`04-reviewer-response/` 已存在或 试运行 已列出。
- 读书卡落点已通过二选一检查：本地模式下 `01-reading-cards/` 已存在或 试运行 已列出；集中主卡模式下 manifest 已声明 `reading_cards_mode: "centralized_links"` 和集中主卡位置。
- `annotations/inbox.md` 和 `annotations/review-log.md` 已存在或 试运行 已列出。
- 如用户要求 manifest，已说明 `.research/` 推荐文件和模板来源。
- 未覆盖、移动、删除任何既有文件。
- 如路径权限不足或目录不存在，已给出明确原因和下一步。

## 用法

```powershell
python tools\create_project_workspace.py --root "$env:USERPROFILE\ResearchProjects\示例课题名称"
```

跨设备推荐：

```powershell
python tools\create_project_workspace.py --project-name "示例课题名称"
```

如果只想预览：

```powershell
python tools\create_project_workspace.py --project-name "示例课题名称" --dry-run
```

如果课题采用集中主卡和项目指针：

```powershell
python tools\create_project_workspace.py --project-name "示例课题名称" --reading-cards-mode centralized-links
```

只读审计现有课题读书卡落点：

```powershell
python tools\create_project_workspace.py --root "课题目录" --audit
```
