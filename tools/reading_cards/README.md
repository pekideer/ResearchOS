# Reading-card tools

本目录集中读书卡、PRISMA、期刊等级、作者机构、题录同步和缓存证据包工具。

`card_common.py` 是共享纯函数模块，统一提供读书卡元数据解析、Zotero 条目 key
处理和期刊等级格式化；其他脚本应引用该模块，不再复制这些实现。

本目录工具可以只读访问 Zotero 父文档或 Local API，但不得写入 Zotero。
