# ResearchOS 隐私边界

ResearchOS 可以管理具体科研项目，但公开仓库只能保存通用科研助理框架。真实项目内容必须留在用户本地或用户指定的私有项目目录。

## 可以进入公开仓库

- `AGENTS.md`、`README.md`、`CAPABILITIES.md`、`TRIGGERS.md`、`WORKFLOWS.md`、`QUALITY_GATES.md`。
- `POLICIES/`、`RUNBOOKS/`、`TOOL_CONTRACTS/`。
- `.agents/skills/` 中的通用 skill。
- `templates/` 中的空白模板。
- `configs/*.example.*` 示例配置。
- 经审查不含个人路径、密钥和具体课题材料的通用工具。
- 面向用户的通用说明文档。

## 不得进入公开仓库

- 真实课题目录、读书卡、综述矩阵、论文草稿、审稿意见、周汇报、导师意见和团队内部材料。
- `.researchos/active_project.yml`、`.researchos/project_registry.yml`、真实 `machine_config.json`。
- 用户主目录 `.researchos/` 中的任何真实配置。
- Zotero SQLite、Zotero storage、PDF、规范化全文、全库导出、真实条目缓存。
- `corpus/zotero/`、`corpus/fulltext/`、`corpus/reading-cards/cards/`、`corpus/reading-cards/indexes/` 中的真实内容。
- `.env`、API key、token、cookie、代理完整 URL、账号和机构内部地址。
- 任何包含个人绝对路径的临时文件或报告，例如真实 `C:\Users\...`、`D:\...`、同步盘路径。

## 推荐本地私有位置

- 本机路径映射：`%USERPROFILE%\.researchos\machine_config.json`。
- 当前课题指针：`%USERPROFILE%\.researchos\active_project.yml` 或仓库本地 `.researchos\active_project.yml`。
- 项目登记表：`%USERPROFILE%\.researchos\project_registry.yml` 或仓库本地 `.researchos\project_registry.yml`。
- 本地 Agent 运行材料：Agent Core 根目录下被 Git 忽略的 `.researchos/`；其中内容不得作为唯一项目状态或唯一正式审计副本。
- 具体课题上下文：课题目录下的 `.research/`。
- 具体课题成果：课题目录下的 `01-reading-cards/`、`02-literature-matrix/`、`03-manuscript/`、`.paper/`。

项目 `.research/` 只能保存跨端恢复所需的 manifest、状态、交接、决策、审批和精简审计；不得保存 tmp、cache、debug、preview、render、个人绝对路径、密钥或可重建的过程材料。具体边界见 `docs/governance/cross-device-storage-and-role-architecture.md`。

## 发布前最小检查

发布前至少确认：

1. `git status` 中没有 `.researchos/`、`corpus/zotero/`、`corpus/fulltext/`、真实读书卡或具体课题目录。
2. 文本扫描没有真实绝对路径、密钥、未公开课题名、审稿材料或个人账号。
3. `configs/` 下只有 `.example.*` 文件。
4. `docs/` 中没有具体课题成果；系统报告若由本地库生成，应留在本地并被 `.gitignore` 排除。
5. 首次推送 GitHub 前没有提交过敏感内容；如果已经提交过，不能只靠删除文件，需要清理 Git 历史或重建仓库。
