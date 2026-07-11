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

作者和第一作者单位的权威来源是读书卡生成时的 PDF 首页语义识别，提示词见 `templates/reading-card-first-page-bibliographic-extraction-prompt.md`。生成卡片时只需把 PDF 第 1 页、必要时 第 2 页 的题录/作者/单位区文本送入语义识别，不要为了单位识别反复上传整篇 PDF 文本。

单位识别的材料读取顺序必须固定为：

1. 先查 ResearchOS 共享事实源：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。
2. 如果父文档 规范化文本 存在，只截取 第 1-2 页，必要时 第 3 页，供语义识别；不得再回头读取 Zotero/PDF 来做同一项单位识别。
3. 如果课题目录 `.research/fulltext_cache/ITEMKEY.txt` 已由父文档派生，也可复用该缓存。
4. 只有父文档和 全文缓存 均缺失时，才允许通过 Zotero Local API 只读定位 PDF 并抽取首页文本，并应优先回写父文档维护链路或可回溯的 缓存。
5. 如果既无父文档文本、全文缓存 又无 PDF，必须标注 `needs_check` 或 `not_found`，不得凭机构常识补全。

单位字段规则：

- `authors`：中文作者写成姓+名，中间不加空格；多作者用 `; ` 分隔。
- `first_author_affiliation`：只写第一作者一级单位和国家，格式为 `一级单位, 国家`。
- `first_author_affiliation_raw`：保留 PDF 中支持判断的原始单位片段。
- `first_author_affiliation_source`：写明 `PDF 第 1 页 作者区 语义抽取` 或对应页码。
- `first_author_affiliation_status`：`ok`、`needs_check` 或 `not_found`。

不得把本地启发式抽取结果直接当作最终单位。`tools/reading_cards/build_affiliation_semantic_packet.py` 用于从父文档派生文本或 全文缓存 生成供 AI/人工语义判断的首页证据包。`tools/reading_cards/sync_first_author_affiliations.py` 用于卡片排查、缓存复用或人工核查线索；它默认应优先读取父文档派生文本或 `.research/fulltext_cache/...`，再读取 `03-文献矩阵/.internal/affiliation-cache/`，只有这些缓存缺失时才只读解析 Zotero/PDF 前 1-2 页文本。

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

### 4.0 全局集中主卡规则

ResearchOS 读书卡长期采用“集中主卡 + 项目引用”的规则：

1. 一条 Zotero 文献只维护一张权威读书卡正文。
2. 集中读书卡默认放在 `corpus/reading-cards/cards/`；具体项目读书卡写入用户指定项目工作区。
3. 项目、点子或课题目录通过指针页引用集中主卡。
4. ResearchOS SQLite 父文档中使用 `reading_cards` 表登记集中主卡，使用 `reading_card_project_links` 表登记项目、点子或来源目录对集中主卡的引用关系。
5. 来源副本只有在内容哈希与集中主卡一致时才可自动替换为指针页；内容不同必须人工复核。
6. 集中主卡直接维护在 `corpus/reading-cards/cards/`。

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

- 集中主卡保留简短 YAML 头部，用于 `card_id`、`zotero_key`、`project_id`、`title`、`fulltext_status`、`source` 和 `normalized_at`。
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

- 默认读取由父文档派生的 `<project-root>/.research/fulltext_cache/ITEMKEY.txt`；没有项目缓存时，应先用父文档上下文包准备材料。
- 只输出 第 1-3 页 的紧凑证据包和 JSONL，不读取 Zotero，不读取 PDF，不写读书卡。
- 证据包只作为临时语义判断材料，不作为长期项目成果保存；完成判断后，主结果应写入集中读书卡文末元数据。
- 跨文献第一作者机构索引长期保存到 `corpus/indexes/first-author-affiliations.csv`。
- 项目 `03-文献矩阵/` 只保留项目视角的团队追踪、矩阵和 gap 判断，不长期保存通用机构缓存或大段语义证据包。
- 后续 AI/人工语义判断必须基于临时证据包、父文档 规范化文本 或同一 全文缓存 片段。

`tools/reading_cards/sync_first_author_affiliations.py` 用于卡片核查和生成候选线索；若其结果与 PDF 首页语义识别冲突，以语义识别结果为准，并把冲突写入需要核查项。

## 5. 质量门禁

- 读书卡的视觉样式不得牺牲证据可追溯性。
- 元数据不能暴露 API key、Zotero 数据库路径或敏感缓存。
- Zotero `extra` 不写入读书卡。该字段常含插件/引用管理扩展信息，反复 YAML/JSON 转义会造成卡片体积异常膨胀；如需核查，应回到 Zotero 元数据快照或 `.internal` 表。
- 期刊标签必须来自 EasyScholar 或人工确认，不得推断。
- 第一作者单位必须来自 PDF 首页/前两页语义识别或人工确认；只保留一级单位和国家，不得凭机构常识补全。
- 不确定字段使用 `?`、留空或 `需要核查`。
- 读书卡同步阅读总表后，必须能回溯到 Zotero 条目 key 和读书卡路径。
