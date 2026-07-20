# Zotero Local API Readonly Runbook

本操作手册说明如何执行 Zotero 只读工作流。该流程不写入 Zotero，不修改 标签、文献集、笔记或 PDF。

注意：普通阅读、综述、AI 分类和治理任务默认先读取 `RUNBOOKS/zotero-library-parent-documents.md` 定义的父文档。Zotero Local API 只读流程主要用于维护父文档、排查父文档缺失或临时检索。

## 适用场景

- 从 Zotero 搜索文献。
- 读取 条目元信息和 子条目。
- 定位 PDF。
- 抽取 PDF 文本。
- 更新或修复 ResearchOS SQLite 父文档和 规范化文本。

## 步骤

### 0. 先检查父文档

```powershell
python tools\zotero\build_zotero_library_context_packet.py --item-key ITEM_KEY --include-text
```

若父文档命中，直接使用父文档和规范化文本。

### 1. Ping

```powershell
python tools\zotero\zotero_local_api_cli.py ping --allow-local-api
```

完成标准：输出 Zotero Local API 可访问，或给出明确错误原因。

### 2. Search

```powershell
python tools\zotero\zotero_local_api_cli.py search --allow-local-api --query "KEYWORD" --limit 10
```

完成标准：候选结果包含 title、条目 key、作者、年份、DOI 或 URL。

### 3. Get item

```powershell
python tools\zotero\zotero_local_api_cli.py get-item --allow-local-api --key ITEM_KEY
```

完成标准：输出母条目元信息和 子条目。

### 4. Get PDF

```powershell
python tools\zotero\zotero_local_api_cli.py get-pdf --allow-local-api --key ITEM_KEY
```

完成标准：输出 PDF 附件 key、PDF 路径和存在性检查。

### 5. Extract PDF text

先检查父文档和课题 `02-证据材料/全文缓存/`；旧 `.research/fulltext_cache/` 仅只读兼容。若父文档或缓存已存在，直接使用；只有缺失时才抽取 PDF 文本，项目结果写入证据目录，共享结果先进入本机 staging。

```powershell
python tools\zotero\zotero_local_api_cli.py extract-pdf --pdf "PDF_PATH" --project-root "课题目录" --item-key ITEM_KEY --cache-subdir reading-cards --max-pages 5
```

如果没有具体课题目录，应优先使用 `tools\zotero\zotero_library_index.py sync` / `normalize-text-cache` 维护父文档。当前共享读取入口为 `corpus/fulltext/`。完成标准：生成或复用文本缓存，并说明缓存路径和页数范围。扫描版 PDF 如无法抽取，应提示需要 OCR。

### 6. 生成读书卡

将父文档中的题录信息、条目 key 和 规范化文本 交给 `paper-deep-reading`。

完成标准：读书卡区分事实、推断、建议和假设，包含 `generated_at`，并保留 条目 key 与文本来源。

## 常见错误

- HTTP 403：通常是 Zotero 已运行但 Local API 未启用。
- 连接失败：Zotero 桌面端未打开、端口 `23119` 被拦截，或 API 地址错误。
- 条目 key 不存在：请确认使用 top-level 条目 key。
- PDF 路径不存在：附件可能未下载、外部链接失效或 file URL 解析失败。
- 抽取文本为空：PDF 可能是扫描版，当前默认流程不做 OCR。
