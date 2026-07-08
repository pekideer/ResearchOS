# ResearchOS 长任务状态模板说明

长任务中断后，优先使用具体课题目录下的 `.research/` manifest 体系恢复上下文。

不要在 `.research/` 或 run state 中保存 API key、Zotero 数据库路径、PDF 缓存、Zotero storage 或敏感未发表全文。

## 推荐目录

```text
课题目录/
  .research/
    project_manifest.yml
    run_state.json
    experiment_matrix.yml
    data_dictionary.yml
    open_questions.md
  03-文献矩阵/
    prisma/
      prisma-records.csv
      prisma-search-log.csv
```

## `project_manifest.yml`

用途：让未来 AI 或研究者快速理解课题状态、研究问题、输入材料和输出位置。

模板：`templates/research-project-manifest.yml`

核心字段：

- `project`：课题名、阶段、负责人和更新时间。
- `research_focus`：研究背景、研究问题、假设和关联 gap。
- `sources`：读书卡、综述矩阵、Zotero 条目 key、数据和稿件位置。
- `outputs`：课题输出目录。
- PRISMA 综述项目可在 `outputs` 或 `sources` 中记录 `03-文献矩阵/09-治理记录/prisma-records.csv`、`prisma-search-log.csv` 和 `zotero-tag-mirror-plan.json`。
- `status`：当前阶段、完成步骤、待审批事项、阻塞原因和下一步。
- `safety`：确认不保存 API key、Zotero 数据库或 PDF 缓存。

## `run_state.json`

用途：记录当前执行状态，便于中断恢复。

模板：`templates/research-run-state.json`

```json
{
  "project_name": "",
  "current_stage": "",
  "last_completed_step": "",
  "source_items": [],
  "outputs": [],
  "pending_user_approval": [],
  "blocked_reasons": [],
  "next_actions": []
}
```

## `experiment_matrix.yml`

用途：记录实验、模型、验证路径和输出。

模板：`templates/research-experiment-matrix.yml`

## `data_dictionary.yml`

用途：记录数据来源、变量、单位、角色和限制。

模板：`templates/research-data-dictionary.yml`

## `open_questions.md`

用途：记录研究问题、证据问题、方法问题、用户决策和阻塞项。

模板：`templates/research-open-questions.md`

## 使用规则

- `.research/` 是状态索引，不替代原始数据、论文全文或 Zotero。
- 条目 key、文件路径、矩阵路径可以记录；真实 API key 和敏感缓存不得记录。
- 每次长任务结束时，建议更新 `last_completed_step`、`outputs` 和 `next_actions`。
