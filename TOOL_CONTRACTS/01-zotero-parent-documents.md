# Zotero 父文档、Local API 与全文缓存契约

## 1. 适用工具

- `zotero_local_api_cli.py`
- `build_fulltext_cache_packet.py`
- `build_zotero_library_context_packet.py`
- `zotero_local_api.py`
- `ensure_ocr_needed.py`
- `zotero_fast_collection_sync.py`
- `zotero_library_index.py`
- `zotero_annotation_sync.py`
- `start_zotero_library_watcher.ps1`

## 2. 工具目的

本专题工具用于维护和排障 ResearchOS 的 Zotero 父文档、规范化全文缓存和 Local API 只读访问。普通科研任务应优先读取父文档，不应直接访问 Zotero 原始数据库或 PDF。

## 3. 事实源

- SQLite 父文档：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite`
- 规范化全文：`corpus/fulltext/zotero-library-normalized/`
- Local API：`http://localhost:23119/api/`
- 用户 ID：`0`

## 4. 允许行为

- 检查 Zotero Local API 是否可用。
- 只读查询条目元数据、附件位置和 PDF 信息。
- 抽取 PDF 文本并写入 ResearchOS 父文档或规范化全文缓存。
- 生成供阅读、综述、选题、矩阵和治理使用的上下文包。
- 标记扫描版、文本缺失或可能需要 OCR 的文件。
- 维护 watcher 所需的本地同步状态。
- 只读采集已有集中读书卡对应条目的 Zotero 原生 PDF annotation，并写入父文档镜像。

## 5. 禁止行为

- 不直接读取或修改 Zotero 原始 `zotero.sqlite`。
- 不写入 Zotero 条目、标签、文献集、笔记或附件。
- 不移动、复制、重命名、删除 Zotero PDF。
- 不把 Zotero storage、PDF 缓存、API key 或 `.env` 放入 OneDrive 项目目录。
- 不把 Local API 读取结果直接解释为人工批准的治理结论。

## 6. 失败处理

Local API 不可用时，应提示：

1. 确认 Zotero 桌面端已打开。
2. 确认 Zotero 设置中已启用 Local API。
3. 确认本机端口 `23119` 未被防火墙或安全软件拦截。
4. 确认请求地址为 `http://localhost:23119/api/`。

PDF 文本抽取失败时，应说明失败原因、条目范围和是否可能需要 OCR。默认流程不自动执行 OCR。

## 7. 验收标准

- 父文档路径存在且可只读打开。
- 规范化全文缓存路径明确。
- 输出报告区分事实、推断和建议。
- 涉及 PDF 总结时说明文本来源和页数范围。
- 未发生 Zotero 写入、PDF 移动或原始数据库访问。
