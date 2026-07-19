# 本地运行区与安全清理契约

## 1. 工具

- `tools/runtime/local_runtime.py`
- `tools/runtime/terminal_roles.py`

## 2. 作用

该工具只管理当前 Agent Core 根目录下的本地 `.researchos/`：初始化标准目录、验证运行区身份、生成清理预览，并在用户明确指定既有计划时清理已过保留期的文件。

终端角色工具读取 `%USERPROFILE%/.researchos/terminal_role.json`，对 Framework Maintainer、Corpus Publisher 和 Zotero Writer 权限分别进行本地预检；Project Writer 由项目交接协议管理。

## 3. 允许行为

- 创建 `.researchos/tmp/`、`cache/`、`logs/`、`failed-runs/`、`audit-staging/` 和本地 `runtime.json`。
- 只读审计目录数量、体积、未管理顶层目录和清理候选。
- 生成 `.researchos/cleanup-plan.json`，默认不删除。
- 仅在显式 `cleanup --apply <PLAN>` 时，删除计划中仍保持相同大小和修改时间的普通文件。

## 4. 禁止行为

- 不得清理 Agent Core 根目录、同步盘 `corpus/`、任何项目目录或项目 `.research/`。
- 不得跟随符号链接或 Junction 清理外部目录。
- 不得在缺少或不匹配 `runtime.json` 时生成或应用清理计划。
- 不得自动清理未关闭 failed run、未晋升 audit staging、未完成外部写入、待审批计划或未关闭回滚事项。
- 不得把本地 `.researchos/` 当作唯一项目状态或唯一正式审计副本。

## 5. 保留规则

- `tmp/`：7 天。
- `cache/`：30 天。
- `logs/`：14 天。
- `failed-runs/`：只有 scope 的 `cleanup-state.json` 明确 `issue_closed: true` 后，从 `closed_at` 起保留 30 天。
- `audit-staging/`：只有 scope 明确 `task_closed: true` 且 `promoted: true` 后，从 `closed_at` 起保留 30 天。

## 6. 验收

1. `init` 不覆盖已有有效 marker，不清理任何文件。
2. `audit` 和不带 `--apply` 的 `cleanup` 不删除文件。
3. apply 前一次性验证全部候选；任何目标漂移或越界时，在删除前整体停止。
4. 第一轮部署只初始化和审计，不应用清理计划。
5. follower 的 Git 只读权限必须由远端凭据和分支保护最终保证；本地 hook 只防止误推送，不能替代服务端权限。
