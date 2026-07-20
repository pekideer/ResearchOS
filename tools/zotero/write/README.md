# Zotero 写入工具

本目录全部是高风险外部写入入口，必须先读取 `POLICIES/ZOTERO_WRITE_POLICY.md` 与 `RUNBOOKS/zotero-web-api-write-canary.md`，并获得对具体计划的批准。

| 工具 | 用途 |
|---|---|
| `execute_zotero_item_mutation_plan.py` | 通用 tags 与条目 collection membership 冻结计划的预检/执行 |
| `mutation_contract.py` | 唯一 item mutation plan schema 和快照比较 |
| `mutation_executor.py` | 全局预检、PATCH、回读、审计和 rollback |
| `execute_project_collection_overlay_write.py` | 带项目用途互斥状态机的专用 overlay |
| `execute_zotero_deleted_collection_cleanup.py` | 已删除 collection 引用的专用清理 |
| `publish_reading_card_note.py` | 读书卡 note 的专用发布 |
| `zotero_web_api.py` | 共享 Web API、代理和分页基础设施 |

通用 mutation plan 必须绑定 `source_packet_hash`，逐条冻结完整 `version/tags/collection_keys` 和完整预期写后状态。真实写入前验证整批；任一漂移时零 PATCH。旧 additive 入口已删除，不保留兼容 schema。

所有模式均保存脱敏审计。真实写入运行包进入 `.researchos/outputs/archive/A-001-library-governance/zotero-item-mutation-runs/`；项目 overlay 和读书卡 note 使用各自显式目录。
