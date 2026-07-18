---
name: zotero-reading-card-pipeline
description: 对一个、多个、新增或全库 Zotero 条目连续完成父文档与 PDF 文本准备、期刊词典查询、第一作者单位语义识别、集中初筛读书卡生成/更新，并在用户明确批准后衔接 Zotero 笔记发布；当用户说“生成某个条目的阅读卡并同步到 Zotero”“处理新增文献”“全库生成读书卡”“识别单位并建卡”或同义自然语言时使用。
---

## 目标

把自然语言中的 Zotero 条目处理请求闭环为“语料准备 → 模型语义判断 → 读书卡 → 审计 → 经审批的 Zotero 同步”，避免把 Python 启发式候选冒充模型确认结果。

## 必须读取

1. `RUNBOOKS/reading-card-governance.md`
2. `WORKFLOWS.md` 工作流 1C；涉及 Zotero 笔记或 annotation 时再读工作流 1B
3. `QUALITY_GATES.md` 的证据、来源、输出和 Zotero 检查
4. 涉及真实 Zotero 写入时读取 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`

## 范围判断

- 从用户表达、item key、当前项目上下文或唯一题名匹配确定范围；不能唯一定位时才提问。
- `全库`、`新增`、一个或多个 item key 使用同一流程，只改变 scope 和批次大小。
- “生成读书卡并同步到 Zotero”包含本地处理和外部写入两个阶段；用户未明确批准真实写入时，只完成本地卡和发布预检。

## 执行顺序

1. 优先读取 ResearchOS SQLite、规范化全文和既有集中读书卡；材料缺失时才运行 `tools/reading_cards/zotero_library_pipeline.py run` 补齐父文档、PDF 文本、OCR 状态和期刊词典。
2. 运行 `semantic-packet` 为尚未语义处理的条目生成第 1–3 页证据包。Python 候选只能作为线索。
3. 模型亲自阅读证据包，按 `templates/literature/first-page-bibliographic-extraction-prompt.md` 判断作者显示名、第一作者标号、单位标号、第一个一级单位和国家；首页是封面时继续检查第 2–3 页。
4. 输出结构化 JSONL，并先用 `semantic-apply` 默认预检；通过后才用 `--write-local` 写 ResearchOS SQLite 和集中读书卡。
5. 使用模型根据题录、摘要和可用全文生成或更新初筛读书卡 1–5、7 章。不得把摘要或片段写成已核实全文结论；默认不生成第 6 章。
6. 运行 `audit --strict`。只要仍有 `heuristic_candidate`、旧 `not_found`、`existing_card_candidate` 或 `not_processed`，就不得报告单位识别完成。
7. 用户要求同步 Zotero 时，转入 `zotero-reading-card-annotation-sync`：先生成 live dry-run 和预览，再按明确批准计划执行单条金丝雀；未批准不写。

## 单位状态

- `heuristic_candidate`：机器候选，仍待模型语义处理，不得作为确定单位发布。
- `semantic_confirmed`：模型基于指定页码、原始单位片段确认。
- `manual_confirmed`：用户人工确认。
- `semantic_needs_check`：模型已检查但作者—单位对应仍不确定。
- `semantic_not_found`：模型已检查规定页数但未发现足够信息。
- `source_unavailable`：缺 PDF、OCR 未完成或文本抽取失败。
- `not_processed`：尚未进入语义阶段。

## 保护规则

- 现有人工/精读卡只更新受控题录、单位和元数据字段，不覆盖人工正文、annotation 生成区、项目关联或第 6 章。
- 语义结果必须包含 item key、当前 item version、证据哈希、检查页码、原始片段、来源和状态；材料变化后拒绝旧结果。
- 期刊等级只来自 SQLite 词典、EasyScholar 或人工确认，不由模型猜测。
- 不读取或修改 `zotero.sqlite`，不修改 PDF，不自动写 Zotero。
- 本 skill 不授权修改 ResearchOS 本身；发现能力缺口时遵守 `AGENTS.md` 的 ResearchOS 自修改门禁。

## 完成条件

- 请求范围内每个条目都有明确 PDF/文本、期刊、单位语义和读书卡状态。
- 确定单位均有页码、原始证据和 `semantic_confirmed`/`manual_confirmed` 状态。
- 语义未决或来源不可用均显式说明原因，不使用裸 `?`。
- 严格审计数量守恒，且 Zotero 写入停在用户批准边界。
