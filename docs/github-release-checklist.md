# GitHub 发布检查清单

本清单用于把当前 ResearchOS 包装为可传播的公开科研助理框架。目标是让其他用户 pull 后能直接使用，而不是面对一个需要维护的代码项目。

## 1. 仓库定位

- [ ] README 首屏说明 ResearchOS 是科研助理框架，不是具体课题仓库。
- [ ] QUICKSTART 说明用户如何用自然语言初始化、建立课题工作区和恢复上下文。
- [ ] PRIVACY 说明公开层、本地私有层和具体课题层的边界。
- [ ] 文档默认以“如何使用 agent”组织，而不是以“如何开发代码”组织。

## 2. 公开内容

- [ ] 保留通用规则、skills、工作流、质量检查、工具契约、策略、runbook、模板和示例配置。
- [ ] 只保留 `configs/*.example.*`，不保留真实配置。
- [ ] `templates/` 只包含空白模板或脱敏示例。
- [ ] 通用工具不含个人路径、密钥、具体课题假设或一次性项目逻辑。

## 3. 必须排除

- [ ] `.researchos/` 中的真实状态和当前课题指针。
- [ ] `corpus/zotero/` 中的真实 Zotero SQLite。
- [ ] `corpus/fulltext/` 和 `corpus/fulltext*/` 中的全文缓存。
- [ ] `corpus/reading-cards/cards/` 和 `corpus/reading-cards/indexes/` 中的真实读书卡和索引。
- [ ] `docs/reports/` 中由本地库生成的系统报告。
- [ ] 任何具体课题目录、论文草稿、审稿意见、周汇报和团队材料。
- [ ] `.env`、API key、token、cookie、代理完整 URL 和账号。

## 4. 初始化 Git 前

- [ ] 确认当前目录还没有 `.git/`，或确认历史中没有敏感内容。
- [ ] 检查 `.gitignore` 已覆盖本地私有配置、语料、全文、读书卡、输出和缓存。
- [ ] 执行文本扫描，重点查找真实绝对路径、密钥、未公开课题名、Zotero 数据和项目材料。
- [ ] 不使用 `git add .` 盲目提交；先检查待提交文件清单。

## 5. 推荐首次提交范围

推荐首次提交包含：

- 根目录规则与入口：`AGENTS.md`、`README.md`、`QUICKSTART.md`、`PRIVACY.md`、`CAPABILITIES.md`、`TRIGGERS.md`、`WORKFLOWS.md`、`QUALITY_GATES.md`、`TOOL_CONTRACTS.md`、`DISTRIBUTION.md`。
- 规则目录：`POLICIES/`、`RUNBOOKS/`、`TOOL_CONTRACTS/`。
- 通用资源：`.agents/skills/`、`templates/`、`configs/*.example.*`、`docs/` 中的通用说明。
- 经审查的通用工具：`tools/`，高风险工具必须保留审批说明。
- 占位说明：`corpus/README.md`、`corpus/reading-cards/README.md`、`local-cache/README.md`。

## 6. GitHub 推送前

- [ ] 本地运行一次发布扫描。
- [ ] 检查 GitHub 远程仓库是否为空仓库。
- [ ] 首次提交后再次检查提交内容，不合格时在公开前重建仓库。
- [ ] 推送后在 GitHub 网页抽查 README、QUICKSTART、PRIVACY 和文件列表。
