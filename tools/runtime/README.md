# Runtime tools

本目录集中本机 Python/OCR 环境检查、本地运行区、终端角色、共享语料快照和项目交接工具。

运行环境、OCR runtime 和缓存应保留在机器本地目录；不得把环境、密钥或大型
runtime 写入同步仓库。

`local_runtime.py` 管理 Agent Core 下被 Git 忽略的 `.researchos/`。默认命令只初始化、审计或生成清理计划；真实清理必须显式提供 `cleanup --apply <PLAN>`，且只能作用于带有效 `runtime.json` 的本地运行区。

`terminal_roles.py` 读取用户目录中的私有 `terminal_role.json`，分别检查 framework、corpus 和 Zotero 写入角色。Git `pre-push` 门禁只提供本地防误操作；follower 的最终只读权限仍应由远端只读凭据和分支保护保证。

`corpus_snapshot.py` 只读计算共享 corpus 的确定性内容快照。`project_handoff.py` 使用该快照、Agent Core commit 和终端身份，对项目 `.research/handoff.yml` 执行 bootstrap、release、claim 和写入权检查；release 必须记录最近完成步骤和下一步，claim/check-write 必须匹配当前 commit 与 corpus 快照，改变项目状态必须显式使用 `--apply`。

`project_write_guard.py` 是项目写入口的共用 fail-closed 门禁。`publish_corpus.py` 把 `M-006` staging 冻结为带哈希和目标基线的计划，只允许 Corpus Publisher 显式 apply，并以最后写入的 release manifest 作为跨 Junction 的提交记录。真实发布、回滚和删除仍需分别审批。
