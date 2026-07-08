# ResearchOS 高风险工具入口

本目录只存放需要单独审批的高风险工具。这里的工具不得由普通科研助理任务自动触发。

## 使用边界

- Zotero 写入、Zotero 恢复、Zotero 清理、批量结构改写和外部 API 写入，必须先读取 `POLICIES/ZOTERO_WRITE_POLICY.md` 与 `RUNBOOKS/zotero-web-api-write-canary.md`。
- 未完成试运行、人工确认、金丝雀测试、分批执行计划和回滚计划前，不得执行真实写入。
- 不得把 API key、完整代理地址、代理账号密码写入文件、日志或报告。
- 不得把本目录工具移回 `tools/` 根目录。

## 当前工具

| 工具 | 用途 | 默认状态 |
|---|---|---|
| `execute_project_collection_overlay_write.py` | 写入项目文献集覆盖层 | 需审批 |
| `execute_zotero_additive_write_plan.py` | 执行追加式 Zotero Web API 写入计划 | 需审批 |
| `execute_zotero_deleted_collection_cleanup.py` | 清理已删除 collection 引用 | 需审批 |
| `zotero_web_api.py` | 高风险 Zotero Web API workflow 的共享 helper | 仅供本目录工具调用 |

## 参数边界

- `execute_project_collection_overlay_write.py` 必须由调用方显式提供具体项目参数。
- `--assignments`、`--hierarchy`、`--runs-dir`、canary `--item-key` 和 `--target-path` 均必须显式传入。
- 普通科研任务不能通过默认参数误触发具体项目写入。
