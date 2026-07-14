# Zotero Web API 写入与高风险回滚契约

## 1. 适用工具

- `tools/zotero/write/execute_project_collection_overlay_write.py`
- `tools/zotero/write/execute_zotero_additive_write_plan.py`
- `tools/zotero/write/execute_zotero_deleted_collection_cleanup.py`
- `tools/zotero/write/zotero_web_api.py`
- `tools/zotero/write/publish_reading_card_note.py`
- `tools/zotero/write/README.md`

## 2. 工具目的

本专题只用于用户明确批准后的 Zotero Web API 写入。写入范围包括标签、文献集、项目覆盖层和受控读书卡子笔记等高风险操作。

这些工具统一放在 `tools/zotero/write/`，不得作为普通科研助理能力自动触发。该目录名称描述 Zotero 写入功能，不改变其高风险属性。目录只保留追加式、显式限定的增减式或窄范围清理工具；全量重建标签、全量重建文献集或清理旧 collection 树的旧链路不再作为 ResearchOS 工具入口。`execute_zotero_additive_write_plan.py` 为兼容历史入口保留文件名，但其移除能力只能由计划中的 `remove_collections`、`remove_tags` 明确列出，且必须保存写前/写后快照与回滚载荷。

## 3. 强制前置条件

执行任何 Zotero 写入前，必须同时满足：

1. 用户明确要求写入 Zotero。
2. 已读取 `POLICIES/ZOTERO_WRITE_POLICY.md`。
3. 已读取 `RUNBOOKS/zotero-web-api-write-canary.md`。
4. 已生成试运行计划。
5. 已给出写入范围、影响条目、回滚方式和失败处理。
6. 已获得用户对具体写入计划的确认。

## 4. 允许行为

- 读取经过人工确认的写入计划。
- 通过 Zotero Web API 执行金丝雀测试。
- 分批写入已批准的标签、文献集或覆盖层变更。
- 创建或版本安全地更新一条已批准的 ResearchOS 读书卡生成笔记，并在写后验证身份、归属、标签、结构化内容和版本。
- 记录脱敏审计信息和回滚材料。

## 5. 禁止行为

- 不通过 Local API 写入 Zotero。
- 不跳过试运行和金丝雀测试。
- 不写入未经确认的 AI 分类、聚类或建议。
- 不删除 Zotero 条目或 PDF。
- 不写入 annotation，不覆盖人工修改过的生成笔记，不自动删除冲突笔记。
- 不把 API key、完整代理地址、代理账号密码写入文件、日志或报告。
- 不接受脱离原预检目录、provenance 不匹配或越出集中读书卡目录的 note 批准计划。
- 不在失败状态下继续扩大写入批次。

## 6. 代理和密钥

访问 `https://api.zotero.org` 前应嗅探可用代理，优先级为：

1. `ZOTERO_HTTPS_PROXY`
2. `HTTPS_PROXY`
3. `HTTP_PROXY`
4. 当前系统代理设置

审计中最多记录“使用了代理”和脱敏后的主机/端口。不得记录完整代理 URL、账号、密码或 API key。

## 7. 验收标准

- 写入前有试运行材料。
- 写入前有人工确认。
- 金丝雀测试通过。
- 分批执行并有失败停止条件。
- 输出包含回滚计划和实际写入摘要。
- ResearchOS 通用写入计划保留在 `.researchos/outputs/machine/`；preflight、
  写入前后快照、执行审计和回滚材料进入
  `.researchos/outputs/archive/A-001-library-governance/`。
- 项目 collection overlay 的运行目录必须由调用方显式提供，不得使用隐式的
  ResearchOS 通用机器目录。
- 读书卡 note 计划进入 `.researchos/outputs/machine/M-005-reading-card-annotation-sync/`；真实金丝雀证据进入 `.researchos/outputs/archive/A-003-reading-card-note-publish/`。
