# Reading-card tools

本目录集中读书卡、PRISMA、期刊等级、作者机构、题录同步和缓存证据包工具。

`card_common.py` 是共享纯函数模块，统一提供读书卡元数据解析、Zotero 条目 key
处理和期刊等级格式化；其他脚本应引用该模块，不再复制这些实现。

本目录工具可以只读访问 Zotero 父文档或 Local API，但不得写入 Zotero。

`zotero_library_pipeline.py` 是全库、增量和显式 item key 的统一摄取入口：

```text
python tools/reading_cards/zotero_library_pipeline.py run --scope new
python tools/reading_cards/zotero_library_pipeline.py run --item-key ITEMKEY
python tools/reading_cards/zotero_library_pipeline.py semantic-packet --scope pending --batch-size 20
python tools/reading_cards/zotero_library_pipeline.py semantic-apply --results RESULTS.jsonl
python tools/reading_cards/zotero_library_pipeline.py semantic-apply --results RESULTS.jsonl --write-local
python tools/reading_cards/zotero_library_pipeline.py audit --strict
```

EasyScholar 首次接入可先执行不触碰读书卡的三期刊金丝雀：

```powershell
python tools/reading_cards/sync_journal_rankings.py --include-library-items --library-limit 3 --dictionary-only
```

它编排父文档同步、PDF 文本规范化、期刊词典、单位候选/别名频次、模型/人工
首页语义结果和集中初筛读书卡。机械候选不进入正式单位字段；语义结果需通过
item version、证据哈希、页码和来源校验。自动卡不生成项目借鉴章，不覆盖既有
人工卡正文，也不写入 Zotero。
