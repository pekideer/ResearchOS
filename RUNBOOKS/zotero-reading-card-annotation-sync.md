# Zotero 读书卡与标注闭环

本手册定义集中读书卡发布到 Zotero 条目笔记，以及 Zotero 原生 PDF 标注回流 ResearchOS 的职责和审批边界。

## 1. 权威来源

- 集中读书卡正文是唯一权威主版本。
- Zotero 子笔记是阅读镜像，不因进入 Zotero 而成为新的事实源。
- Zotero annotation 是人工阅读证据：高亮原文属于“原文摘录”，评论属于“人工判断”。
- annotation 原始字段存入 ResearchOS 父文档；读书卡只保留面向人工阅读的派生区。

## 2. 数据方向

```text
集中读书卡 --审批后 Web API 写入--> Zotero 条目子笔记
Zotero PDF annotation --Local API 只读--> ResearchOS annotations 表
annotations 表 --本地受控更新--> 读书卡 6.99 标注同步区
```

不得把这三条路径合并为同一文档的无人值守双向覆盖。

## 3. 标注采集

annotation 的 `parentItem` 指向 PDF attachment。当前 Local API 的采集顺序固定为：

1. 用题录 item key 读取第一层 children。
2. 只选择 PDF attachment。
3. 对本次运行只做一次 `items?itemType=annotation` 完整分页枚举。
4. 只保留 `parentItem` 等于目标 attachment key 的 annotation。
5. 保存 annotation key、attachment key、parent item key、类型、原文、评论、颜色、页码、位置、标签、版本和内容哈希。
6. 只有全局 annotation 枚举和目标条目 children 均完整读取成功后，才能把该 attachment 的本地缺失 annotation 标为软删除。

默认范围是已有集中读书卡的条目；不得因启用本能力而扩大成全库 annotation 扫描。

## 4. 读书卡更新

读书卡在 `## 7. 元数据（折叠）` 前维护唯一生成区：

```text
<!-- researchos:zotero-annotations:start -->
### 6.99 人工阅读标注（Zotero 同步）
...
<!-- researchos:zotero-annotations:end -->
```

- 同步程序只能替换该区。
- `--write-cards` 必须显式指定至少一个 `--item-key`；不得把空范围解释为批量写全部集中读书卡。
- 起止标记必须同时不存在，或各有且仅有一个且顺序正确；重复、缺失或倒置时停止。多行人工批注必须缩进为引用行，不得形成控制标记。
- 原文摘录、人工判断、定位线索和需要核查必须分开。
- PDF 物理页序使用 `annotationPosition.pageIndex + 1`，总页数来自父文档 `pdf_texts.pages_total`；`annotationPageLabel` 作为文献印刷页码另列，不得混用。
- 正文第 1-6 区的结论更新由 LLM/人工另行审查，不由同步程序自动完成。
- annotation 删除只改变活动生成区；历史记录继续保存在父文档软删除状态中。

## 5. Zotero 笔记发布

- 写入仅通过 `tools/zotero/write/publish_reading_card_note.py` 和 Zotero Web API。
- 默认只生成 `approved-plan-candidate.json` 与 `note-preview.html`。
- 真实写入必须指定同一个已批准计划，并使用 `--write --canary`。
- 创建笔记只设置 `itemType=note`、`parentItem`、笔记正文和 `rs:reading-card` 标签。
- 更新只允许已登记 note key、实质内容未被人工修改且版本匹配的生成笔记。
- 冲突检测使用保留标题、段落、列表、引用、强调、正文和链接/图像目标的结构化内容指纹；只忽略已验证的 Zotero schema 外层、链接 `rel`、blockquote 段落包装、空列表节点和不受支持的 `small`/`pre > code` 规范化。
- 原始 note HTML hash 仍用于已批准计划到实际写入之间的精确版本复核；内容指纹只用于识别写后规范化和后续人工内容变化。
- 若已追踪笔记与当前读书卡内容指纹一致但本地映射仍是旧原始 HTML hash，可显式使用 `--repair-local-mapping` 只修复本地映射；该参数不写入 Zotero。
- 批准计划必须来自 `.researchos/outputs/machine/M-005-reading-card-annotation-sync/` 的原始 `approved-plan-candidate.json`，并核对 schema、模式、来源目录、卡片路径、哈希和既有 note 状态。
- 写入后先核验 note key、item type、parent item、`rs:reading-card` 标签、结构化内容指纹和版本推进；任何后置条件失败都保存失败摘要与回滚计划，但不得登记成功映射。
- 同一 `card_id` 出现多个生成笔记时停止。
- 不自动删除、合并或移动任何 Zotero 笔记。

## 6. 金丝雀审查

首个测试条目应同时具备：一张集中读书卡、一个 PDF 附件、至少一条文字高亮和一条人工评论。依次检查：

1. 只读扫描能否找到正确 attachment 和 annotation。
2. 页面、颜色、原文与评论是否正确分层。
3. 读书卡生成区预览是否不改动其他正文。
4. Zotero note 预览是否可读。
5. 用户批准具体计划后执行一次 create 或 update。
6. 用户在 Zotero 中检查条目归属、排版、同步和链接。
7. 批量能力只有在用户确认金丝雀后才能启用。

## 7. 隐私

annotation 原文和评论属于真实科研材料，只能进入私有 `corpus/`、机器留存和写入审计目录；不得进入公开仓库、公开 kit、日志摘要或对话中的大段原文输出。
