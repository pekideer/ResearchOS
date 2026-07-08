# ResearchOS Kit Export Agent Rules

本文档是导出 kit、starter 模板或给他人复用框架包时的智能体执行规则。面向人的版本说明见 `DISTRIBUTION.md`。

目标是只导出通用方法、模板、skills、策略、工具契约和低风险工具，剔除具体课题、个人路径、Zotero 数据、PDF、缓存、执行产物和任何可恢复隐私的信息。

## 1. 适用场景

- 用户说“导出 kit”“打包 ResearchOS”“发布模板”“发给别人”“starter 模板”“Personal Reuse Kit”“清理隐私后压缩”。
- 用户要求检查分发包是否包含具体课题信息、Zotero 数据、PDF、路径或密钥。

## 2. 导出前必须读取

1. `AGENTS.md`
2. `DISTRIBUTION.md`
3. `POLICIES/API_KEY_POLICY.md`
4. `POLICIES/ZOTERO_READONLY_POLICY.md`
5. `TOOL_CONTRACTS.md`
6. `TOOL_CONTRACTS/00-index.md`
7. `templates/research-run-state.md`
8. 本文件

## 3. 默认可包含内容

kit 可包含以下通用资产：

- `AGENTS.md`
- `docs/modes/AGENTS.kit-export.md`
- `README.md`
- `CAPABILITIES.md`
- `TRIGGERS.md`
- `WORKFLOWS.md`
- `QUALITY_GATES.md`
- `TOOL_CONTRACTS.md`
- `TOOL_CONTRACTS/`
- `DISTRIBUTION.md`
- `RUN_STATE_TEMPLATE.md`
- `POLICIES/`
- `RUNBOOKS/`
- `docs/references/`
- `templates/`
- `.agents/skills/`
- `configs/*.example.*`
- 经过审查的通用 `tools/`
- `.env.example`
- `requirements.txt`
- `requirements-ocr.txt`

## 4. 默认必须剔除内容

导出包不得包含：

- `.git/`
- `.env`
- `.local/`
- `.researchos/` 中的真实同步记忆和当前课题指针；只可保留不含真实课题的示例文件。
- `*.env`、任何包含 `API_KEY`、`TOKEN`、`SECRET` 的真实密钥文件。
- `.venv/`、`venv/`
- `.researchos/outputs/`
- 真实点子、来源记录和研究简报；只可保留空目录说明、模板或已脱敏示例。
- 点子登记表和点子索引。
- `local-cache/` 的实际缓存。
- `PROJECT_STATE.md`
- `docs/modes/AGENTS.local-research.md`，除非明确作为通用模板审查后再加入。
- 用户主目录 `.researchos/` 中的任何真实配置、memory 或 registry。
- `00_ResearchOS/.researchos/active_project.yml` 和 `project_registry.yml`。
- 任何具体课题目录，例如带 `.research/project_manifest.yml` 的研究项目目录。
- `.research/`、`.paper/`、`01-reading-cards/`、`02-literature-matrix/`、`03-manuscript/`、`04-reviewer-response/`、`05-ai-code-workspace/` 的真实课题产物。
- `.research/fulltext_cache/`、`.research/material_text/`、`02-literature-matrix/.internal/*packet*` 等全文缓存、证据包和中间材料。
- Zotero PDF、Zotero storage、`zotero.sqlite`、Zotero 导出的全库 JSON、真实 item 全量缓存。
- 真实 API key、token、cookie、账号、邮箱、机构内部地址。
- 未公开论文全文、基金申请书、审稿意见、周汇报、导师意见、团队成员隐私信息。
- 含具体课题假设、真实条目 key、真实文献集或标签执行记录、个人绝对路径的临时脚本或报告。

## 5. 隐私扫描规则

打包前至少执行一次文本扫描，重点检查：

- Windows 绝对路径：`C:\`、`D:\`、`OneDrive -`
- 用户目录：`Users\`、`%USERPROFILE%`
- Zotero 痕迹：`zotero.sqlite`、`storage`、`api.zotero.org/users/`、`items/`
- 密钥痕迹：`API_KEY`、`TOKEN`、`SECRET`、`Authorization`、`Bearer`
- 课题痕迹：真实课题名、团队成员姓名、未公开项目名、基金正文、审稿材料。
- 真实产物目录：`.research/`、`.paper/`、`priority-cards/`、`reading-summary-table.html`
- 点子知识库痕迹：`IDEA-`、`idea-registry.csv`、点子目录路径或具体点子正文

发现命中后，必须逐项判断是通用示例还是私有内容。私有内容应剔除或替换为占位符，不得仅靠压缩包说明提醒接收者忽略。

## 6. 工具筛选规则

- `tools/` 只保留不绑定具体课题、不包含个人路径、不直接写入外部系统的通用工具。
- 具体课题辅助脚本应放在课题目录 `05-ai-code-workspace/` 或 `local-cache/project-specific/`，不得进入 kit。
- 能执行 Zotero 写入、批量移动、删除、重命名或外部发布的脚本不得进入 starter 模板。
- 如需在 personal kit 中保留高风险工具，必须同时保留对应 `TOOL_CONTRACTS/03-zotero-web-api-write.md`、试运行规则、审批规则和回滚说明。

## 7. 输出要求

导出完成后必须生成 `KIT_MANIFEST.md`，至少包含：

- kit 名称、生成时间、导出模式。
- 包含路径。
- 剔除路径。
- 隐私扫描摘要。
- 已知限制。
- 接收者本地配置说明。

最终交付应是新建 release 目录和 zip 包，不建议直接压缩整个工作区。
