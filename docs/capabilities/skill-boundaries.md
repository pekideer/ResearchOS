# ResearchOS skill 边界

本文件用于处理容易混淆的 skill。只有路由不确定时才读取；普通明确任务直接使用对应 skill。

## 路由与项目状态

| 主 skill | 只负责 | 不负责 | 转交 |
|---|---|---|---|
| `semantic-route-planner` | 模糊、多目标请求的主次意图和能力路线 | 扫描完整项目、执行具体科研任务 | 明确后转交一个主 skill |
| `project-map-builder` | 上下文恢复、项目地图、当前位置、明确要求的汇报导航 | 普通任务例行结尾、论文或综述正文 | 具体任务转交对应执行 skill |

原独立汇报导航能力已并入 `project-map-builder`。普通任务只需在最终汇报中说明完成内容和必要的下一步，不再触发独立 skill。

## 从点子到研究问题

| 阶段 | 主 skill | 通过条件 | 下一阶段 |
|---|---|---|---|
| 点子资产化 | `idea-to-research-potential` | 有 IDEA 编号、点子卡、来源和初步判断 | 需要检索时转交 |
| 检索设计/候选发现 | `literature-search-map` | 有可复制检索式、数据库路线和候选清单 | 精读或矩阵 |
| 深度综合报告 | `research-intelligence-report` | 综合库内外证据形成正式报告 | 缺口判断 |
| 多文献比较 | `literature-matrix` | 有可追溯矩阵和候选缺口 | 立项判断 |
| 缺口立项判断 | `gap-to-topic` | 明确继续、修改、暂缓或放弃 | 研究问题 |
| 问题与变量设计 | `research-question-framing` | 有可验证问题、假设、变量和路径 | 方法设计 |

不得用早期点子 skill 代替正式检索、深度报告或立项判断；不得在缺少推进判断时把宽泛兴趣直接包装成成熟研究问题。

## 论文与返修

| 主 skill | 触发条件 | 与 `.paper/` 的关系 |
|---|---|---|
| `paper-memory-builder` | 用户明确要求建立/更新论文记忆，或复杂多轮返修缺少索引 | 创建或更新 `.paper/` |
| `claim-evidence-audit` | 检查论断强度和证据匹配 | 有 `.paper/` 则读取，无则直接审计材料 |
| `methods-design-review` | 检查方法、数据、指标、对照和鲁棒性 | 不创建论文记忆 |
| `results-figure-narrative` | 根据既有图表事实组织结果与讨论 | 不执行全面证据审计 |
| `academic-polishing` | 保持技术含义的语言润色 | 不新增论断或证据 |
| `reviewer-response` | 拆解审稿意见并形成逐条回复 | 多轮返修时可读取 `.paper/` |

普通单次润色、审计、结果叙事或审稿回复不自动触发 `paper-memory-builder`。

## Zotero

| 主 skill | 边界 |
|---|---|
| `zotero-literature-access` | 仅在父文档缺失、过期或排障时访问 Local API |
| `zotero-library-governance` | 只读盘点整个库的主题、文献集和标签 |
| `project-collection-overlay` | 为一个明确课题生成项目用途覆盖层试运行计划 |

任何 Zotero 写入都不由上述 skill 直接执行，必须进入独立审批流程。

## 主 skill 规则

1. 每个请求默认只有一个主 skill。
2. 辅助 skill 只提供必要的中间产物，不重复生成主输出。
3. 明确请求不先触发 `semantic-route-planner`。
4. 普通任务结尾不触发项目地图能力。
5. 路由仍不确定时，读取本文件；不要同时加载所有 skill 正文。
