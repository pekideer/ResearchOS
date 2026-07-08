# API Key Policy

本策略用于避免 API key 泄露，适用于 Zotero Web API 及未来可能接入的其他外部服务。

## 禁止行为

- 不把 API key 写入 `.env`、Markdown、日志、报告、截图或提示词。
- 不把真实 API key 打印到终端或最终报告。
- 不把真实 API key 放入 OneDrive 项目目录。
- 不在示例文件中使用真实 key。

## 允许方式

- 只通过环境变量读取 key。
- 输出时只能显示是否存在，不显示真实值。
- 示例中使用占位符，不使用真实值。

## 推荐环境变量

```powershell
$env:ZOTERO_API_KEY="..."
$env:ZOTERO_USER_ID="0"
$env:ZOTERO_API_BASE="https://api.zotero.org"
$env:EASYSCHOLAR_API_KEY="..."
```

说明：

- `ZOTERO_API_KEY`：仅用于 Zotero Web API 写入流程。
- `ZOTERO_USER_ID`：Zotero 用户 ID，本地只读默认可用 `0`。
- `ZOTERO_API_BASE`：Local API 默认 `http://localhost:23119/api`，Web API 默认 `https://api.zotero.org`。
- `EASYSCHOLAR_API_KEY`：仅用于本地查询期刊等级；不得写入 OneDrive 项目目录。ResearchOS 配置入口见 `RUNBOOKS/easyscholar-api-setup.md`。

## 泄露处理

如果 key 已泄露，应提示用户立即：

1. 撤销泄露的 API key。
2. 重新创建最小权限 key。
3. 检查日志、Markdown、截图和历史提交。
4. 清理本地环境中不应保存的副本。
