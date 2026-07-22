# ResearchOS Zotero 工具

- `zotero_library_index.py`、`zotero_fast_collection_sync.py`：维护只读父文档与必要缓存。
- `build_zotero_library_context_packet.py`：统一上下文入口；`--profile content` 排除当前 tags/collection，`--profile library` 才单列库内现状。
- `zotero_ai_governance.py`：语义治理 CLI；必须显式选择 `content-tags` 或 `library-structure`。
- `governance/`：任务专属契约、证据构建和只读计划生成。
- `zotero_new_item_monitor.py`：新增条目只读监控。
- `write/`：逐次审批的 Zotero Web API 写入入口。

只读工具不得隐式调用 `write/`。ResearchOS 代码只准备和验证语料，不完成科研语义判断，也不调用通用语言模型 API。
