# ResearchOS 快速开始

ResearchOS 是给 Codex 使用的科研助理框架。普通阅读、判断、写作和审查不需要先安装 Python，也不要求先配置 Zotero。

## 1. 第一次打开：先检查，不先安装

在 Codex 中打开 ResearchOS 目录后说：

```text
检查 ResearchOS 是否可以直接使用。只做只读检查，不安装依赖，不写入 Zotero。
```

Codex 应按顺序检查：

1. `AGENTS.md`、`CAPABILITIES.md`、`TRIGGERS.md` 和 `.agents/skills/` 是否完整。
2. `.gitignore` 是否排除 `.researchos/`、真实配置、语料、项目记忆和密钥。
3. `configs/*.example.*` 和 `templates/` 是否可用。
4. 是否已有当前项目指针；没有项目时只报告“尚未绑定课题”，不视为框架故障。
5. 只有用户需要 PDF/OCR、Zotero 父文档维护或批量工具时，才检查 Python、Zotero Local API 和相关依赖。

输出只使用三种状态：

- **可直接使用**：LLM 原生科研任务可以开始。
- **部分可用**：科研任务可开始，但某些本地工具尚未配置。
- **需要处理**：核心规则、skill 或隐私边界缺失。

## 2. 可选：建立本机私有配置

需要跨设备映射项目路径时说：

```text
根据 configs 中的样例建立本机私有配置。真实配置放到用户主目录，不写入 GitHub。
```

推荐位置：`%USERPROFILE%/.researchos/machine_config.json`。没有该配置时，ResearchOS 默认把自身父目录作为 `projects_root`，因此配置不是普通使用的前置条件。

## 3. 建立课题工作区

```text
为这个课题建立 ResearchOS 工作区：<课题路径>
```

工作区会建立中文编号目录，并创建上下文恢复链：

```text
.research/project_manifest.yml
.research/run_state.json
.research/run-log.jsonl
01-课题入口/
02-证据材料/
03-文献矩阵/
05-论文稿件/
07-审稿回复/
10-批注/
```

既有文件不会被覆盖。只想预览时说“先试运行，不实际创建”。

## 4. 继续课题

```text
继续当前课题，先恢复上下文。
```

Codex 按 `active_project.yml → project_manifest.yml → run_state.json → run-log.jsonl` 的职责恢复，但冲突时以用户本轮说明和当前项目文件为准。它先读取轻量恢复包，再按本轮任务读取必要材料，不扫描全部全文。

## 5. 常用自然语言入口

```text
为这篇文献生成读书卡。
整理这些读书卡，形成综述矩阵。
判断这个研究缺口是否值得做。
把通过判断的选题变成研究问题、假设和变量。
审查这个方法设计能否支撑研究问题。
润色这段论文，但不要改变技术含义。
处理我的批注收件箱。
```

用户不需要记 skill 名称。明确请求直接进入一个主 skill；只有多目标或意图不清时才使用语义路由。

## 6. 只有需要工具时才准备环境

需要 OCR、Zotero 父文档维护或本地批量语料处理时，再运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\runtime\build_local_python_env.ps1 -Python "<LOCAL_PYTHON_EXE>"
```

该操作会创建本机环境并安装依赖，执行前需要用户确认。普通科研对话不依赖此步骤。

## 7. 安全与发布

- Zotero 默认只读；任何写入必须单独审批。
- 具体科研成果写入课题目录，不写入 ResearchOS 根目录。
- 真实配置、全文、PDF、数据库、运行记忆和密钥不进入公开仓库。
- 发布前检查 `PRIVACY.md` 和 `docs/github-release-checklist.md`。
