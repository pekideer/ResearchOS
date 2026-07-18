# ResearchOS LLM-first 最小代码治理计划（2026-07-19）

## 1. 治理目标

ResearchOS 以当前 ChatGPT/Codex agent 为科研语义主体。代码只承担：

1. PDF/OCR、Zotero、项目文件到 plain text、JSONL、SQLite 等可回溯语料的获取与规范化。
2. 路径、格式、版本、哈希、状态、幂等、审计和回滚等确定性处理。
3. 经用户审批的 Zotero 或外部系统读写。

代码不得直接调用通用语言模型 API，不得用关键词、评分或聚类规则代替 agent 判断研究主题、方法、对象、单位对应、创新、缺口和证据含义。

## 2. 验收标准

- 普通科研请求不要求开发或运行代码；材料足够时直接由 skill 和当前 agent 完成。
- 批量语义任务统一使用“工具准备语料包 → 当前 agent 判断 → 工具校验/应用结构化结果”。
- 仓库不存在读取模型 API key、提交 Chat Completions/Batch 或在代码内选择模型的活跃实现。
- 新条目监控只输出元数据和来源，不自动生成研究方向、方法、对象标签或稳定文献集建议。
- 启发式只允许用于定位、缺失检测、格式预检或明确未确认的召回候选，不得形成可发布科研事实。
- 每个保留脚本都能归入“语料准备、确定性基础设施、受控外部读写”之一，并有工具契约。

## 3. 第一阶段：明确越界链治理

状态：已实施并通过全量回归。

### 3.1 代码内模型调用

- 删除 `zotero_ai_governance.py` 的 OpenAI Batch 请求构建、文件上传、Batch 创建、模型选择和模型 API key 读取。
- 新入口 `build-agent-packet` 只生成逐条证据 JSONL 和一次性结果 schema 说明。
- `build-plan` 只接受当前 agent 输出的普通 JSONL，拒绝模型 API response envelope。

### 3.2 关键词新条目分类

- 删除 `zotero_new_item_monitor.py classify`。
- 删除关键词匹配、研究方向/方法/对象标签生成和自动 dry-run 写入计划。
- 保留 `check`、`report` 和 `sync-selected`：分别负责发现、语料报告和选定元数据同步。

### 3.3 评分式方向和标签规划

- 删除 `aggregate_research_directions.py`：不再用固定评分把方向提升为“核心/支线/长尾”。
- 删除 `build_tag_aggregation_plan.py`：不再用硬编码关键词归并科研标签。
- 删除依赖上述机器语义结果的 `build_collection_restructure_plan.py`。
- 研究方向、标签和文献集候选改由 `zotero-library-governance` skill 与当前 agent 生成，再交给确定性计划校验和 Zotero 审批链。

## 4. 第二阶段：候选召回与展示层收缩

状态：已实施核心收缩；自动初筛卡继续保留为纯题录/证据壳。

| 对象 | 当前作用 | 风险判断 | 治理动作 |
|---|---|---|---|
| `sync_first_author_affiliations.py` | 正则召回首页单位候选 | 与 agent 直接读取页段重复，且存在候选污染正式字段的风险 | 已删除；旧 `heuristic_candidate` 只作为迁移拦截状态保留 |
| `zotero_library_pipeline.py` 单位候选函数 | 为语义批次提供未确认线索 | 作者—单位对应属于语义判断 | 已删除候选提取；流水线只记录文本可用性、页段、来源和证据哈希 |
| 自动初筛卡渲染 | 把题录与摘要写成可浏览 Markdown | 若模板措辞包含语义结论会越界 | 保留纯题录/证据壳；模型精读内容只能由对应 skill 生成 |
| `sync_journal_rankings.py` | 查询并规范化外部期刊事实 | 属于外部事实桥接，不是科研推理 | 保留来源、查询状态和失败边界；不得由模型或规则猜测等级 |

## 5. 第三阶段：非语义基础设施必要性复核

状态：已完成第一轮复核。

- 保留项目工作区脚手架、PRISMA 状态表和阅读汇总表，它们只做确定性结构、状态管理和静态展示。
- 删除 `serve_portable_html.py`；阅读汇总改用普通相对链接和 `zotero://`，不再维护本地打开服务及其路径执行面。
- OCR 依赖检查默认不安装；只有用户明确批准并传入 `--install` 时才允许安装组件。
- 阅读汇总不再依据标签或项目默认值推断“与主题相关性”，缺失值保持为空，等待用户或当前 agent 判断。
- 每个工具必须说明真实复用场景、不可由现有 skill/模板替代的原因、输入输出和失败边界。
- 无调用入口、无复用证据或只服务一次性历史任务的工具进入删除候选；不因为“可能有用”长期保留。

## 6. 迁移说明

| 旧入口 | 新路线 |
|---|---|
| `zotero_ai_governance.py build-batch-file` | `prepare-corpus` → `build-agent-packet` → 当前 agent 判断 |
| `zotero_ai_governance.py submit-batch` | 已删除；不再由 ResearchOS 代码提交模型任务 |
| `zotero_ai_governance.py aggregate-directions/build-collection-plan/build-tag-plan` | 当前 agent 使用 `zotero-library-governance` 直接生成结构化建议 |
| `zotero_new_item_monitor.py classify` | `report` 输出新条目语料 → 当前 agent 分诊 → 如需写入则进入 Zotero 审批链 |
| `sync_first_author_affiliations.py` | `semantic-packet` 输出首页页段 → 当前 agent 判断 → `semantic-apply` 校验/应用 |
| `serve_portable_html.py` | 直接打开静态 HTML；读书卡使用相对链接，Zotero 使用系统协议链接 |

## 7. 安全边界

本治理不连接或写入 Zotero，不读取 `zotero.sqlite`，不移动 PDF，不修改真实课题成果，不安装依赖。删除范围仅限已确认违反 LLM-first 边界且已有 agent 替代路线的 ResearchOS 代码。

## 8. 实施验证

- 相关 Python 入口通过语法编译检查。
- 定向治理测试 29/29 通过。
- 全量单元测试 80/80 通过。
- `git diff --check` 通过。
- 活跃代码中未检出 OpenAI API/Batch 调用、本地 HTML 打开端点、已删除单位候选工具或主题相关性默认推断。
- 验证过程未连接或写入 Zotero，未安装依赖；测试临时目录已清理。
