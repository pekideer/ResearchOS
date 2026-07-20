# Reading Card Governance

本操作手册定义 ResearchOS 读书卡的全局治理规则。目标是让读书卡优先服务人工阅读和论文写作，同时保留 Zotero/ResearchOS 自动同步所需的可追溯字段。

## 1. 元数据位置

集中主卡开头保留简短 YAML 头部，只放稳定索引字段；作者、年份、期刊、附件、期刊等级等详细元数据统一放在文末编号标题：

````md
## 7. 元数据（折叠）

<details>
<summary>Reading card metadata</summary>

```yaml
item_key: "[KEY](zotero://select/library/items/KEY)"
title: "..."
authors: "..."
publication_tags: "..."
journal_ranking_source: "EasyScholar"
```

</details>
````

凡显示 Zotero 条目 key，必须使用可点击格式：

```yaml
item_key: "[KEY](zotero://select/library/items/KEY)"
```

HTML 中显示 Zotero 条目 key 时必须使用：

```html
<a href="zotero://select/library/items/KEY">KEY</a>
```

内部脚本可以从上述格式反解 raw key；不要为了机器方便在人工界面裸露 `KEY`。

## 2. 视觉结构

读书卡正文使用编号标题和轻量 HTML 色块。彩色 HTML 标题就是该区块的唯一标题，不得再在其上方额外写一行无格式 Markdown 标题。标准一级阅读区块为：

- `## <span ...>1. 创新摘要</span>`
- `## <span ...>2. 背景</span>`
- `## <span ...>3. 研究内容</span>`
- `## <span ...>4. 研究结果</span>`
- `## <span ...>5. 创新点</span>`
- `## <span ...>6. 借鉴</span>`
- `## 7. 元数据（折叠）`

二级小节采用 `### 2.1`、`### 3.1` 这类编号。一级彩色标题必须保留 Markdown `##` 前缀以进入大纲，颜色背景由标题内的 `<span>` 提供。

卡片题目使用一级 Markdown 标题，不使用 raw HTML `<h1>`。题目必须直接写成可点击 Zotero 链接：

```md
# [可读题名](zotero://select/library/items/KEY)
```

题目下方使用 Markdown 列表显示供人快速识别的条目信息：

- Zotero 条目链接
- 中文题名（英文文献题名必须提供；中文题名不重复显示）
- 作者
- 单位
- 出版年份
- 期刊名称
- 期刊等级

如果读书卡有 Zotero 条目 key，题目和题目下方 `Zotero条目` 行都必须保留可点击链接：

```md
- **Zotero条目：** [KEY](zotero://select/library/items/KEY)
```

不得在读书卡开头使用 raw HTML `<h1>` 或整块 `<div>` 题录信息。原因是 Obsidian 的不同视图、同步预览和外部 Markdown 阅读器可能直接显示原始 HTML 代码，造成“代码泄露”而不是正常可视化。

作者和第一作者单位的权威来源是读书卡生成时的 PDF 首页语义识别，提示词见 `templates/literature/first-page-bibliographic-extraction-prompt.md`。生成卡片时只需把 PDF 第 1 页、必要时 第 2 页 的题录/作者/单位区文本送入语义识别，不要为了单位识别反复上传整篇 PDF 文本。

单位识别的材料读取顺序必须固定为：

1. 先查 ResearchOS 共享事实源：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。
2. 如果父文档 规范化文本 存在，只截取 第 1-2 页，必要时 第 3 页，供语义识别；不得再回头读取 Zotero/PDF 来做同一项单位识别。
3. 如果课题目录 `02-证据材料/全文缓存/ITEMKEY.txt` 已由父文档派生，也可复用；旧 `.research/fulltext_cache/` 仅只读兼容。
4. 只有父文档和 全文缓存 均缺失时，才允许通过 Zotero Local API 只读定位 PDF 并抽取首页文本，并应优先回写父文档维护链路或可回溯的 缓存。
5. 如果既无父文档文本、全文缓存 又无 PDF，必须标注 `needs_check` 或 `not_found`，不得凭机构常识补全。

