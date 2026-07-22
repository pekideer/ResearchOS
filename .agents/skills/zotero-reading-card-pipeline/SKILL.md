---
name: zotero-reading-card-pipeline
description: 编排一个、多个、新增或全库 Zotero 条目的父文档、PDF/OCR、规范化文本、期刊词典、第一作者单位语义包、集中读书卡 staging 与统一契约审计；当用户说“生成某个条目的阅读卡并同步到 Zotero”“处理新增文献”“全库生成读书卡”“识别单位并建卡”或同义自然语言时使用。科研内容精读委托 `paper-deep-reading`，真实 Zotero note 发布委托 `zotero-reading-card-annotation-sync`。
---

## 职责

作为 Zotero 到读书卡的确定性编排器，负责范围、语料、批次、状态、staging、审计和发布移交；不在代码中替代模型判断研究问题、结论、创新或项目用途。

## 必须读取

1. `RUNBOOKS/reading-card-governance.md`
2. `WORKFLOWS.md` 工作流 1C；涉及 note/annotation 时再读 1B
3. `QUALITY_GATES.md` 的证据、来源、输出、统一读书卡契约和 Zotero 检查
4. 真实 Zotero 写入时读取 `POLICIES/ZOTERO_WRITE_POLICY.md` 与 `RUNBOOKS/zotero-web-api-write-canary.md`

## 执行顺序

1. 从用户表达、item key、当前项目或唯一题名确定范围；只有无法唯一定位时才提问。
2. 优先复用 SQLite 父文档、规范化全文和集中主卡；缺材料时运行 `zotero_library_pipeline.py run`，所有写入先进入机器本地 staging。
3. 对待处理条目运行 `semantic-packet`；当前 agent 读取第 1–3 页证据并判断第一作者、单位与国家，再用 `semantic-apply` 预检和受控写入 staging。
4. 无卡条目可由流水线生成只陈述材料状态的 `auto_initial_screening` 骨架；骨架不作科研语义结论，也不生成未映射的第 6 节。
5. 用户要求精读、范围内有可用全文或增量治理要求完成精读时，把单篇证据包逐条交给 `paper-deep-reading`；编排器不得自行改写第 1–6 节。
6. 对每张卡调用统一 `reading_card_contract`；`audit --curation-strict` 使用完整正文、证据回执和第 6 节结构判断，不再以两个头部字段代表精读完成。
7. 通过本地审计后说明 `corpus_publication_required`；共享 corpus 只由 Corpus Publisher 发布。
8. 用户要求同步 Zotero 时转入 `zotero-reading-card-annotation-sync`。发布 dry-run 和真实写入会再次校验同一契约；未经具体批准不写。

## 保护规则

- 现有人工/精读卡的科研正文只能由 `paper-deep-reading` 或人工审查更新；批处理工具仅维护确定性题录、单位、期刊、索引和状态字段。
- 语义结果绑定 item version、证据哈希、检查页码、原始片段和来源；漂移时废弃旧结果。
- `heuristic_candidate`、旧 `not_found`、`existing_card_candidate` 和 `not_processed` 不是已完成单位识别。
- 初筛、局部阅读和全文精读是不同合同状态；占位卡、可用全文和两项精读标记都不能单独证明精读完成。
- 不读取或修改 `zotero.sqlite`，不修改 PDF，不自动写 Zotero，不直接写共享 corpus。

## 完成条件

- 范围内每个条目都有明确的父文档、PDF/文本、期刊、单位语义和读书卡合同状态。
- 全文条目只有在 `paper-deep-reading` 完成且合同返回 `deep_read_complete=true` 后才记为精读。
- `audit --strict --curation-strict` 数量守恒并列出所有阻断；staging 与共享发布状态分开报告。
- Zotero 写入停在用户批准边界；如已批准，则按单条金丝雀、逐条回读和最终审计执行。
