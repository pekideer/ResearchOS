---
name: paper-deep-reading
description: 对单篇论文、会议论文、学位论文或专利全文进行结构化语义精读，区分事实、作者解释、读者推断、局限与可迁移价值，并按统一读书卡契约生成或深化正文；当用户要求“精读这篇文献”“按最新模板重做读书卡”“检查旧卡是否真完成精读”或提供单篇全文要求提炼时使用。它不负责批量 Zotero 同步、PDF/OCR 准备、期刊词典或 Zotero Web 写入。
---

## 职责

作为单篇文献的语义精读引擎，负责读书卡第 1–6 节的科研判断和第 7 节的语义回执。语料准备与批量编排交给 `zotero-reading-card-pipeline`；Zotero note 发布交给 `zotero-reading-card-annotation-sync`。

## 必须读取

1. `RUNBOOKS/reading-card-governance.md`
2. `templates/literature/paper-reading-card.md`
3. `WORKFLOWS.md` 工作流 1
4. `QUALITY_GATES.md` 的证据、来源、输出和读书卡契约检查

## 输入门禁

- 确认题录身份、文本来源、页码范围和文本完整性；优先读取 Zotero 父文档与规范化文本。
- 全文不可用时只能生成初筛或局部阅读结果，不得声明 `full_text_reviewed`。
- 读取全文前记录来源文件的 SHA-256；材料变化后重新阅读，不复用旧回执。
- 第一作者单位使用首页至第 3 页的语义结果；本 skill 不用正文主题或机构常识猜测单位。

## 精读步骤

1. 写出一句话定位和一段话综述，明确证据范围。
2. 提取研究问题、方法路线、数据/模型/实验条件、变量和指标。
3. 提取主要结论，分别标记事实、作者解释和读者推断；数值保留对象、基线、单位与页码。
4. 以明确参照对象判断创新性；没有参照时写“暂不能判断”。
5. 从设计、数据、方法和外推边界说明局限，不空泛批评。
6. 填写跨项目可复用观点、引用风险和需要核查项。
7. 仅在项目关联与用途已有明确证据时生成结构化第 6 节；每个 `project_links` 项目单列 `6.1.n`，完整填写任务、借鉴点、拟使用位置、证据、边界和状态。
8. 写入统一回执：`generation_mode`、`fulltext_status`、`read_status`、`text_source`、`text_pages_read`、`source_text_sha256`、`reviewed_sections`。
9. 调用 `tools.reading_cards.reading_card_contract.validate_reading_card` 校验；未通过不得把卡片报告为精读完成，也不得进入 Zotero 发布预检。

## 输出契约

- 初筛：`auto_initial_screening`，不能标记 `full_text_reviewed` 或 `deep`。
- 局部阅读：`llm_partial_fulltext_review`，明确页码和未覆盖内容。
- 全文精读：`llm_fulltext_deep_reading` + `full_text_reviewed` + `read_status: deep`，且第 1–5、7 节具有实质内容。
- 旧卡可按 v1 兼容结构校验；再次语义更新时升级为 `researchos-reading-card/v2` 并补齐来源哈希。
- 第 6 节不是精读完成标志。存在时必须符合当前多项目结构；旧式平铺“借鉴”、含义不明的“本课题”或空项目块均为契约错误。

## 完成条件

- 结论可回溯到指定文本和页码，未编造题录、数据、图表或引用。
- 事实、作者解释、推断、建议和需要核查项分离。
- 合同校验 `valid=true`；全文精读还必须 `deep_read_complete=true`。
- 只写本地或已批准的项目/语料 staging；本 skill 不授权 Zotero 或共享 corpus 写入。
