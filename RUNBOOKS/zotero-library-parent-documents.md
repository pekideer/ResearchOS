# Zotero Library Parent Documents

本操作手册定义 ResearchOS 后续文献管理、阅读、综述、AI 分类和治理任务的默认事实源。目标是让所有任务先读取同步盘父文档，避免每个流程重新访问 Zotero、重新定位 PDF 或重复抽取全文。

## 1. 父文档

ResearchOS 的 Zotero 父文档由两类机器产物组成：

```text
corpus/zotero/M-001-zotero-library/zotero_library.sqlite
corpus/fulltext/zotero-library-normalized/ITEMKEY__ATTACHMENTKEY.txt
```

- `zotero_library.sqlite` 保存 Zotero 顶层条目 元数据、文献集/标签 快照、附件元数据、PDF 抽取状态和 规范化文本 路径。
- `zotero-library-normalized/` 保存 附件级 AI 规范化 PDF 文本。
- `tools/zotero/zotero_fast_collection_sync.py` 是父文档每日快同步入口，只维护 文献集 树、项目 文献集 归属和必要条目元数据。
- `tools/zotero/zotero_library_index.py sync` 和 `watch` 是父文档全量维护入口；普通阅读、矩阵、治理和 AI 任务默认不直接读取 Zotero Local API 或 PDF。

## 2. 默认读取顺序

1. 已知 条目 key、题名或检索条件时，先查询 `zotero_library.sqlite`。
2. 需要全文或首页文本时，优先读取 SQLite 中 `pdf_texts.text_normalized_cache_path` 指向的 规范化文本。
3. 若 SQLite 中的 normalized path 因跨设备盘符变化失效，按当前工作区定位到 `corpus/fulltext/zotero-library-normalized/ITEMKEY__ATTACHMENTKEY.txt`。
4. 只有 文献集 树、项目 文献集 归属或必要条目元数据需要保持最新时，才调用 Zotero Local API，通过 `tools/zotero/zotero_fast_collection_sync.py` 做每日快同步。
5. 只有父文档缺失、过期、附件状态缺失或需要补齐全文缓存时，才通过 `tools/zotero/zotero_library_index.py sync` / `watch` 更新 SQLite 和文本缓存。
6. 只有 SQLite 记录显示 PDF 文本缺失、抽取失败或 `needs_ocr` 时，才进入 PDF 抽取/OCR 修复流程。

## 3. 轻量维护约定

父文档长期维护默认采用“每日快同步、按需全文读取”：

1. 每日快同步只维护 Zotero 文献集 树、项目 文献集 下的条目归属和必要条目元数据。
2. 每日快同步使用 `tools/zotero/zotero_fast_collection_sync.py`，不得读取 PDF、不得抽取全文、不得 OCR、不得写入 Zotero。
3. 全文缓存默认不做实时检查；只要 `item_key` 与 `attachment_key` 稳定，后续按 `ITEMKEY__ATTACHMENTKEY.txt` 定位规范化文本。
4. 需要读取某条文献全文时，先查 `pdf_texts.text_normalized_cache_path`，若文件存在则直接读取。
5. 若目标条目没有规范化文本，才进入单条 PDF 抽取或 OCR 修复流程。
6. 全库 `zotero_library_index.py sync`、`normalize-text-cache`、`ocr-needed` 和 `slim-db` 只作为低频维护或故障排查入口，不纳入每日任务。
7. 在 Windows 上优先使用 `http://127.0.0.1:23119/api` 和 Python/curl 访问 Local API；避免用 PowerShell `Invoke-RestMethod` 判断 Local API 是否可用。

## 4. 推荐工具

从父文档构建上下文包：

```powershell
python tools\zotero\build_zotero_library_context_packet.py --item-key ITEMKEY --include-text
python tools\zotero\build_zotero_library_context_packet.py --query "radiant cooling" --limit 20
```

每日快同步：

```powershell
python tools\zotero\zotero_fast_collection_sync.py --api-base http://127.0.0.1:23119/api --user-id 0 --include-items --project-path "具体课题目录"
```

低频维护父文档：

```powershell
python tools\zotero\zotero_library_index.py sync
python tools\zotero\zotero_library_index.py watch
python tools\zotero\zotero_library_index.py normalize-text-cache --overwrite
```

当前共享读取入口以 `corpus/` 为准。脚本默认写入位置应使用 `corpus/` 或项目局部缓存。

检查 OCR 待处理项：

```powershell
python tools\runtime\ensure_ocr_needed.py
```

## 5. 冲突处理

- `tools/zotero/zotero_local_api_cli.py` 只作为父文档维护或故障排查的底层工具，不作为普通阅读/治理默认入口。
- 课题 `.research/fulltext_cache/` 仍可作为项目局部缓存，但其来源应优先由父文档派生；不得绕过已有父文档重复读取 PDF。
- 人工报告可引用 规范化文本 路径和页数/字符范围，但不得把整篇全文复制进报告。
- 不读取或修改 Zotero 原始 `zotero.sqlite`。
- 不复制、移动、删除或重命名 Zotero PDF。

## 6. 完成标准

- 任务说明中明确使用了 SQLite 父文档或 规范化文本 父文档。
- 若未命中父文档，说明原因，并优先通过 `zotero_library_index.py` 更新父文档。
- 后续读书卡、矩阵、论断审计、AI 分类和治理计划均能回溯到 条目 key、附件 key、SQLite 记录和 规范化文本 文件。
