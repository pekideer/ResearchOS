# ResearchOS 本机持续科研模式

本文件定义跨会话继续课题时的唯一上下文恢复链。其他 skill、工作流和工具只能引用本链，不得另设优先级。

## 何时执行

用户提到“当前课题”“继续上次”“研究进展”“阅读卡”“论文进展”“周汇报”“项目记忆”，或在 ResearchOS 框架目录中发起具体课题任务时执行。普通独立问答不执行。

## 四层状态职责

```text
active_project.yml       只回答“当前是哪一个项目”
project_manifest.yml     保存稳定项目事实和规范输出位置
run_state.json           保存当前可恢复快照
run-log.jsonl            只追加最小运行历史
```

- 项目正文、论文全文、完整对话、API key、Zotero 数据库/PDF 路径不得写入上述状态文件。
- `run-log.jsonl` 是审计线索，不是事实源；与项目当前文件冲突时，以当前项目文件为准。

## 唯一恢复链

### 1. 定位项目

按以下顺序选择第一个可唯一定位的项目：

1. 用户本轮明确指定的项目路径。
2. 当前工作目录或其上级中存在 `.research/project_manifest.yml` 的项目。
3. `00_ResearchOS/.researchos/active_project.yml`。
4. `%USERPROFILE%/.researchos/active_project.yml`。
5. 项目登记：先 `00_ResearchOS/.researchos/project_registry.yml`，再 `%USERPROFILE%/.researchos/project_registry.yml`。
6. 仍未定位时，只扫描 ResearchOS 父目录一级子目录中的 `.research/project_manifest.yml`。

`machine_config.json` 只负责把 `root_key` 映射为本机路径，不决定当前项目。优先读取 `%USERPROFILE%/.researchos/machine_config.json`；没有配置时，`projects_root` 默认为 ResearchOS 父目录。

若两个候选项目同优先级且无法消解，列出候选并向用户确认，不猜测。

### 2. 读取最小恢复包

项目定位后，先只读取存在的轻量文件：

1. `.research/project_manifest.yml`
2. `.research/run_state.json`
3. `.research/run-log.jsonl` 最后 5 条有效记录
4. `.research/project_overview_and_plan.md`
5. `.research/material_index.md`

随后根据本轮任务按需读取：文献任务读阅读计划、读书卡指针和矩阵；论文任务读用户指定稿件和必要 `.paper/` 索引；实验任务读实验矩阵和数据字典。不要为了恢复上下文读取全部全文。

### 3. 处理冲突

信息冲突时按以下优先级判断：

```text
用户本轮明确说明
→ 当前项目原始/人读文件
→ project_manifest.yml
→ run_state.json
→ run-log.jsonl
→ active_project.yml
→ project_registry.yml
→ 其他历史记忆
```

不得静默覆盖冲突。对会改变项目目标、研究问题、证据状态或输出位置的冲突，向用户说明；只涉及过期进度时，可按当前文件更新状态并记录来源。

### 4. 输出恢复摘要

执行任务前用不超过 6 行说明：当前项目与定位依据、当前阶段和本轮目标、已恢复的关键材料、缺失或冲突信息，以及本轮预计输出位置。

## 状态更新

以下任务完成后更新 `.research/run_state.json` 并向 `.research/run-log.jsonl` 追加一条记录：

- 长任务或多步骤任务。
- 创建、修改或移动了项目文件。
- 形成了新的研究判断、审批状态或阻塞项。
- 需要跨会话交接。

简单问答、纯解释、没有状态变化的只读查看不记录。

- 只在稳定项目事实、研究问题或规范输出位置改变时更新 `project_manifest.yml`。
- 只在切换当前项目时更新 `active_project.yml`。
- `run_state.json` 可覆盖，表示最新快照。
- `run-log.jsonl` 只追加，不改写历史；纠错时追加新记录并引用原 `run_id`。

最小字段和隐私规则见 `templates/project-state/run-state.json`、`templates/project-state/run-record.json`。

## 项目与输出边界

- `project_root` 必须是具体课题目录，不是 `00_ResearchOS`。
- 具体成果写入项目工作区；ResearchOS 自身治理说明写入 `docs/`。
- 读书卡默认使用 `corpus/reading-cards/cards/` 集中主卡和项目指针。
- 尚未归属的人工材料进入与 ResearchOS 平级的 `0.Inbox/`。
- Zotero 默认只读；父文档正常时不直接访问 Local API/PDF。
- 同步状态中的路径使用项目相对路径或便携指针，不写本机绝对项目路径。

## 完成标准

- 当前项目定位可解释且唯一。
- 只加载了本轮必要的上下文。
- 恢复摘要区分事实、推断和缺失项。
- 需要留痕的任务已更新快照并追加最小日志；普通问答没有制造噪声记录。