单位字段规则：

- `authors`：中文作者写成姓+名，中间不加空格；多作者用 `; ` 分隔。
- `first_author_affiliation`：只写第一作者一级单位和国家，格式为 `一级单位, 国家`。
- `first_author_affiliation_raw`：保留 PDF 中支持判断的原始单位片段。
- `first_author_affiliation_source`：写明 `PDF 第 1 页 作者区 语义抽取` 或对应页码。
- `first_author_affiliation_status`：正式使用 `semantic_confirmed`、`manual_confirmed`、`semantic_needs_check`、`semantic_not_found`、`source_unavailable`；新流水线在判断前只写 `not_processed`。历史 `heuristic_candidate` 仍视为待处理，旧 `ok` 仅在同时具有 PDF 页码、语义来源和原始证据时兼容为 `semantic_confirmed`，旧 `not_found` 不视为已经语义核查。

代码不得用正则抽取单位并写入读书卡。`tools/reading_cards/zotero_library_pipeline.py semantic-packet` 是全库、新增和指定条目的统一证据包入口；`tools/reading_cards/build_affiliation_semantic_packet.py` 保留给项目局部缓存。语义结果必须先通过 `semantic-apply` 的 item version、证据哈希、页码、原始片段和状态校验，才能写入 SQLite 和集中读书卡。

## 3. 期刊等级来源

读书卡期刊等级统一来自 SQLite 期刊等级词典；词典缺失且允许联网时，才通过 EasyScholar API 补足。ResearchOS 约定写入：

- `publication_tags`
- `journal_ranking_source: "EasyScholar"`
- `journal_ranking_status`

EasyScholar 只读取和保留以下 field：

```text
sciif, sci, ssci, zhongguokejihexin, eii, cssci, cscd, xr, xrWarn, xrTop
```

其他 EasyScholar 返回字段不得写入 `publication_tags` 或 `.internal` 缓存。输出字段统一使用 `eii`、`xrWarn`、`xr`；读书卡内只保留期刊等级同步闭环所需字段。

显示映射遵循 ZoteroStyle 的缩写习惯：`中国科技核心期刊=科核`、`CSSCI扩展版=C刊扩`、`CSSCI=C刊`、`CSCD=C`、`核心库=核`、`扩展库=扩`、`SSCI=S`、`SCIWARN=🚫`、`EI检索=EI`、`/.*TOP.*/=TOP`；SCI 升级版学科分区压缩为 `工1`、`材2` 等短标签。期刊名称单独一行，期刊等级另起一行用彩色 标记 显示。

限制：

- EasyScholar API key 不得写入 OneDrive、Markdown、日志、截图、prompt、Git 或 kit export。
- API 查询结果写入 `publication_tags` 前，必须保留来源；失败或未匹配时保留核查状态。
- 无法匹配时留空并标注 `journal_ranking_status: "no_match"` 或 `error`，不得推断。
- 期刊等级不得从 Better Notes、ZoteroStyle 或 Zotero Local API 读取。

配置入口见 `RUNBOOKS/easyscholar-api-setup.md`。

## 4. 同步脚本规则

### 阅读状态语义

“待读”固定表示尚未生成读书卡，不使用项目 collection 表达。阅读状态以集中读书卡为事实源，Zotero 只在审批后镜像：

- 无读书卡：`rs:read/todo`；
- 已有读书卡但未明确完成全文精读：`rs:read/initial-card`；
- 读书卡 `read_status` 明确为 `deep`、`全文精读` 或等价状态：`rs:read/deep-read`。

项目相关性与用途尚未完成分配时使用唯一临时 collection `00-待分配-triage`。退出待分配不代表已经生成读书卡；生成或深化读书卡也不自动改变项目用途 collection。

### 4.0 全局集中主卡规则

ResearchOS 读书卡长期采用“集中主卡 + 项目引用”的规则：

