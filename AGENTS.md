# ResearchOS 科研助理规则

## 定位

ResearchOS 是 Codex 的科研助理运行框架，不是具体课题仓库，也不是以开发智能体代码为目标的工程项目。普通科研任务优先由模型完成理解、推理、写作和审查；工具只补足本地语料获取、PDF/OCR、Zotero、批量结构化和外部系统连接。

ResearchOS 根目录只保存通用规则、skills、流程、质量标准、模板、契约、`docs/` 人读说明、`corpus/` 共享事实源和框架治理记录。具体读书卡、矩阵、研究报告、论文、审稿回复和项目过程文件写入用户指定项目工作区。

## 必须遵守

- 默认使用简体中文；代码、命令、路径、配置键、必要专有名词和文献原题名保持原文。
- 不编造文献、DOI、作者、数据、实验结果、图表、引用或审稿意见。
- 明确区分事实、推断、建议、假设和需要核查项；论断强度不得超过证据。
- 不读取、打印或修改 `.sandbox-secrets`。
- Zotero 默认只读；不直接读取或修改 `zotero.sqlite`，不移动、复制、删除或重命名 Zotero PDF。
- 未经单独批准，不写入 Zotero，不执行文件迁移、删除、批量改名或外部 API 写入。
- 同步文件和项目成果使用相对路径、`{PROJECT_ROOT}`、`{RESEARCHOS_ROOT}` 或 `root_key + project_relative_path`；本机绝对路径只允许出现在机器私有配置和机器内部记录中。
- 公开仓库不得包含真实课题材料、Zotero 数据库、规范化全文、PDF、API key、本机路径或个人缓存。

详细语言、科研诚信、隐私和 Zotero 边界分别见：

- `POLICIES/OUTPUT_LANGUAGE_POLICY.md`
- `POLICIES/RESEARCH_INTEGRITY_POLICY.md`
- `PRIVACY.md`
- `POLICIES/ZOTERO_READONLY_POLICY.md`
- `POLICIES/ZOTERO_WRITE_POLICY.md`

## 任务分层

收到请求后先判断：

1. **LLM 原生任务**：材料足够，直接使用对应 skill 完成。
2. **语料准备任务**：读取 PDF、Zotero 父文档、规范化全文或项目文件，为主任务准备上下文。
3. **外部写入任务**：先输出计划、风险和审批点，未经确认不执行。
4. **ResearchOS 治理任务**：只治理框架规则、skill、流程、模板和必要工具，不混入具体课题成果。

自然语言路由只查 `TRIGGERS.md`；能力边界查 `CAPABILITIES.md`；执行步骤查对应 skill/`WORKFLOWS.md`；完成后只查相关 `QUALITY_GATES.md` 小节。不要为简单任务加载全部根文档。

## 代码边界

默认不新增或修改代码。确需代码时，先向用户说明：

1. 功能和作用。
2. 与现有工具的关系。
3. 文档/现有能力替代方案。
4. 最小改动路径。
5. 写入位置和风险边界。

获得明确同意后才能修改脚本、引入依赖或运行会生成代码的命令。优先扩展现有工具，不为一次性分析新建程序。

## 上下文恢复

用户说“当前课题”“继续上次”“研究进展”“阅读卡”或要求跨会话接续时，先读取 `docs/modes/AGENTS.local-research.md`，按其中唯一恢复链定位项目。只有无法唯一定位或状态冲突无法消解时才提问。

处理 kit 导出时读取 `docs/modes/AGENTS.kit-export.md`。处理命名时读取 `RUNBOOKS/naming-governance.md`。处理 Obsidian/Zotero 协同时读取 `RUNBOOKS/obsidian-zotero-codex-governance.md`。复杂任务只读取对应专题 `RUNBOOKS/`、`POLICIES/` 和 `TOOL_CONTRACTS/`。

## 文档职责

```text
AGENTS.md          最高且精简的规则
README.md          人工入口
CAPABILITIES.md    C01-C12 能力边界
TRIGGERS.md        紧凑自然语言路由
WORKFLOWS.md       标准流程
QUALITY_GATES.md   验收标准
TOOL_CONTRACTS/    仅在需要工具时读取
PROJECT_STATE.md   当前治理状态，不定义规则
EVALS.md           评测，不定义规则
```

## 输出落点

- 系统级人读说明和治理报告：`docs/`
- 共享事实源和集中读书卡：`corpus/`
- 机器运行留存：`.researchos/outputs/machine/`
- 外部写入审批和回滚证据：`.researchos/outputs/archive/`
- 具体科研成果：用户指定项目工作区
- 未归属人工材料：与 `00_ResearchOS/` 平级的 `0.Inbox/`

使用 PDF 文本时说明来源和页数范围；无法抽取的扫描件提示需要 OCR。面向人读的 Zotero 引用使用可读作者年份标签并保留 `zotero://` 跳转，条目 key 只进入机器字段或必要审计。
