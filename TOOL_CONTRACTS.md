# ResearchOS 工具契约总纲

`TOOL_CONTRACTS.md` 是 ResearchOS 工具契约层的根入口。具体工具说明、输入输出、允许行为、禁止行为和失败处理统一归入 `TOOL_CONTRACTS/`。

工具契约层只在 `WORKFLOWS.md` 判断需要本地工具补足时介入；不定义能力编号、不维护自然语言触发词、不写科研结论，也不替代 `QUALITY_GATES.md` 的验收标准。

## 1. 契约层职责

工具契约层用于回答四个问题：

1. 这个工具服务哪个科研流程。
2. 它补足了 LLM 对话本身无法完成的哪类本地能力。
3. 它绝不能触碰什么。
4. 它完成后应如何验收。

工具契约不是代码说明书，也不是科研结论来源。工具契约只定义工具边界、使用条件和治理约束。ResearchOS 的主体是科研助理场景、提示规则、上下文恢复和质量标准；工具只是为 LLM 准备语料、连接外部系统或执行经批准的批量操作。

## 2. 工具分层

| 层级 | 作用 | 默认风险 |
|---|---|---|
| 语料准备工具 | 获取或整理 PDF 文本、Zotero 父文档、规范化全文、项目目录上下文和上下文包 | 只读或写入机器中间产物 |
| 外部桥接工具 | 连接 Zotero Local API、Zotero Web API、EasyScholar、本机 opener 或系统路径配置 | 按读取/写入分别审批 |
| ResearchOS 自检工具 | 审计规则、契约、输出边界、命名、治理仪表盘和功能闭环 | 默认只读 |
| 高风险写入工具 | 写入 Zotero、批量移动/删除/改名、修改项目结构或外部系统 | 必须单独审批 |

## 3. 目录

| 文件 | 职责 |
|---|---|
| `TOOL_CONTRACTS/00-index.md` | 工具契约总索引和工具到专题的映射 |
| `TOOL_CONTRACTS/01-zotero-parent-documents.md` | Zotero 父文档、Local API、PDF 文本、全文缓存和 watcher |
| `TOOL_CONTRACTS/02-zotero-library-governance.md` | Zotero 文献库治理、研究方向聚合、标签和文献集建议 |
| `TOOL_CONTRACTS/03-zotero-web-api-write.md` | Zotero Web API 写入、金丝雀测试、回滚和高风险写入 |
| `TOOL_CONTRACTS/04-reading-cards-prisma.md` | 读书卡、PRISMA、期刊等级、作者机构和引用显示 |
| `TOOL_CONTRACTS/05-project-workspace.md` | 点子、课题、项目工作区和项目材料治理；具体科研成果默认写入指定项目路径 |
| `TOOL_CONTRACTS/06-researchos-governance.md` | ResearchOS 自身规则、输出边界、命名、Obsidian 打开方式和审计 |
| `TOOL_CONTRACTS/07-runtime-ocr-local-env.md` | 本机运行环境、OCR 和依赖配置 |

## 4. 全局边界

### 4.1 默认只读

除非专题契约明确允许，ResearchOS 工具默认只读外部事实源和 Zotero。只读不等于可以无限制读取隐私目录；读取范围仍受 `AGENTS.md`、`POLICIES/`、相关 `RUNBOOKS/` 和用户授权约束。

### 4.2 默认不写 Zotero

未获得用户单独批准时，任何工具不得写入 Zotero，不得删除条目，不得修改标签、文献集、笔记、附件或 PDF。Zotero 写入只允许走 `TOOL_CONTRACTS/03-zotero-web-api-write.md` 定义的 Web API 审批流程。

### 4.3 默认不直接触碰 `zotero.sqlite`

ResearchOS 普通阅读、综述、选题和治理任务默认使用父文档：

- `corpus/zotero/M-001-zotero-library/zotero_library.sqlite`
- `corpus/fulltext/zotero-library-normalized/`

不得直接读取或修改 Zotero 原始 `zotero.sqlite`。

### 4.4 默认不新增代码

ResearchOS 的目的不是代码维护项目，也不是开发科研智能体本体，而是科研助理运行框架。需要新增脚本、程序代码或自动化实现时，必须先汇报：

1. 代码功能。
2. 与现有工具或文档的关系。
3. 是否可以用现有能力或最小文档改动实现。
4. 拟写入路径和风险。

经用户同意后才能写入。

### 4.5 具体项目成果不写入 ResearchOS 根框架

跨项目共享事实源以 `corpus/` 为入口。系统级人读治理报告进入 `docs/`。机器运行留存进入 `.researchos/outputs/machine/`。具体课题的读书卡、综述矩阵、研究报告、论文草稿、审稿回复和项目治理结果默认写入用户指定项目路径。

### 4.6 高风险动作单独审批

以下动作必须单独审批：

- 写入 Zotero。
- 删除、移动、重命名真实科研材料。
- 批量修改项目文件夹结构。
- 修改审计脚本、写入脚本或跨设备路径解析代码。
- 写入密钥、代理、令牌或完整本机隐私路径。

## 5. 新增工具登记规则

新增或实质改造工具前，必须先判断是否真的需要代码。若用户批准写入代码，新工具还必须登记到：

1. `TOOL_CONTRACTS/00-index.md`
2. 对应专题契约文件
3. 相关 `WORKFLOWS.md` 或 `RUNBOOKS/`
4. 必要的 `QUALITY_GATES.md` 检查项

未登记契约的工具不得作为 ResearchOS 稳定能力入口。

## 6. 自动审计

自动审计脚本应读取 `docs/`、`corpus/`、`tools/high_risk/`、活跃工具清单和 `TOOL_CONTRACTS/` 专题契约。新增或改造自动审计脚本前，必须按“默认不新增代码”的规则单独汇报并获得用户批准。
