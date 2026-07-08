# 读书卡首页题录信息抽取提示

用于生成或更新读书卡时，从 PDF 首页或前两页文本中语义识别作者与第一作者单位。不要把该提示词用于整篇论文结论总结；它只处理题录区、作者区、单位区、审稿节点和摘要前后的文献信息。

## 输入

- Zotero 题录：标题、作者、年份、期刊、DOI、条目 key。
- PDF 第 1 页文本，必要时加第 2 页文本；优先来自课题目录 `.research/fulltext_cache/<cards-root-name>/ITEMKEY.txt`，缓存存在时不得为了单位识别重新读取 Zotero/PDF。
- 已有读书卡元数据，可作为参考但不得覆盖 PDF 明确信息。

## 任务

请只根据 PDF 首页或前两页的题录/作者/单位区域，抽取并规范化以下字段：

```yaml
authors: "作者显示名；多作者用 ; 分隔"
first_author_affiliation: "一级单位, 国家"
first_author_affiliation_raw: "PDF 中支持该判断的原始单位片段"
first_author_affiliation_source: "PDF 第 1 页 作者区 语义抽取"
first_author_affiliation_status: "ok|needs_check|not_found"
```

## 作者规范

- 中文作者写成“姓+名”，中间不加空格，例如 `张三`、`欧阳明`。
- 中文作者之间用 `; ` 分隔，不使用英文逗号拆开姓名。
- 英文或拼音作者不翻译，尽量保留 PDF 或 Zotero 题录中的显示顺序。
- 不确定姓名边界时保留原文，并把 `first_author_affiliation_status` 标为 `needs_check`。

## 单位规范

- 目标是第一作者的一级单位和国家，不要输出二级单位、实验室、学院、系、城市、邮编、邮箱、审稿日期或通讯作者标记。
- 常见单位链为：`二级单位, 一级单位, 城市, 国家, 邮编`。此时保留一级单位和国家，例如 `School of Architecture, Chongqing University, Chongqing, China, 400045` 输出 `Chongqing University, China`。
- 中文单位链同理，例如 `重庆大学建筑城规学院，重庆大学，重庆，中国，400045` 输出 `重庆大学, 中国`。
- 如果单位只给出一级单位和城市/国家，直接使用可识别的一级单位和国家。
- 如果第一作者有多个单位，优先取第一作者编号对应的第一个一级单位；若无法判断，写最可能项并标 `needs_check`。
- 如果首页/前两页没有足够信息，写：
  - `first_author_affiliation: "需要核查"`
  - `first_author_affiliation_raw: "?"`
  - `first_author_affiliation_status: "not_found"`

## 边界

- 不得凭机构常识补全未出现的国家或单位。
- 不得使用本地启发式抽取结果作为最终依据；它只能作为待核查线索。
- 如果 Zotero 题录作者与 PDF 首页作者冲突，优先保留 PDF 首页作者区，并在读书卡“需要核查”中说明。
- 输出写入读书卡顶部“作者/单位”信息和文末 `## 7. 元数据（折叠）`，不得写入 YAML 头部。
