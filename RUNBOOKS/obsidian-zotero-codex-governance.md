# Obsidian、Zotero 与 Codex 协同边界

本手册定义用户选择使用 Obsidian 阅读 Markdown 时，ResearchOS、Zotero、项目工作区和 Obsidian 的职责边界。默认事实源是 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。

## 1. 三层分工

| 层级 | 主要职责 | 边界 |
|---|---|---|
| Zotero | 题录、附件、文献集、标签、PDF 和 `zotero://` 跳转 | 写入必须走审批、试运行、金丝雀测试和回滚计划 |
| ResearchOS | 规则、流程、模板、共享事实源、集中读书卡和治理状态 | 具体科研成果进入用户指定项目工作区 |
| Obsidian | 人工阅读、双链导航、项目进展浏览和知识地图 | 只作为阅读界面和导航界面，不承载 Zotero 数据库、PDF 缓存或机器事实源 |
| Codex | 生成读书卡、矩阵、报告、审计表和链接修复建议 | 未经批准不写入 Zotero，不替代人工研究判断 |

## 2. 当前入口

- 系统级人读说明：`docs/`
- 共享事实源：`corpus/`
- 集中读书卡：`corpus/reading-cards/cards/`
- 具体课题成果：用户指定项目工作区
- 未归属人工材料：与 `00_ResearchOS/` 平级的 `0.Inbox/`
- 机器运行留存：`.researchos/outputs/machine/`
- 外部写入审计证据：`.researchos/outputs/archive/`

Obsidian 可以打开 `docs/`、具体项目工作区或集中读书卡目录进行阅读。ResearchOS 根目录包含规则、工具、策略和机器留存，不建议作为日常知识库根目录。

## 3. 链接规则

读书卡和报告中引用文献时，正文显示可读引用标签，链接指向 Zotero：

```md
[Wang(2025)](zotero://select/library/items/ITEMKEY)
```

如需打开 PDF，使用附件链接：

```md
[PDF](zotero://open-pdf/library/items/ATTACHMENTKEY)
```

供人阅读的正文不裸露 Zotero 条目 key。文末元数据、机器表、审计追踪和排障说明可以显示 key，且必须保留可点击链接。

跨文档知识导航可使用 Obsidian 双链：

```md
[[path/to/file|可读名称]]
```

链接显示名应面向人阅读，不使用机器字段名作为可见文本。报告、进展记录和读书卡优先链接到主题、问题、方法、证据、研究缺口和项目进展节点。

## 4. 文档组织

入口页只负责导航，不堆放长正文。推荐结构：

- `docs/README.md`：ResearchOS 系统级人读入口。
- 项目工作区 `01-课题入口-YYYYMMDD.md`：课题读书卡、矩阵、报告、论文草稿和待办问题入口。
- `corpus/reading-cards/cards/`：跨项目共享读书卡主库。

证据层包括读书卡、全文摘录、综述矩阵、论断-证据表和 PRISMA 状态表。叙事层包括研究进展报告、深度研究报告、选题判断、论文段落和审稿回复草稿。叙事层中的关键判断应链接到证据层。

## 5. 文件命名

具体项目的人读文档遵循 `RUNBOOKS/naming-governance.md`：

```text
corpus/reading-cards/cards/RC-###_短题名.md
03-文献矩阵/LM-###_用途说明.md
05-论文稿件/MS-###_稿件部分.md
07-审稿回复/RR-###_回复主题.md
```

集中读书卡文件名固定为：

```text
RC-###_ZoteroKey_短题名.md
```

可读名称优先于机器 key；Zotero key 放入文末元数据、机器表或审计字段。

## 6. 维护规则

1. 人读入口保持短小，只放导航、状态摘要和关键链接。
2. 读书卡不互相复制摘要；通过链接连接共同主题、方法和研究缺口。
3. 研究报告不粘贴长篇 PDF 文本；引用页数范围、读书卡和 Zotero 链接。
4. Codex 批量生成文档后，应检查裸露 Zotero key、断链、重复标题和无证据结论。
5. Zotero 标签和文献集治理走审批流程；Obsidian 标签只用于人工阅读状态和主题导航。
