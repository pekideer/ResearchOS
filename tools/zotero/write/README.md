# ResearchOS Zotero 写入工具入口

本目录只存放需要单独审批的 Zotero Web API 写入与恢复工具。这里的工具不得由普通科研助理任务自动触发；目录名称描述功能，不降低其高风险等级。

## 使用边界

- Zotero 写入、Zotero 恢复、Zotero 清理、批量结构改写和外部 API 写入，必须先读取 `POLICIES/ZOTERO_WRITE_POLICY.md` 与 `RUNBOOKS/zotero-web-api-write-canary.md`。
- 未完成试运行、人工确认、金丝雀测试、分批执行计划和回滚计划前，不得执行真实写入。
- 不得把 API key、完整代理地址、代理账号密码写入文件、日志或报告。
- 不得把本目录工具移回 `tools/` 根目录，也不得由普通只读 Zotero 工具隐式导入执行入口。

## 当前工具

| 工具 | 用途 | 默认状态 |
|---|---|---|
| `execute_project_collection_overlay_write.py` | 写入项目文献集覆盖层 | 需审批 |
| `execute_zotero_additive_write_plan.py` | 执行追加式 Zotero Web API 写入计划 | 需审批 |
| `execute_zotero_deleted_collection_cleanup.py` | 清理已删除 collection 引用 | 需审批 |
| `zotero_web_api.py` | 共享环境配置、脱敏代理、HTTP 请求和分页 helper | 仅供本目录工具调用 |

## 参数边界

- `execute_project_collection_overlay_write.py` 必须由调用方显式提供具体项目参数。
- `--assignments`、`--hierarchy`、`--runs-dir`、canary `--item-key` 和 `--target-path` 均必须显式传入。
- 普通科研任务不能通过默认参数误触发具体项目写入。

## 输出边界

- `execute_zotero_additive_write_plan.py` 和
  `execute_zotero_deleted_collection_cleanup.py` 的输入计划来自
  `.researchos/outputs/machine/M-002-library-governance/`，但 preflight、写入前后
  快照、执行审计和回滚材料统一写入
  `.researchos/outputs/archive/A-001-library-governance/`。
- `execute_project_collection_overlay_write.py` 不提供默认输出目录；调用方必须通过
  `--runs-dir` 显式指定具体项目的 `.internal/zotero-collection-overlay/` 或经批准的
  ResearchOS 审计归档位置。
- 不得把真实写入运行包重新写回 `outputs/machine/`。
