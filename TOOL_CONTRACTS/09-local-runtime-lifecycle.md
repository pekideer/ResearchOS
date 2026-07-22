# 本地运行区与安全清理契约

## 1. 工具

- `tools/runtime/local_runtime.py`
- `tools/runtime/terminal_roles.py`
- `tools/runtime/corpus_snapshot.py`
- `tools/runtime/project_handoff.py`

## 2. 作用

该工具只管理当前 Agent Core 根目录下的本地 `.researchos/`：初始化标准目录、验证运行区身份、生成清理预览，并在用户明确指定既有计划时清理已过保留期的文件。

终端角色工具读取 `%USERPROFILE%/.researchos/terminal_role.json`，对 Framework Maintainer、Corpus Publisher 和 Zotero Writer 权限分别进行本地预检；Project Writer 由项目交接协议管理。

共享语料快照工具只读计算 corpus 内容哈希，不修改 SQLite、全文或读书卡。项目交接工具把 corpus 快照、Agent Core commit、终端身份和项目状态修订号写入项目 `.research/handoff.yml`；默认只输出计划，bootstrap、release 和 claim 均需显式 `--apply`。release 必须写入最新 `last_completed` 与 `next_action`；claim 和 check-write 必须与交出时的 framework commit、corpus snapshot ID 和 content hash 一致。

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
6. 项目交接文件使用 JSON-compatible YAML；任何转换前都核对项目 identity、live state、终端 identity、framework commit 和 corpus snapshot。
7. `claim` 或 `check-write` 发现 Agent Core commit、共享 corpus snapshot ID 或 content hash 漂移时必须停止；先完成 Git/同步盘对齐，再重新计划，不得在接管时静默覆盖锚点。
