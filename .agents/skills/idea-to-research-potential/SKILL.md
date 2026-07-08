---
name: idea-to-research-potential
description: 捕获用户的碎片化想法、知识片段、灵感问题并沉淀为可复用知识体系；当用户说“记录这个点子”“评估这个想法”“碎片知识入库”“判断研究潜力”“把想法变成研究方向”“形成点子汇报”时使用。用于生成 IDEA 编号、点子卡、来源记录、研究简报，并按快速/侦察/深度分级判断研究潜力；深度阶段若查阅外部数据库或出版商并发现候选文献，必须输出外部候选阅读清单及建议文献集/标签。
---

## 目标

用于把零散想法变成可追踪的科研资产。该 skill 负责记录、归类、初步检索、潜力判断和后续转交，不把未核查点子包装成成熟选题。

## 默认存储

- 已有项目路径：写入用户指定项目工作区，优先使用 `03-decisions/`、`04-reports/`、`annotations/` 和必要的 `.research/` 索引。
- 暂无项目归属：写入 `00_ResearchOS` 平级的 `0.Inbox/02-unassigned-ideas/`，等待人工分流。
- ResearchOS 本体：只保存能力说明、模板、skill 规则和治理记录；不保存具体点子正文。

点子捕获由本 skill、模板和项目工作区/平级 `0.Inbox` 完成。

## 点子文件夹结构

每个项目工作区内的点子材料必须按用途分文件夹存放，避免把所有材料堆在项目根目录或 ResearchOS 根目录。

- 根目录只放稳定控制文档：`IDEA-..._idea-card.md`、`IDEA-..._research-brief.md`、`IDEA-..._live-direction.md`、`IDEA-..._source-log.md`。
- `reading-cards/`：读书卡、deep-reading、读书卡快捷入口和单篇文献精读材料，例如 `IDEA-..._<KEY>_deep-reading.md`、`IDEA-..._<KEY>_reading-card.shortcut.md`。
- `reports/`：给人看的阶段性报告、节点汇报、综述汇报和判断报告，例如 `IDEA-..._six-paper-review-report.md`。
- `search/`：检索式、检索图谱、外部检索记录、外部候选阅读清单，例如 `IDEA-..._search-map.md`、`IDEA-..._external-search-log.md`、`IDEA-..._external-reading-candidates.md`。
- `candidates/`：本地候选池、阅读优先级列表、待筛选文献池，例如 `IDEA-..._candidate-pool-local.md`、`IDEA-..._reading-priority-list.md`。
- `matrices/`：文献矩阵、节点计划、研究缺口/选题表格和其他比较表，例如 `IDEA-..._literature-matrix.csv`、`IDEA-..._literature-review-node-plan.md`。
- `annotations/`：人工阅读批注收件箱、处理记录和已处理归档，例如 `inbox.md`、`review-log.md`、`processed/YYYY-MM-processed.md`；活跃收件箱只保留待处理或需确认条目。
- `.internal/`：机器可读 CSV/JSON、中间缓存、未整理导出和审计文件。

如果现有 idea 目录已有根级读书卡、报告、矩阵或检索文件，继续该 idea 前应先进入对应项目工作区，并更新 来源记录 或索引中的相对路径。ResearchOS 根目录不新增这类文件。

## 工作流

1. 捕获原始想法：保留用户原文、日期、触发上下文、关联课题和初步标签。
2. 分配稳定编号：使用 `IDEA-YYYYMMDD-###`，文件夹名追加短 slug。
3. 分级处理：
   - `quick`：结构化、归类、初步潜力判断。
   - `scout`：在 quick 基础上读取本地 ResearchOS 材料、读书卡和可用 Zotero 题录线索；这是宽候选池阶段，允许纳入直接相关、机制相邻、方法相邻、场景相邻和背景边界文献。
   - `deep`：在 scout 基础上进行外部检索；先扩展候选池，再按证据强度分层，不在点子阶段直接用成熟 研究缺口 标准排除边缘文献。未实际检索的信息必须标注“需要核查”。如果实际查阅网络数据库、出版商页面或 DOI/引用链并发现值得读或待进一步确认的文献，必须生成 `search/IDEA-..._external-reading-candidates.md` 和可选 `.csv`。
4. 输出固定研究简报：一句话概括、所属课题方向、研究进展、候选文献池、可能研究缺口、潜力评分、是否值得继续推进的初步判断、建议方向、补读关键词、下一步行动和不确定项。
5. 对候选文献按“直接相关、机制相邻、方法相邻、场景相邻、背景材料、暂不纳入”分层；只有直接相关和明确支撑问题的相邻文献进入研究缺口证据，其余保留在来源记录作为发散线索。CSV/JSON 机器字段可继续使用稳定英文值，但面向用户的 Markdown 必须显示中文。
6. 维护点子实时方向文档：在每次新增检索、精读、综述矩阵、人工判断或方向收束后，更新 `IDEA-..._live-direction.md`，用于人工快速查看当前理解、材料池、证据地图、决策记录和下一步。
   - `当前理解` 必须包含一个可实时改写的正式学术论证段：用完整段落写出“基于哪些证据，可以暂时形成什么观点；该观点的边界是什么；下一步要验证什么假设/设想”。不得只写零散摘要。
   - `后续假设/设想` 必须显式列出，区分可检索验证的文献假设、可方法化验证的研究假设和暂时保留的探索设想。
   - `人工方向定位` 必须作为固定块保留，用于记录人工确认后的方向选择、主线/支线、纳入范围、排除范围、决策日期和后续处理。
