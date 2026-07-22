---
name: zotero-reading-card-annotation-sync
description: 在 ResearchOS 与 Zotero 之间建立读书卡和人工标注闭环；当用户要求“把读书卡同步到 Zotero 条目笔记”“读取或同步 Zotero PDF 标注”“根据高亮/批注更新读书卡”“同步这篇文献的阅读痕迹”或执行相关金丝雀测试时使用。负责只读采集 annotation、证据分级、读书卡受控生成区和经审批的单条笔记发布；不负责修改 PDF、写入 annotation 或无人值守双向覆盖。
---

## 目标

保持 ResearchOS 集中读书卡为权威主版本，将其镜像为对应 Zotero 条目下的子笔记；只读回收 Zotero 原生 PDF 标注，并在证据审查后更新读书卡的受控生成区。

## 固定职责

- ResearchOS 读书卡：唯一权威正文。
- Zotero 子笔记：阅读镜像，默认不接受人工直接改写。
- Zotero annotation：人工阅读痕迹；只读采集，不写入、不删除。
- ResearchOS 父文档 `annotations` 表：原始标注事实源和删除历史。
- 读书卡 `6.99 人工阅读标注（Zotero 同步）`：面向人工阅读的派生区，不自动改变其他正文结论。

## 证据分类

- `annotationText`：标为“原文摘录”；保留条目、附件、页码和 annotation 跳转。
- `annotationComment`：标为“人工判断”；不得直接写成文献事实。
- 只有位置、颜色或类型：标为“定位线索”。
- 同时存在摘录和评论：标为“原文摘录＋人工判断”，分别解释。
- 区域图像、手写和无上下文短句：标为“需要核查”，未读取图像前不得推断内容。
- 页码以 `annotationPosition.pageIndex + 1` 作为 PDF 物理页序；父文档有总页数时显示 `当前页/总页数`。`annotationPageLabel` 仅显示为文献印刷页码。

## 工作流

1. 确认目标是只读标注回流、读书卡本地更新，还是 Zotero 笔记发布。
2. 默认只处理已有集中读书卡对应的条目；金丝雀使用一个明确 item key。
3. 只读扫描 annotation：

   ```powershell
   python tools/zotero/zotero_annotation_sync.py --allow-local-api --item-key ITEMKEY
   ```

4. 用户确认扫描范围后，写入 ResearchOS 父文档镜像；这不是 Zotero 写入：

   ```powershell
   python tools/zotero/zotero_annotation_sync.py --allow-local-api --item-key ITEMKEY --write-mirror
   ```

5. 先生成读书卡更新预览：

   ```powershell
   python tools/reading_cards/sync_zotero_annotations_to_cards.py --item-key ITEMKEY
   ```

6. 用户要求应用后才加 `--write-cards`，并必须同时给出至少一个明确 `--item-key`；只替换带起止标记的生成区。重复、缺失或倒置的生成区标记必须停止写入。
7. 发布 Zotero 笔记前，读取 `POLICIES/ZOTERO_WRITE_POLICY.md` 与 `RUNBOOKS/zotero-web-api-write-canary.md`，生成 live dry-run：

   ```powershell
   python tools/zotero/write/publish_reading_card_note.py --card "corpus/reading-cards/cards/RC-...md"
   ```

8. 把 `approved-plan-candidate.json` 和 `note-preview.html` 交给用户确认。未获得针对该计划的明确“执行写入”批准时停止。
9. 获批后只执行单条金丝雀：

   ```powershell
   python tools/zotero/write/publish_reading_card_note.py --write --canary --approved-plan ".researchos/outputs/machine/.../approved-plan-candidate.json"
   ```

10. 保存执行前、执行后、回滚计划和脱敏代理记录；让用户在 Zotero 中检查笔记归属、排版和跳转。

## 冲突与失败

- 题录条目 children 只用于定位 PDF 附件；当前 Local API 的 annotation 通过一次全局 `itemType=annotation` 枚举取得，再按 `parentItem=attachment key` 限定到目标 PDF。
- 全局 annotation 枚举或目标条目 children 读取失败时，不对相关附件执行标注软删除。
- 已生成笔记若正文、链接/图像目标或有意义的标题、段落、列表、强调结构被人工修改，停止更新并输出冲突；不得覆盖。只忽略已验证的 Zotero HTML schema、链接 `rel`、blockquote 段落包装、空列表节点和不受支持的 `small`/`pre > code` 规范化。
- 已追踪笔记与当前读书卡内容指纹一致、但本地映射仍保存旧原始 HTML hash 时，只能通过显式 `--repair-local-mapping` 修复 ResearchOS 本地映射；该操作不得调用 Zotero 写接口。
- 找到多个同一 `card_id` 的生成笔记时停止。
- 真实写入只允许 `create` 或已追踪且版本匹配的 `update`；不自动删除任何笔记。
- 批准计划必须位于本次机器预检目录、结构和来源目录匹配；写后必须核验 note key、类型、母条目、标签、内容指纹和版本，再登记成功映射。
- Local API 不可用时停止只读同步；Web API、API key 或代理检查失败时停止写入。

## 输出

- `.researchos/outputs/machine/M-005-reading-card-annotation-sync/`：只读扫描、读书卡预览和笔记 dry-run。
- `.researchos/outputs/archive/A-003-reading-card-note-publish/`：真实金丝雀执行前后证据和回滚计划。
- `corpus/zotero/M-001-zotero-library/zotero_library.sqlite`：annotation 镜像和笔记映射状态。
- `corpus/reading-cards/cards/`：集中主卡及其受控标注生成区。

## 完成条件

- Zotero 读操作未修改 Zotero、PDF 或原始 `zotero.sqlite`。
- 每条活动标注可回溯到 item key、attachment key、PDF 物理页序、文献印刷页码和 annotation key。
- 原文摘录、人工判断、定位线索和需要核查项已区分。
- 读书卡其他正文未被批量覆盖。
- 真实笔记写入已有具体批准计划、单条金丝雀、版本检查、执行前后证据和独立回滚计划。
