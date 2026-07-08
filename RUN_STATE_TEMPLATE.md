# ResearchOS 长任务状态入口

本文件只保留根目录入口。长任务状态模板和使用说明已归入模板层：

- 状态 JSON 模板：`templates/research-run-state.json`
- 使用说明：`templates/research-run-state.md`
- 课题 manifest 模板：`templates/research-project-manifest.yml`
- 实验矩阵模板：`templates/research-experiment-matrix.yml`
- 数据字典模板：`templates/research-data-dictionary.yml`
- 开放问题模板：`templates/research-open-questions.md`

处理“继续上次”“恢复上下文”“当前课题进展”时，应优先读取具体课题目录下的 `.research/`，再参考上述模板。

不要在 `.research/` 或 run state 中保存 API key、Zotero 数据库路径、PDF 缓存、Zotero storage 或敏感未发表全文。
