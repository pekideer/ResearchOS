# Zotero Web API Write Canary Runbook

本操作手册 只说明操作手册，不执行写入。它不是自动执行授权；每次写入 Zotero 前必须获得用户单独确认。

真实写入、恢复、清理和项目 collection overlay 写入工具统一位于 `tools/zotero/write/`。目录名称只描述功能，其中工具仍属于高风险工具。进入该目录、看到具体脚本名或持有 dry-run 计划，不等于获得执行授权；只有完成本手册的前置条件、人工确认、金丝雀测试和回滚准备后，才允许调用其中工具。

## 适用场景

- 用户明确要求执行 Zotero 文献集、标签、item 或 note 写入。
- 已有 试运行 和人工确认的 plan。
- 写入范围可小批量控制。

## 前置条件

- 已完成 `POLICIES/ZOTERO_WRITE_POLICY.md` 检查。
- 用户明确批准具体 plan 文件。
- Zotero 已同步，或用户已完成备份。
- API key 仅来自环境变量。

## 环境变量检查

只检查是否存在，不输出真实值：

```powershell
$null -ne $env:ZOTERO_API_KEY
$env:ZOTERO_USER_ID
$env:ZOTERO_API_BASE
```

推荐：

- `ZOTERO_API_KEY`：必需，真实值不得输出。
- `ZOTERO_USER_ID`：必需。
- `ZOTERO_API_BASE`：默认 `https://api.zotero.org`。

## 代理检查

写入 Zotero Web API 前必须嗅探当前代理通道。优先级：

1. `ZOTERO_HTTPS_PROXY`
2. `HTTPS_PROXY`
3. `HTTP_PROXY`
4. 当前系统代理设置

执行要求：

- 只记录是否启用代理、代理来源和脱敏后的主机/端口。
- 不输出代理账号密码，不把完整代理 URL 写入日志、报告或 Markdown。
- 如果存在代理，应在只读 Web API 测试、金丝雀测试和批量写入中一致使用该代理。
- 如果代理不可用导致连接失败，应停止写入并报告代理来源和错误类型，不自动改用直连，除非用户明确要求。

## 只读权限测试

先通过 Zotero Web API 执行只读 GET，确认 key、user ID 和 API base 可用。

完成标准：

- 能读取用户库或指定测试条目。
- 未发生 POST、PUT、PATCH、DELETE。

## 金丝雀测试文献集创建测试

仅在用户批准后执行：

1. 创建低风险 金丝雀测试文献集。
2. 保存 执行前状态。
3. 执行创建。
4. 保存 执行后状态。
5. 用户确认结果。

## 单条 item tag 测试

仅在用户批准后执行：

1. 选择低风险 item。
2. 保存 条目执行前 JSON。
3. 添加或修改一个 金丝雀测试 tag。
4. 保存 条目执行后 JSON。
5. 生成 回滚计划。
6. 用户确认。

## 单条读书卡笔记测试

仅在用户批准具体 `approved-plan-candidate.json` 后执行：

1. 选择一张已映射 item key 的集中读书卡。
2. 只读获取母条目和现有 children，生成 `note-preview.html`。
3. 确认 action 为 `create`，或为已登记且版本/结构化内容指纹均匹配的 `update`；批准计划必须保留在原预检目录且 provenance 匹配。
4. 使用 `publish_reading_card_note.py --write --canary --approved-plan ...` 执行一条。
5. 保存母条目/children 执行前状态、note 执行前/后状态和脱敏代理记录；写后核验 note key、类型、母条目、标签、结构化内容指纹和版本。
6. 创建操作生成“另行批准后删除”的回滚计划；更新操作保存原 note HTML。
7. 用户在 Zotero 中确认条目归属、排版、链接和同步结果后，才能讨论扩大范围。

## 人工确认点

- 试运行计划 是否完整。
- 金丝雀测试结果是否符合预期。
- 回滚计划 是否可执行。
- 批量大小是否可控。

## Rollback 文件

每批至少保存：

- `before.json`
- `after.json`
- `rollback_plan.json`
- `write_audit.csv`

## 失败停止规则

- 任意 HTTP 错误、版本冲突、部分失败或返回结构异常，立即停止。
- 不自动扩大批量。
- 不自动重试破坏性操作。
- 输出失败 条目 key、错误消息和已完成批次。
