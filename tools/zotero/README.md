# Zotero tools

本目录集中 Zotero 只读访问、父文档维护、文献库治理和新条目监控工具。

- `zotero_local_api.py`：只读 Local API 共享客户端。
- `zotero_local_api_cli.py`：只读排障和 PDF 定位/抽取入口。
- `zotero_library_index.py`：父文档 SQLite 与全文缓存维护主入口。
- `zotero_fast_collection_sync.py`：文献集与必要元数据快同步。
- `build_zotero_library_context_packet.py`：从父文档生成上下文包。
- `zotero_ai_governance.py`：文献库治理主入口；内部实现位于 `governance/`。
- `zotero_new_item_monitor.py`：新增条目监控和试运行分类计划。
- `write/`：需要逐次审批的 Zotero Web API 写入工具。

只读工具不得隐式调用 `write/`。写入工具不得由普通科研任务自动触发。
