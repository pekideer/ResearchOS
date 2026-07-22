---
reading_card_schema: "researchos-reading-card/v2"
card_id: "{{ card_id }}"
zotero_key: "{{ item_key_raw }}"
project_links: {{ project_links_json }}
title: "{{ title }}"
fulltext_status: "{{ fulltext_status }}"
generation_mode: "{{ generation_mode }}"
reading_depth: "{{ reading_depth }}"
reviewed_sections: "{{ reviewed_sections }}"
source_text_sha256: "{{ source_text_sha256 }}"
source: "{{ text_source }}"
normalized_at: "{{ normalized_at }}"
---

# [{{ title }}](zotero://select/library/items/{{ item_key_raw }})

- **Zotero条目：** [{{ item_key_raw }}](zotero://select/library/items/{{ item_key_raw }})
- **中文题名：** {{ title_zh }}
- **作者：** {{ authors }}
- **单位：** {{ first_author_affiliation }}
- **出版年份：** {{ year }}
- **期刊名称：** {{ venue }}
- **期刊等级：** {{ publication_tags_标记s }}

## <span style="display:block; margin: 0.65em 0 0.45em; padding: 0.45em 0.75em; border-left: 7px solid #94a3b8; background: #f8fafc; color: #334155; font-size: 1.05em; font-weight: 800; line-height: 1.35;">🧾 1. 创新摘要</span>

{{ one_paragraph_review }}

---

## <span style="display:block; margin: 0.65em 0 0.45em; padding: 0.45em 0.75em; border-left: 7px solid #f59e0b; background: #fff7e6; color: #c2410c; font-size: 1.05em; font-weight: 800; line-height: 1.35;">📜 2. 背景</span>

### 2.1 一句话定位

事实：

推断：

### 2.2 一段话综述

背景：？目的：？方法：？结论：？意义：？

---

## <span style="display:block; margin: 0.65em 0 0.45em; padding: 0.45em 0.75em; border-left: 7px solid #86efac; background: #f0f9ec; color: #166534; font-size: 1.05em; font-weight: 800; line-height: 1.35;">🔬 3. 研究内容</span>

### 3.1 研究问题

### 3.2 方法路线

### 3.3 数据/模型/实验条件

### 3.4 关键变量

- 自变量：
- 因变量：
- 控制变量：
- 关键指标：

---

## <span style="display:block; margin: 0.65em 0 0.45em; padding: 0.45em 0.75em; border-left: 7px solid #fb7185; background: #f8fafc; color: #581c87; font-size: 1.05em; font-weight: 800; line-height: 1.35;">🚩 4. 研究结果</span>

### 4.1 主要结论

事实：

作者解释：

我的推断：

### 4.2 局限性与边界

---

## <span style="display:block; margin: 0.65em 0 0.45em; padding: 0.45em 0.75em; border-left: 7px solid #22d3ee; background: #ecfeff; color: #155e75; font-size: 1.05em; font-weight: 800; line-height: 1.35;">📌 5. 创新点</span>

参照对象：

判断：

---

## <span style="display:block; margin: 0.65em 0 0.45em; padding: 0.45em 0.75em; border-left: 7px solid #7dd3fc; background: #e0f2fe; color: #0369a1; font-size: 1.05em; font-weight: 800; line-height: 1.35;">🔬 6. 借鉴</span>

### 6.1 项目关联与具体用途

> 一条文献可以关联零个、一个或多个项目。每个项目必须单独建立一条记录，不得使用含义不明的“本课题”；`6.1.n` 按该条目项目关联的相对时间顺序编号，较早关联者在前。若 `project_links` 为空，删除下方 `6.1.1` 示例，不得保留空项目块。

#### 6.1.1 {{ project_name }}（`{{ project_id }}`）

- **对应项目问题/任务：**
- **具体借鉴点：**
- **拟使用位置：** Introduction / 方法 / 实验设计 / 结果对照 / Discussion / 其他
- **证据位置：**
- **适用边界：**
- **状态：** 候选 / 已核查 / 已采用

> 如关联其他项目，继续增加 `6.1.2`、`6.1.3`，并完整填写同一组字段。

### 6.2 跨项目可复用观点

| 观点 | 证据位置 | 引用风险 | 备注 |
|---|---|---|---|
|  |  |  |  |

### 6.3 不建议引用或需要核查

| 内容 | 原因 | 需要核查什么 |
|---|---|---|
|  |  |  |

---

## 7. 元数据（折叠）

<details>
<summary>Reading card metadata</summary>

```yaml
item_key: "[{{ item_key_raw }}](zotero://select/library/items/{{ item_key_raw }})"
card_id: "{{ card_id }}"
zotero_key: "{{ item_key_raw }}"
reading_card_schema: "researchos-reading-card/v2"
generation_mode: "{{ generation_mode }}"
fulltext_status: "{{ fulltext_status }}"
reading_depth: "{{ reading_depth }}"
reviewed_sections: "{{ reviewed_sections }}"
source_text_sha256: "{{ source_text_sha256 }}"
manual_ref_id: "{{ card_id }}"
title: "?"
title_zh: "?"
authors: "?"
first_author_affiliation: "?"
first_author_affiliation_raw: "?"
first_author_affiliation_source: "?"
first_author_affiliation_status: "?"
year: "?"
venue: "?"
journal_abbrev: "?"
publication_tags: "?"
journal_ranking_source: "EasyScholar"
abstract_note: "?"
generated_at: "YYYY-MM-DDTHH:MM:SS+08:00"
status: "todo"
read_status: "{{ read_status }}"
importance: "normal"
planned_use: []
topic_relevance: "?"
tags: []
rating_5: "?"
text_source: "{{ text_source }}"
text_pages_read: "{{ text_pages_read }}"
evidence_strength: "?"
one_paragraph_review: "?"
pdf_attachment_key: "?"
pdf_attachment_keys: []
pdf_attachment_paths: []
child_keys: []
child_types: []
creators_json: []
date: "?"
doi: "?"
issn: "?"
isbn: "?"
volume: "?"
issue: "?"
pages: "?"
series: "?"
language: "?"
library_catalog: "?"
url: "?"
access_date: "?"
citation_key: "?"
zotero_tags: []
zotero_collections: []
zotero_relations: {}
zotero_self_link: "?"
zotero_alternate_link: "?"
zotero_attachment_link: "?"
zotero_date_added: "?"
zotero_date_modified: "?"
zotero_num_子条目: "?"
zotero_metadata_synced_at: "?"
prisma_record_id: "?"
prisma_stage: "?"
screening_decision: "?"
exclude_reason: "?"
gap_ids: []
```

</details>
