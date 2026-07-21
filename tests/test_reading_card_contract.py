from __future__ import annotations

import unittest

from tools.reading_cards.reading_card_contract import validate_reading_card


def deep_card(*, section_six: str, source_hash: str = "a" * 64) -> str:
    return f"""---
reading_card_schema: "researchos-reading-card/v2"
card_id: "RC-900"
zotero_key: "ITEM1234"
project_links: [{{"project_id":"cscec3-ai-temperature-control","project_name":"中建三局AI温控","association_order":1}}]
fulltext_status: "full_text_reviewed"
generation_mode: "llm_fulltext_deep_reading"
reviewed_sections: "1,2,3,4,5,7"
source_text_sha256: "{source_hash}"
---

# Contract test

## 1. 创新摘要

事实：本文完整说明研究问题、技术路径、验证对象以及结论边界，并保留足够正文内容供结构校验使用。

## 2. 背景

事实：研究背景、既有局限、研究目的和应用语境均来自已经审阅的全文材料。推断与作者原始论述分别标记，不把摘要当作完整证据。相关假设、研究场景、问题边界和作者所述动机也分别保留来源位置，避免在复述时扩大原文论断。

## 3. 研究内容

事实：研究对象、数据来源、输入输出、实验步骤、对照设置和评价指标均按全文逐项整理。这里保留足够长度，用于证明本节并非空标题或占位文本。模型结构、参数条件、采样过程、训练验证划分和复现实验限制也按证据位置记录，并明确哪些内容是作者陈述、哪些是审阅者推断。

## 4. 研究结果

事实：主要结果、定量指标、作者解释、局限条件和适用边界均有正文证据。这里继续提供足够内容，以验证精读声明与可见正文结构相互一致。对照结果、误差指标、敏感性分析、图表位置和未被数据直接支持的解释均分开记录，不将相关性改写为因果结论。

## 5. 综合判断

判断：文献可作为方法来源，但外推到现场前仍需独立验证，不能把作者场景直接视为本项目结论。

{section_six}

## 7. 元数据（折叠）

```yaml
item_key: ITEM1234
card_id: RC-900
generation_mode: llm_fulltext_deep_reading
fulltext_status: full_text_reviewed
read_status: deep
text_source: corpus/fulltext/ITEM1234.txt
text_pages_read: 1-18
reviewed_sections: 1,2,3,4,5,7
source_text_sha256: {source_hash}
```
"""


CURRENT_SECTION_SIX = """## 6. 项目借鉴

### 6.1 项目关联与具体用途

#### 6.1.1 中建三局AI温控（cscec3-ai-temperature-control）

- **对应项目问题/任务：** 现场温控方法验证。
- **具体借鉴点：** 使用同类评价指标作为方法来源。
- **拟使用位置：** 方法研究与实验设计。
- **证据位置：** 正文第 8–12 页。
- **适用边界：** 数据与气候条件不同，需重新验证。
- **状态：** 已映射。

### 6.2 跨项目可复用观点

评价流程可以复用，但参数不能直接迁移。

### 6.3 不建议引用或需要核查

现场外推结论需要核查。"""


class ReadingCardContractTests(unittest.TestCase):
    def test_current_deep_card_passes_and_emits_receipt(self) -> None:
        result = validate_reading_card(deep_card(section_six=CURRENT_SECTION_SIX), "ITEM1234")
        self.assertTrue(result.valid)
        self.assertTrue(result.deep_read_complete)
        self.assertEqual(len(result.to_dict()["receipt_hash"]), 64)

    def test_old_section_six_cannot_be_promoted_by_new_status_fields(self) -> None:
        old_section = """## 6. 对本课题的借鉴

这篇文章可以用于本课题的方法和讨论。"""
        result = validate_reading_card(deep_card(section_six=old_section), "ITEM1234")
        self.assertFalse(result.valid)
        self.assertFalse(result.deep_read_complete)
        self.assertIn("ambiguous_project_reference", result.issue_codes)
        self.assertIn("project_section_structure_incomplete", result.issue_codes)

    def test_v2_deep_card_requires_source_text_hash(self) -> None:
        result = validate_reading_card(deep_card(section_six=CURRENT_SECTION_SIX, source_hash="?"), "ITEM1234")
        self.assertFalse(result.valid)
        self.assertIn("source_text_sha256_invalid", result.issue_codes)

    def test_initial_screening_without_project_section_is_valid(self) -> None:
        body = """---
reading_card_schema: researchos-reading-card/v2
card_id: RC-901
zotero_key: ITEM5678
project_links: []
fulltext_status: full_text_available_needs_review
generation_mode: auto_initial_screening
---

# Initial
## 1. 创新摘要
自动初筛，不形成全文结论。
## 2. 背景
摘要证据待全文核对。
## 3. 研究内容
当前只记录材料状态。
## 4. 研究结果
未执行全文结果判断。
## 5. 初筛判断
建议进入人工或模型精读。
## 7. 元数据（折叠）
```yaml
item_key: ITEM5678
read_status: 自动初筛，待精读
```
"""
        result = validate_reading_card(body, "ITEM5678")
        self.assertTrue(result.valid)
        self.assertEqual(result.profile, "initial")
        self.assertFalse(result.deep_read_complete)

    def test_initial_mode_cannot_claim_deep_completion(self) -> None:
        body = """---
card_id: RC-902
zotero_key: ITEM9999
project_links: []
generation_mode: auto_initial_screening
fulltext_status: full_text_reviewed
---
## 1. 创新摘要
内容。
## 2. 背景
内容。
## 3. 研究内容
内容。
## 4. 研究结果
内容。
## 5. 判断
内容。
## 7. 元数据（折叠）
```yaml
item_key: ITEM9999
read_status: deep
```
"""
        result = validate_reading_card(body, "ITEM9999")
        self.assertFalse(result.valid)
        self.assertIn("reading_depth_declaration_inconsistent", result.issue_codes)


if __name__ == "__main__":
    unittest.main()
