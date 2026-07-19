# Runtime tools

本目录集中本机 Python/OCR 环境检查和本地 HTML 服务工具。

运行环境、OCR runtime 和缓存应保留在机器本地目录；不得把环境、密钥或大型
runtime 写入同步仓库。

`local_runtime.py` 管理 Agent Core 下被 Git 忽略的 `.researchos/`。默认命令只初始化、审计或生成清理计划；真实清理必须显式提供 `cleanup --apply <PLAN>`，且只能作用于带有效 `runtime.json` 的本地运行区。

`terminal_roles.py` 读取用户目录中的私有 `terminal_role.json`，分别检查 framework、corpus 和 Zotero 写入角色。Git `pre-push` 门禁只提供本地防误操作；follower 的最终只读权限仍应由远端只读凭据和分支保护保证。