1. 一条 Zotero 文献只维护一张权威读书卡正文。
2. 集中读书卡默认放在 `corpus/reading-cards/cards/`；具体项目读书卡写入用户指定项目工作区。
3. 项目、点子或课题目录通过指针页引用集中主卡。
4. ResearchOS SQLite 父文档中使用 `reading_cards` 表登记集中主卡，使用 `reading_card_project_links` 表登记项目、点子或来源目录对集中主卡的引用关系。
5. 来源副本只有在内容哈希与集中主卡一致时才可自动替换为指针页；内容不同必须人工复核。
6. 集中主卡直接维护在 `corpus/reading-cards/cards/`。
7. 一张集中主卡允许关联零个、一个或多个项目；项目关联是多对多关系，不得把单数 `project_id` 解释为唯一归属。

#### 4.0.1 第 6 节多项目借鉴规则

- 第 6 节不得使用含义不明的“本课题”。
- `### 6.1 项目关联与具体用途` 下，每个项目独立使用 `#### 6.1.n 项目名称（project_id）`。
- `6.1.n` 按该条目与项目建立关联的相对时间升序编号；`project_links[].association_order` 保存该稳定相对顺序。历史时间缺失时由人工确认顺序，不得按项目名称、当前目录或模型猜测。
- 每个项目条目必须分别写明：对应项目问题/任务、具体借鉴点、拟使用位置、证据位置、适用边界和状态。
- 同一条文献对不同项目的用途不得合并概括；例如对某项目可用于 Introduction，对另一项目可能只用于方法或结果对照。
- 不依赖具体项目的观点放入 `### 6.2 跨项目可复用观点`。
- 未明确项目名称和具体用途时标为“待映射”，不得由条目主题相似性自动推断项目归属。
- 简短 YAML 头部优先使用内联 JSON 数组 `project_links` 保存多项目索引；旧 `project_id` 只作为兼容字段，后续按人工审查逐卡迁移，不批量猜测。

如需要执行“来源副本改指针页”这类写入，必须先提交脚本必要性说明，并以
`corpus/reading-cards/`、项目工作区和审计留存边界为基准制定执行方案。

当前默认做法：

- 新读书卡：由 LLM 按模板生成，写入集中主卡或用户指定项目工作区。
- 现有读书卡：优先通过人工/LLM 审查判断是否并入集中主卡，不自动批量覆盖。
- 表格和元数据：只使用下列活跃同步工具处理必要的批量字段。

`tools/reading_cards/sync_zotero_metadata_to_cards.py` 只同步 Zotero 标准题录/PDF 元数据，不负责期刊等级。默认使用：

```powershell
python tools\reading_cards\sync_zotero_metadata_to_cards.py --project-root "课题目录" --metadata-layout tail
```

行为：

- 集中主卡保留简短 YAML 头部，用于 `card_id`、`zotero_key`、`project_links`、`title`、`fulltext_status`、`source` 和 `normalized_at`；旧 `project_id` 仅兼容读取。
- 题录、期刊等级、单位、PRISMA 和同步字段写入文末 `## 7. 元数据（折叠）`。
- `item_key` / `zotero_item_key` 写入为 `[KEY](zotero://select/library/items/KEY)`。

`tools/reading_cards/sync_journal_rankings.py` 负责期刊等级，默认使用 ResearchOS 父文档 SQLite 中的 `journal_rankings` 词典表：

```powershell
python tools\reading_cards\sync_journal_rankings.py --cards-root "corpus\reading-cards\cards" --no-api
```

行为：

- 默认不请求 Zotero；加 `--no-api` 时也不请求 EasyScholar API。
- 依据读书卡中的期刊名字段查询期刊等级。
- 查询顺序为：先查 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 中的 `journal_rankings` 词典表，命中后直接把表中等级映射到读书卡；同一期刊只维护一条标准等级记录，多个条目复用该映射。
- 词典表没有该期刊且允许 API 时，才请求 EasyScholar API；API 成功返回后必须先写入 SQLite 词典表，再写入读书卡。
- API 错误不得清空读书卡已有 `publication_tags`。
- 更新可见的“期刊等级”行、`publication_tags`、`journal_ranking_source`，未匹配或错误时保留 `journal_ranking_status`。
- 将白名单字段摘要写入 SQLite 词典表；项目级 CSV 只作为可选报告，不作为权威词典。

