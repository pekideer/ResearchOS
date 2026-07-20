---
name: zotero-literature-access
description: 当 ResearchOS Zotero 父文档缺失、过期或需要维护时，通过 Zotero Local API 只读搜索条目、读取元信息、定位 PDF 附件并抽取文本；普通阅读和治理默认先用父文档。
---

## 目标

在 Codex 中安全调用本机 Zotero Local API，维护或排查 ResearchOS Zotero 父文档。普通文献阅读、综述矩阵、AI 分类和库治理默认先读取 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。Local API 流程只读，不向 Zotero 写入任何内容。涉及 PDF/长文本读取时，必须先检查父文档和课题 `.research/fulltext_cache/`；命中时不重新读取 PDF。

## 触发场景

- 父文档缺失、过期或路径失效，需要重新同步 Zotero 条目。
- 需要临时排查父文档中某个 条目 key、附件或 PDF 路径。
- 需要确认 Zotero Local API 是否可访问。
- 需要将缺失的 PDF 文本补入父文档或项目全文缓存。

## 输入

- 检索关键词、主题词、作者名、DOI 或标题片段。
- Zotero 顶层条目 key。
- 可选：PDF 路径、页数范围、输出路径。
- 可选：课题目录；用于优先复用或写入 `.research/fulltext_cache/`。

## 工作流

1. 先检查父文档：`tools/zotero/build_zotero_library_context_packet.py --profile content --item-key ITEM_KEY --include-text` 或按查询词读取 SQLite。
2. 父文档命中时，直接把父文档上下文包交给 `paper-deep-reading`、`literature-matrix` 或治理流程，不继续调用 Local API。
3. 只有父文档缺失、过期、路径失效或明确需要增量同步时，运行 `python tools/zotero/zotero_local_api_cli.py ping --allow-local-api`，确认 Zotero Local API 可访问。
4. 优先用 `tools/zotero/zotero_library_index.py sync` / `watch` 更新 SQLite 父文档和 PDF 文本缓存链接。
5. 临时排障时，可使用 `python tools/zotero/zotero_local_api_cli.py search --allow-local-api --query "关键词" --limit N` 搜索候选文献，或使用 `python tools/zotero/zotero_local_api_cli.py get-item --allow-local-api --key ITEM_KEY` 读取母条目元信息和子条目。
6. 只有父文档和缓存均缺失时，才使用 `python tools/zotero/zotero_local_api_cli.py get-pdf --allow-local-api --key ITEM_KEY` 获取 PDF 路径。
7. 使用 `python tools/zotero/zotero_local_api_cli.py extract-pdf --pdf "PDF_PATH" --project-root "课题目录" --item-key ITEM_KEY --max-pages N` 抽取文本时，应优先把结果写回父文档维护链路或可回溯的 全文缓存。

## 输出

- Zotero 条目标题、条目 key、条目类型、作者、年份、DOI、URL。
- 子条目列表，包括 PDF 附件、笔记、网页快照等。
- PDF 附件 key。
- Windows 可读 PDF 路径和文件存在性检查结果。
- 父文档 规范化文本路径、全文缓存 路径或 PDF 文本抽取结果文件路径。

## 质量规则

- 搜索结果中优先展示 顶层文献条目，避免附件和笔记混入。
- 输出 条目 key，便于用户复查和继续操作。
- 若 API 不可用，必须说明具体错误原因和排查步骤。
- 若 PDF 不存在或无法抽取文本，必须说明可能原因。
- 若父文档或 全文缓存 已存在，必须优先使用现有文本，不重复抽取 PDF。
- 对扫描版 PDF 明确提示可能需要 OCR，当前脚本不做 OCR。

## 安全规则

- 默认只读。
- 不写入 Zotero。
- 不修改 `zotero.sqlite`。
- 不暴露 localhost 端口给外部网络。
- 不保存 API key。
- 不复制、不移动、不删除、不重命名 Zotero PDF。
- 不绕过已有父文档或 全文缓存 重复读取 PDF。

## 完成条件

- 已完成用户请求的搜索、读取、PDF 定位或 PDF 文本抽取步骤。
- 输出保留 Zotero 条目 key，必要时保留 PDF 附件 key。
- 如使用 PDF 文本，说明文本来源、页数范围和输出路径。
- 如使用父文档或 全文缓存，说明 规范化文本/缓存路径和页数/字符范围。
- 如 Local API、条目 key 或 PDF 路径不可用，给出明确错误原因和排查步骤。
- 未写入 Zotero，未读取或修改 `zotero.sqlite`，未移动或复制 Zotero PDF。
