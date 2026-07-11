# EasyScholar API Setup

本操作手册用于配置 EasyScholar API，使 ResearchOS 可以在不依赖 ZoteroStyle DOM 渲染的情况下查询期刊等级，并同步到读书卡、阅读总表和 来源记录。

## 1. 存放原则

- 同步盘保存入口、非敏感 provider 配置和示例。
- 真实 API key 只保存在本机私有目录：`%USERPROFILE%\.researchos\secrets\easyscholar.env`。
- 不把真实 API key 写入 OneDrive、Markdown、日志、截图、prompt、Git 或 kit export。
- 如确需跨设备使用，应在每台设备本机重新录入 key。

## 2. 配置入口

在 ResearchOS 根目录运行：

```powershell
.\tools\reading_cards\configure_easyscholar_api.ps1
```

脚本只会交互式询问：

- EasyScholar endpoint
- API key

其他字段使用 ResearchOS 默认值：

- `method`: `GET`
- `auth_header`: `Authorization`
- `auth_prefix`: `Bearer`
- `query_field_priority`: `venue,publication_title,journal,publication,journal_abbrev`
- `timeout_seconds`: `20`
- `rate_limit_per_minute`: `30`

脚本输出：

- 同步盘非敏感配置：`.researchos\providers\easyscholar.yml`
- 本机密钥文件：`%USERPROFILE%\.researchos\secrets\easyscholar.env`

## 3. 手工填写格式

如不用脚本，可手工创建：

```text
%USERPROFILE%\.researchos\secrets\easyscholar.env
```

内容示例：

```env
EASYSCHOLAR_API_KEY=replace_with_real_key
```

同步盘中的 provider 配置可参考：

```text
configs\easyscholar_api.example.yml
```

## 4. 后续同步规则

后续期刊等级同步脚本应读取：

1. `.researchos\providers\easyscholar.yml`
2. `%USERPROFILE%\.researchos\secrets\easyscholar.env`

脚本只允许把 API 查询结果写入 ResearchOS 本地文档和 `.internal` 缓存；默认不写 Zotero。

## 5. 安全检查

- 终端输出只能显示 key 是否已配置，不得打印真实 key。
- 人工 Markdown/HTML 不得包含 API key。
- kit export 默认排除 `.researchos/` 和所有 secret 文件。
- API 返回的期刊等级如无法匹配，应标注“需要核查”，不得推断。