`tools/reading_cards/sync_reading_summary_table.py` 读取文末 `## 7. 元数据（折叠）` 中的 YAML fenced block，并读取集中主卡的简短 YAML 头部。正文题录与期刊等级以文末元数据为准。

`tools/reading_cards/build_affiliation_semantic_packet.py` 是单位语义识别前的首选证据准备工具。默认使用：

```powershell
python tools\reading_cards\build_affiliation_semantic_packet.py --project-root "课题目录"
```

行为：

- 默认读取由父文档派生的 `<project-root>/02-证据材料/全文缓存/ITEMKEY.txt`；旧 `.research/fulltext_cache/` 仅只读兼容。没有项目缓存时，应先用父文档上下文包准备材料。
- 只输出 第 1-3 页 的紧凑证据包和 JSONL，不读取 Zotero，不读取 PDF，不写读书卡。
- 证据包只作为临时语义判断材料，不作为长期项目成果保存；完成判断后，主结果应写入集中读书卡文末元数据。
- 跨文献第一作者机构索引长期保存到 `corpus/indexes/first-author-affiliations.csv`。
- 项目 `03-文献矩阵/` 只保留项目视角的团队追踪、矩阵和 gap 判断，不长期保存通用机构缓存或大段语义证据包。
- 后续 AI/人工语义判断必须基于临时证据包、父文档 规范化文本 或同一 全文缓存 片段。

旧卡片中的 `heuristic_candidate` 只作为迁移状态保留，必须重新进入首页语义证据包；不得用旧候选直接补齐正式单位。

### 4.1 Zotero 人工标注生成区

Zotero 原生 PDF annotation 回流时，只在 `## 7. 元数据（折叠）` 前维护一个 `### 6.99 人工阅读标注（Zotero 同步）` 生成区，并以 `researchos:zotero-annotations:start/end` 注释标记边界。

- 同步程序只能替换该生成区，不得自动改写第 1-6 区其他正文。
- `annotationText` 标为“原文摘录”，`annotationComment` 标为“人工判断”；两者不得混写成同一事实。
- 每条活动标注优先显示 `annotationPosition.pageIndex + 1` 对应的 PDF 物理页序，并在父文档已有 `pdf_texts.pages_total` 时显示为 `当前页/总页数`；`annotationPageLabel` 只作为独立的文献印刷页码，不得替代 PDF 页序。
- 每条活动标注保留可点击 PDF 页码链接；annotation key 只进入链接和机器字段，不作为可见名称。
- 区域图像、手写和无上下文短句标为“需要核查”。
- annotation 被删除后可从活动生成区移除，但父文档继续保留软删除历史。
- 正式吸收进研究结果、创新点或借鉴正文前，必须经过人工或 LLM 证据审查。

## 5. 质量门禁

- 读书卡的视觉样式不得牺牲证据可追溯性。
- 元数据不能暴露 API key、Zotero 数据库路径或敏感缓存。
- Zotero `extra` 不写入读书卡。该字段常含插件/引用管理扩展信息，反复 YAML/JSON 转义会造成卡片体积异常膨胀；如需核查，应回到 Zotero 元数据快照或 `.internal` 表。
- 期刊标签必须来自 EasyScholar 或人工确认，不得推断。
- 第一作者单位必须来自 PDF 首页/前两页、必要时第 3 页的语义识别或人工确认；只保留第一作者对应的第一个一级单位和国家，不得凭机构常识补全。`heuristic_candidate`、`existing_card_candidate` 和旧 `not_found` 不得作为确定单位显示或发布到 Zotero。
- 不确定字段使用 `?`、留空或 `需要核查`。
- 读书卡同步阅读总表后，必须能回溯到 Zotero 条目 key 和读书卡路径。