7. 对值得继续推进或需要调整后再推进的点子，转交 `gap-to-topic`；完成推进判断后再转交 `research-question-framing`。

## 外部候选阅读清单

外部候选阅读清单用于保存“值得读、但还要进一步确认”的文献线索。它不是精读结论，也不是 Zotero 写入计划。优先使用 `templates/external-reading-candidates.md` / `.csv` 字段，每条至少包含：

- `title`、`authors`、`year_or_date`、`publication_or_source`、`document_type`、`doi`、`url`
- `discovered_from`、`search_query_or_page`、`discovered_at`
- `reason_to_read`：说明它对当前 idea 的作用，如验证 研究缺口、提供方法、提供边界条件、作为相邻机制或背景
- 候选分层：面向用户显示为“直接相关、机制相邻、方法相邻、场景相邻、背景材料、暂不纳入”；机器字段可保存为 `core`、`adjacent-mechanism`、`adjacent-method`、`adjacent-scenario`、`background` 或 `exclude`
- 阅读优先级：面向用户显示为“高、普通、低、暂缓”；机器字段可保存为 `high`、`normal`、`low` 或 `hold`
- `suggested_collection`：建议导入 Zotero 后放入的文献集；若关联具体项目，优先使用项目覆盖层，如 `00.09-watchlist-待补读与跟踪`、`00.02-review-core-综述核心文献`、`00.04-method-source-方法与模型来源`
- `suggested_tags`：建议 `rs:read/todo`、`rs:priority/*`、`rs:use/*`、主题标签、来源标签
- `duplicate_check`：与 Zotero 父文档或本地候选池比对后的状态；未比对必须写 `not-checked`
- `next_action`：导入 Zotero、补全文、生成读书卡、引用追踪、转入矩阵或暂缓

如果没有实际访问外部来源，不得生成看似已发现的候选文献；只能写检索式和“待执行”。

## 人读引用规则

- 供人查阅的 点子卡、研究简报、来源记录、实时方向文档、综述报告、快捷入口和 Markdown/YAML/HTML 表格中，文献显示标签默认使用 `[第一作者姓(年份)](zotero://select/library/items/KEY)`，例如 `[Wang(2025)](...)` 或 `[于(2011)](...)`。
- 不在人工正文中用 条目 key 充当引用标签；条目 key 只保留在 `.internal`、CSV/JSON、脚本输入输出、文末元数据或排障审计字段中。
- 若人工文档确需显示 条目 key，必须同时保留可点击 Zotero 链接。

## 命令

当前默认做法是由 Codex 按本 skill 和模板在指定项目工作区或平级 `0.Inbox/02-unassigned-ideas/` 生成文本。

## 质量规则

- 不编造文献、DOI、作者、期刊、数据、图表或领域进展。
- 所有外部研究进展、文献线索和 Zotero 条目 key 必须可回溯；没有检索就写“需要核查”。
- 外部候选清单中的题录、DOI、URL、来源、发现日期、建议文献集/标签和重复核查状态必须可回溯。
- 不把“当前材料未覆盖”直接写成“领域空白”。
- 点子早期不是系统综述筛选：默认先宽收集再收束，不能因为文献只属于相邻机制、方法或场景就立即排除；排除必须说明为什么对判断大方向没有帮助。
- 面向用户的潜力评分只能写“高、中、低、暂缓”；机器索引字段可保存为 `high`、`medium`、`low` 或 `hold`。
- 人工 Markdown/HTML 中正文引用使用 `Author(year)` 可点击标签；`.internal` CSV 可保留 raw 条目 key。
- 人工文档必须遵守 `POLICIES/OUTPUT_LANGUAGE_POLICY.md`：普通概念用中文表达；英文只保留文献题名、DOI/URL、数据库/软件/API 名、路径/命令/字段名、skill 名、文献专门术语和领域共同认可缩写。必要术语首次出现尽量写成“中文译名（英文原文）”。
- `IDEA-..._live-direction.md` 的“正式论证段”必须克制：不能把未完成检索写成领域结论，不能把候选设想写成已验证假设。
- 建议文献集/标签 仅用于后续导入和整理，不自动写入 Zotero。
- 新增 idea 文件必须写入对应子目录；除 点子卡、研究简报、实时方向文档、来源记录 外，不在根目录新增材料；人工阅读批注写入 `annotations/inbox.md`。
- kit export 时不得导出真实点子正文或项目工作区材料，除非已脱敏。

## 完成条件

- 点子已写入指定项目工作区；暂无归属时已进入平级 `0.Inbox/02-unassigned-ideas/`。
- 点子卡、来源记录 和 研究简报 均存在。
- `IDEA-..._live-direction.md` 存在，并反映最近一次检索、精读、综述或人工方向判断；其中包含正式论证段、后续假设/设想和人工方向定位块。
- 简报 明确区分事实、推断、建议、假设和“需要核查”。
- 来源记录 已记录宽候选池、分层理由和下一批待读文献，而不仅是已精读核心文献。
- 读书卡、阶段性报告、检索材料、候选池、矩阵和人工批注分别位于 `reading-cards/`、`reports/`、`search/`、`candidates/`、`matrices/`、`annotations/`，根目录未堆放这些材料。
- 若 深度阶段实际发现外部候选文献，`search/IDEA-..._external-reading-candidates.md` 已记录题录、DOI/URL、来源、建议文献集/标签、重复核查状态和下一步行动。
- 若建议继续推进，已说明应进入 `gap-to-topic` 的具体输入。
