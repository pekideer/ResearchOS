# 工具契约索引

本文档是 `TOOL_CONTRACTS/` 的总索引。具体工具边界以对应专题文件为准。

## 1. 专题索引

| 专题文件 | 工具范围 |
|---|---|
| `01-zotero-parent-documents.md` | Zotero 父文档、Local API、PDF 文本、全文缓存和 watcher |
| `02-zotero-library-governance.md` | Zotero 文献库治理、研究方向聚合、标签和文献集建议 |
| `03-zotero-web-api-write.md` | Zotero Web API 写入、回滚和高风险写入 |
| `04-reading-cards-prisma.md` | 读书卡、PRISMA、期刊等级、作者机构和引用显示 |
| `05-project-workspace.md` | 点子、课题、项目工作区和项目材料治理 |
| `06-researchos-governance.md` | ResearchOS 自身规则、输出边界、命名和审计 |
| `07-runtime-ocr-local-env.md` | 本机运行环境、OCR 和依赖配置 |
| `08-zotero-reading-card-annotation-sync.md` | Zotero annotation 回流、读书卡生成区和经审批的条目子笔记发布 |

## 2. 工具角色分层

| 角色 | 工具范围 | 使用边界 |
|---|---|---|
| 语料准备 | PDF 文本、Zotero 父文档、规范化全文、上下文包、项目局部缓存 | 只为 LLM 准备可回溯语料，不直接生成科研结论 |
| 外部桥接 | Zotero Local API、Zotero Web API、EasyScholar、跨设备路径 | 读取默认只读；写入和系统级动作必须单独审批 |
| ResearchOS 自检 | 规则审计、契约审计、命名治理、输出边界、治理仪表盘 | 默认只读；代码适配需先汇报必要性 |
| 高风险写入 | Zotero 写入、批量移动/删除/改名、项目结构改写 | 只在用户审批后运行，不作为普通科研能力自动触发 |

## 3. 工具映射

| 工具 | 契约文件 |
|---|---|
| `tools/zotero/zotero_local_api_cli.py` | `01-zotero-parent-documents.md` |
| `tools/reading_cards/build_fulltext_cache_packet.py` | `01-zotero-parent-documents.md` |
| `tools/zotero/build_zotero_library_context_packet.py` | `01-zotero-parent-documents.md` |
| `tools/zotero/zotero_local_api.py` | `01-zotero-parent-documents.md` |
| `tools/runtime/ensure_ocr_needed.py` | `01-zotero-parent-documents.md` |
| `tools/zotero/zotero_fast_collection_sync.py` | `01-zotero-parent-documents.md` |
| `tools/zotero/zotero_library_index.py` | `01-zotero-parent-documents.md` |
| `tools/zotero/start_zotero_library_watcher.ps1` | `01-zotero-parent-documents.md` |
| `tools/zotero/zotero_ai_governance.py` | `02-zotero-library-governance.md` |
| `tools/zotero/zotero_new_item_monitor.py` | `02-zotero-library-governance.md` |
| `tools/zotero/write/zotero_web_api.py` | `03-zotero-web-api-write.md` |
| `tools/zotero/write/execute_project_collection_overlay_write.py` | `03-zotero-web-api-write.md` |
| `tools/zotero/write/execute_zotero_additive_write_plan.py` | `03-zotero-web-api-write.md` |
| `tools/zotero/write/execute_zotero_deleted_collection_cleanup.py` | `03-zotero-web-api-write.md` |
| `tools/zotero/write/README.md` | `03-zotero-web-api-write.md` |
| `tools/reading_cards/configure_easyscholar_api.ps1` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/sync_journal_rankings.py` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/sync_first_author_affiliations.py` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/build_affiliation_semantic_packet.py` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/build_prisma_status_outputs.py` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/sync_reading_summary_table.py` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/sync_zotero_metadata_to_cards.py` | `04-reading-cards-prisma.md` |
| `tools/reading_cards/card_common.py` | `04-reading-cards-prisma.md` |
| `tools/zotero/zotero_annotation_sync.py` | `08-zotero-reading-card-annotation-sync.md` |
| `tools/reading_cards/sync_zotero_annotations_to_cards.py` | `08-zotero-reading-card-annotation-sync.md` |
| `tools/zotero/write/publish_reading_card_note.py` | `08-zotero-reading-card-annotation-sync.md`、`03-zotero-web-api-write.md` |
| `tools/project/extract_project_materials.py` | `05-project-workspace.md` |
| `tools/project/create_project_workspace.py` | `05-project-workspace.md` |
| `tools/researchos_outputs.py` | `06-researchos-governance.md` |
| `tools/runtime/build_local_python_env.ps1` | `07-runtime-ocr-local-env.md` |
| `tools/runtime/serve_portable_html.py` | `07-runtime-ocr-local-env.md` |

## 4. 当前治理要求

- `tools/zotero/write/` 中的工具只能通过审批流程触发，并继续按高风险工具管理。
- `zotero_ai_governance.py` 是 Zotero 文献库治理的主入口；方向聚合、标签计划和文献集计划由该入口调用内部模块。
- 自动审计如需启用，应以当前 `docs/`、`corpus/`、`tools/zotero/write/` 和活跃工具清单为基准。
- 新工具先判断是否真的需要代码；已批准的新工具必须登记到本索引和对应专题文件。
- 工具契约变更后，应同步检查 `WORKFLOWS.md`、`TRIGGERS.md`、`QUALITY_GATES.md` 和相关 `RUNBOOKS/`。
