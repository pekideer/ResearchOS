# Zotero Web API 写入与冻结执行契约

## 适用工具

- `tools/zotero/write/execute_zotero_item_mutation_plan.py`
- `tools/zotero/write/mutation_contract.py`
- `tools/zotero/write/mutation_executor.py`
- `tools/zotero/write/execute_project_collection_overlay_write.py`
- `tools/zotero/write/execute_zotero_deleted_collection_cleanup.py`
- `tools/zotero/write/publish_reading_card_note.py`
- `tools/zotero/write/zotero_web_api.py`

## 通用 item mutation plan

标签和条目 collection membership 的通用增减统一使用结构化计划：

- 顶层：`schema_version`、`plan_id`、`plan_kind`、`source_packet_hash`、`approval_status`、`actions`。
- 每个 action：`item_key`、`expected_before`、`mutation`、`expected_after`、`evidence_refs`。
- `expected_before` 必须冻结 `version + tags + collection_keys`。
- `mutation` 必须使用数组字段 `add_tags/remove_tags/add_collection_paths/remove_collection_paths`，且至少包含一项变化。
- `expected_after` 必须冻结完整 tags 和 collection keys，不接受隐式合并结果。

旧的 additive 兼容入口和旧字段不再接受，避免两套契约并存。

## 执行门禁

1. 用户批准具体计划，计划内 `approval_status` 为 `approved`。
2. 通过 Web API GET 获取所有入选条目和完整 collection 树。
3. 在任何 PATCH 前，全局比较每条目的版本、完整 tags、完整 collection keys、collection path 映射及预期写后状态。
4. 任一条目漂移或计划不一致，整批零写入并记录 `preflight_blocks.json`。
5. PATCH 使用审批快照对应的 `If-Unmodified-Since-Version`。
6. 每条写后立即 GET 回读，精确核对完整 tags 和 collection keys；失败立即停止扩大批次。
7. 无论成功、阻断或中途失败，都保存计划哈希、来源包哈希、before/after、审计和已写条目的 rollback 载荷。

## 专用流程

项目 overlay、deleted-collection cleanup 和 reading-card note 各有额外状态机，保留专用入口；它们不得冒充通用 item mutation plan，也不得绕过各自的审批、金丝雀和回读条件。

reading-card note 使用专用计划 schema v2；计划必须冻结有效的统一读书卡契约回执，真实写入前重新校验本地卡片并比较回执哈希。卡片正文、来源、页码、项目用途结构或回执发生漂移时，计划失效并零写入。

## 安全边界

- 仅 Zotero Web API 可写；Local API 永远只读。
- 不记录 API key、完整代理 URL 或代理凭据。
- 不删除条目、附件或 PDF。删除 note/collection 等动作必须有单独精确审批。
- 运行证据写入 `.researchos/outputs/archive/`；项目 overlay 的项目级证据写入其显式项目运行目录。
