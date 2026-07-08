# Fulltext Cache Governance

本操作手册定义 ResearchOS 对长文本材料的统一读取规则。目标是避免同一 PDF 或大段全文在不同任务中被反复解析、反复上传或反复消耗 token。

全库 Zotero 文献的默认父文档见 `RUNBOOKS/zotero-library-parent-documents.md`：先读取 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 和 `corpus/fulltext/zotero-library-normalized/`，课题 `.research/fulltext_cache/` 是项目局部缓存或派生缓存。

## 1. 适用范围

凡任务需要读取大段文字，尤其是 PDF 全文、PDF 前几页、论文全文、书稿章节、项目材料包、长篇报告，都必须先检查可用父文档或 缓存。Zotero 全库条目优先使用同步盘父文档；具体课题材料再检查课题目录的 全文缓存：

```text
<project-root>/.research/fulltext_cache/
```

规定位置：

- `.research/fulltext_cache/ITEMKEY.txt`
- `.research/fulltext_cache/<material-derived-name>.txt`

## 2. 读取顺序

1. 已知 Zotero 条目 key 时，先用 `tools/build_zotero_library_context_packet.py` 从 SQLite 父文档和 规范化文本 构建上下文。
2. 如果任务绑定具体课题且已有 `.research/fulltext_cache/ITEMKEY.txt`，可复用项目局部缓存，但应优先确认其来源能回溯到父文档。
3. 如果任务是多篇读书卡、综述矩阵、论断审计、方法审查或文本精读，优先用父文档上下文包或 `tools/build_fulltext_cache_packet.py` 从 缓存 生成紧凑证据包。
4. 如果只需要作者/单位题录区，优先读取父文档 规范化文本 或 缓存 的 第 1-2 页，必要时 第 3 页。
5. 父文档或 全文缓存 存在时，不得为同一任务重新读取 Zotero PDF 或重新抽取 PDF 文本。
6. 只有父文档和 缓存均缺失时，才允许通过 `tools/zotero_library_index.py` 或 Zotero Local API 只读定位 PDF 并抽取文本；抽取后必须写回父文档或 `.research/fulltext_cache/` 供后续复用。

## 3. 输出边界

- 全文缓存 是课题内部工作缓存，不是人工主入口。
- 不把 PDF 文件复制到课题目录；只保存抽取后的 `.txt` 文本缓存。
- 不把 全文缓存 放入 kit export、公开附件、报告正文或可分享模板包。
- 人工输出只引用必要摘录、页码范围和 缓存路径；不得整篇粘贴长文本。
- 缓存缺失、抽取失败或扫描版 PDF 时，明确标注 `cache_missing`、`extract_failed` 或 `needs_ocr`。

## 4. 工具入口

通用长文本证据包：

```powershell
python tools\build_zotero_library_context_packet.py --item-key ITEMKEY --include-text
python tools\build_fulltext_cache_packet.py --project-root "课题目录" --max-pages 5
```

第一作者单位证据包：

```powershell
python tools\build_affiliation_semantic_packet.py --project-root "课题目录"
```

PDF 抽取并写入 缓存：

```powershell
python tools\zotero_local_api_cli.py extract-pdf --pdf "PDF_PATH" --project-root "课题目录" --item-key ITEMKEY --cache-subdir .
```

项目材料抽取并写入 缓存：

```powershell
python tools\extract_project_materials.py --project-root "课题目录" --output-dir "课题目录\.research\material_text"
```

## 5. 质量门禁

- 使用 PDF/长文本前，必须说明是否命中 全文缓存。
- 使用 Zotero 全库条目前，必须说明是否命中 SQLite 父文档和 规范化文本。
- 如果没有命中父文档或 缓存，必须说明为何需要重新抽取，并把结果写回父文档或 缓存。
- 任何任务不得绕过已有 缓存 重复读取同一 PDF。
- 对外输出不得泄露 全文缓存 的全文内容。
