# configs 目录治理说明

本目录只存放 ResearchOS 可公开复用的配置样例，不存放真实本机配置、密钥、Zotero 数据库路径、PDF 缓存路径或项目私有材料。

## 保留文件

| 文件 | 用途 | 治理状态 |
|---|---|---|
| `active_project.example.yml` | 当前课题指针样例 | 保留，仅作复制模板 |
| `project_registry.example.yml` | 课题登记表样例 | 保留，仅作复制模板 |
| `machine_config.example.json` | 本机路径配置样例 | 保留，仅作复制模板 |

跨设备约束：同步盘、项目成果、阅读矩阵、读书卡索引、报告和交接文档不得写入真实本机绝对路径；只能使用项目相对路径、`{PROJECT_ROOT}/...`、`{RESEARCHOS_ROOT}/...` 或 `root_key + project_relative_path`。真实绝对路径仅允许出现在用户主目录机器配置、环境变量或被忽略的 `.local/` 中。
| `easyscholar_api.example.yml` | EasyScholar provider 配置样例 | 保留，不包含真实 API key |
| `zotero_governance_rules.example.json` | Zotero 文献治理规则样例 | 保留，被工作流和工具契约引用 |

## 真实配置位置

- 本机专用配置优先放在 `%USERPROFILE%\.researchos\`。
- 工作区同步但不进入 kit 导出的指针类配置放在 `.researchos\`。
- 不应在本目录放置 `active_project.yml`、`project_registry.yml`、`machine_config.json`、`easyscholar_api.yml` 或真实治理规则文件。

## 治理原则

- 新增配置前先确认是否能复用现有样例或 `.researchos/` 配置。
- 不把 API key、cookie、token、代理完整 URL、Zotero storage 路径、PDF 缓存或具体项目私有路径写入本目录。
- 供人阅读的说明默认使用中文；字段名、路径、命令、软件名和 API 名称按原样保留。
