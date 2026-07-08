# ResearchOS Corpus

`corpus/` 是 ResearchOS 的共享事实源和语料入口，供其他项目工作区读取。

它集中保存可跨项目复用的 Zotero SQLite 父文档、规范化 PDF 文本、集中读书卡和索引。科研判断、读书卡写作、综述矩阵和报告仍由 Codex 基于这些语料完成，输出写入用户指定项目路径。

## 目录

- `zotero/`：Zotero SQLite 父文档和相关索引。
- `fulltext/`：PDF 抽取文本和 AI 规范化文本。
- `reading-cards/`：集中读书卡正文和索引。
- `indexes/`：跨项目语料索引和映射表。

## 事实源边界

`corpus/` 是唯一共享事实源入口。`.researchos/outputs/machine/` 只保存机器运行产物、试运行计划和执行记录，不再保存 Zotero 父文档或全文缓存副本。

## 禁止内容

- 不保存 Zotero PDF 原件。
- 不保存 API key、`.env`、账号、token 或代理完整 URL。
- 不保存未明确允许共享的具体项目私密正文。
