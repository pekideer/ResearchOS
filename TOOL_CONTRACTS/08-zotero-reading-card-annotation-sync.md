# Zotero 读书卡与标注同步工具契约

## 1. 适用工具

- `tools/zotero/zotero_annotation_sync.py`
- `tools/reading_cards/sync_zotero_annotations_to_cards.py`
- `tools/zotero/write/publish_reading_card_note.py`

## 2. 目的

只读采集 Zotero 原生 PDF annotation，保存为可追溯的 ResearchOS 语料；生成读书卡受控同步区；在具体审批后把一张读书卡发布为对应条目下的 Zotero 子笔记。

## 3. 输入与输出

- 输入：集中读书卡、item key、题录 children 中的 PDF attachment、全局分页 annotation JSON、批准的 note dry-run 计划。
- 共享事实源：父文档 `annotations` 表和 `reading_card_zotero_notes` 映射表。
- 机器预览：`.researchos/outputs/machine/M-005-reading-card-annotation-sync/`。
- 写入审计：`.researchos/outputs/archive/A-003-reading-card-note-publish/`。

## 4. 允许行为

- 经 `--allow-local-api` 明示后只读获取题录、附件和 annotation。
- 只处理显式 item key 或已有集中读书卡的条目。
- 写入 ResearchOS 父文档 annotation 镜像和软删除状态。
- 只替换读书卡的标注生成区。
- 真实读书卡本地写入必须显式限定至少一个 item key；生成区标记重复、失配或倒置时拒绝写入。
- 在用户批准具体计划后创建或版本安全地更新一条生成笔记。

## 5. 禁止行为

- 不写入或删除 Zotero annotation。
- 不读取或修改原始 `zotero.sqlite`。
- 不修改、移动、复制或删除 PDF。
- 不把人工评论自动解释成文献事实。
- 不覆盖人工修改过的生成笔记。
- 不自动删除冲突笔记或执行回滚。
- 不在计划、日志或输出中记录 API key、完整代理 URL或本机绝对项目路径。

## 6. 失败处理

- 全局 annotation 枚举或目标条目 children 读取失败：相关 attachment 不执行软删除。
- Local API 不可用：停止 annotation 同步并报告故障。
- 找到多个生成笔记、映射缺失、实质内容指纹不匹配或版本冲突：停止写入并生成冲突报告。
- 实质内容指纹覆盖标题、段落、列表、引用、强调、正文和链接/图像目标；只忽略经过金丝雀验证的 Zotero schema、`rel`、blockquote 段落包装、空列表节点和 `small`/`pre > code` 规范化。
- `--repair-local-mapping` 仅在已追踪 note key 与当前读书卡实质内容指纹一致时更新 ResearchOS 映射，不调用 Zotero 写接口。
- Web API、代理或权限测试失败：不得从 Local API 或原始数据库绕过写入。
- 批准计划路径或 provenance 不匹配、写后 note 身份/归属/标签/内容/版本不匹配：停止登记成功状态，保存失败摘要和独立回滚计划。

## 7. 验收标准

- annotation 可回溯到 item、attachment、页码和 annotation key。
- 页码显示区分 PDF 物理页序/总页数与文献印刷页码。
- 读书卡生成区可重复执行且不重复、不改其他正文。
- note dry-run 与实际写入使用同一 source hash 和原始 note HTML hash；写后冲突检测另用稳定内容指纹。
- 金丝雀执行保存 before、after、rollback plan 和脱敏代理记录。
