# Zotero 只读策略

ResearchOS 默认通过同步盘共享事实源执行只读文献任务。父文档包括 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 和 `corpus/fulltext/zotero-library-normalized/`；旧 `.researchos/outputs/machine/` 路径仅作为代码适配前的兼容副本。Zotero Local API 只读流程主要用于维护父文档、搜索条目、读取元信息、定位 PDF 和抽取 PDF 文本。

## 允许行为

- 搜索 Zotero 条目。
- 读取顶层条目元信息。
- 读取子条目。
- 定位 PDF 附件路径。
- 抽取 PDF 文本。
- 读取 ResearchOS 同步盘 SQLite 父文档和 规范化 PDF 文本。
- 通过 `tools/zotero_library_index.py` 更新 SQLite 与文本缓存。
- 输出 条目 key、PDF 附件 key、题录信息、路径存在性和文本抽取结果。

## 禁止行为

- 不写入 Zotero。
- 不创建、移动、删除、修改 Zotero 条目、标签、文献集、笔记 或 PDF。
- 不直接读取或修改 `zotero.sqlite`。
- 不复制、移动、删除、重命名 Zotero PDF。
- 不把 Zotero storage、PDF 缓存、Zotero 数据库或 API key 放进 OneDrive 项目目录。

## Local API 设置

- 默认地址：`http://localhost:23119/api/`
- 默认 user ID：`0`
- 推荐环境变量：`ZOTERO_API_BASE`、`ZOTERO_USER_ID`

## Local API 不可用时排查

1. 确认 Zotero 桌面端已打开。
2. 确认 Zotero 设置中已启用 Local API。
3. 确认本机端口 `23119` 未被防火墙或安全软件拦截。
4. 确认请求地址为 `http://localhost:23119/api/`。

## 完成标准

- 只读任务输出可复核的 条目 key、来源字段或错误原因。
- 普通阅读、综述、AI 分类和治理任务优先使用父文档；Local API/PDF 抽取只用于父文档维护或故障排查。
- 未发生 Zotero 写入和 PDF 文件变更。
