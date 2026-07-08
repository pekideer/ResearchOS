# PRISMA Literature Screening Runbook

本操作手册用于在文献综述中维护 PRISMA 检索、筛选、阅读状态和 Zotero 标签镜像 plan。默认不写入 Zotero。

## 适用场景

- 需要按 PRISMA 思路记录文献检索、去重、筛选、全文评估和纳入过程。
- 需要提醒哪些文献待读、重要、缺少计划用途或缺少排除原因。
- 需要后续绘制 PRISMA flow diagram 的计数。
- 需要把少量状态镜像到 Zotero 标签，方便在 Zotero 中筛选。

## 存放位置

具体课题目录中使用：

```text
03-文献矩阵/prisma/
  prisma-search-log.csv
  prisma-records.csv
  prisma-reminders.csv
  prisma-flow-counts.json
  zotero-tag-mirror-plan.json
```

ResearchOS 模板：

- `templates/prisma-search-log.csv`
- `templates/prisma-records.csv`
- `templates/prisma-zotero-tag-map.yml`
- `templates/paper-reading-card.md`

## 主状态原则

- 主状态保存在 `prisma-records.csv` 和读书卡文末 `## 7. 元数据（折叠）`。
- Zotero 只镜像 `rs:*` 标签，不作为 PRISMA 主数据库。
- 不向 Zotero 笔记、PDF、文献集或 item metadata 写入 PRISMA 全量信息。

## 推荐状态字段

`Read Status`：

- `todo`
- `skimmed`
- `done`
- `deep`

`Importance`：

- `core`
- `high`
- `normal`
- `low`

`Planned Use`：

- `review`
- `intro`
- `background`
- `method`
- `discussion`
- `exclude`

多个 计划用途 用分号分隔，例如：

```text
review;intro
```

## Zotero 标签镜像 规则

`tools/build_prisma_status_outputs.py` 会生成以下 tag：

- `rs:read/todo`
- `rs:read/skimmed`
- `rs:read/done`
- `rs:read/deep`
- `rs:priority/core`
- `rs:priority/high`
- `rs:priority/normal`
- `rs:priority/low`
- `rs:use/review`
- `rs:use/intro`
- `rs:use/background`
- `rs:use/method`
- `rs:use/discussion`
- `rs:use/exclude`

生成的 `zotero-tag-mirror-plan.json` 只是 试运行计划。真正写入 Zotero 必须转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。

## 操作步骤

### 1. 初始化文件

在课题目录下创建 `03-文献矩阵/prisma/`，复制模板：

```powershell
Copy-Item templates\prisma-search-log.csv "课题目录\03-文献矩阵\prisma\prisma-search-log.csv"
Copy-Item templates\prisma-records.csv "课题目录\03-文献矩阵\prisma\prisma-records.csv"
```

### 2. 记录检索日志

每次数据库检索都在 `prisma-search-log.csv` 中记录：

- 检索日期
- 数据库
- 检索式
- filters
- 返回数量
- 导出数量
- 导出文件

### 3. 维护 PRISMA 记录

每条候选文献在 `prisma-records.csv` 中至少记录：

- `Record ID`
- `Zotero Item Key` 或明确来源
- `Title`
- `PRISMA Stage`
- `Screening Decision`
- `Read Status`
- `Importance`
- `Planned Use`

被排除文献应填写 `Exclude Reason`。

### 4. 生成读书卡

读书卡文末元数据必须包含：

```yaml
---
zotero_item_key: "[ITEMKEY](zotero://select/library/items/ITEMKEY)"
generated_at: "YYYY-MM-DDTHH:MM:SS+08:00"
generated_by: "ResearchOS"
read_status: "deep"
importance: "core"
planned_use: ["review", "intro"]
prisma_record_id: "PRISMA-0001"
source_text_range: "pp. 1-8"
---
```

### 5. 生成提醒、计数和 mirror plan

```powershell
python tools\build_prisma_status_outputs.py --records "课题目录\03-文献矩阵\prisma\prisma-records.csv"
```

输出：

- `prisma-reminders.csv`
- `prisma-flow-counts.json`
- `zotero-tag-mirror-plan.json`

### 6. Zotero 写入审批

如果用户明确要求把 tags 写入 Zotero：

1. 复核 `zotero-tag-mirror-plan.json`。
2. 转入 `POLICIES/ZOTERO_WRITE_POLICY.md`。
3. 先 试运行。
4. 用户确认。
5. 金丝雀测试。
6. 小批量写入。
7. 保存 执行前/执行后 和 回滚计划。

## 质量检查

- 每条记录有稳定 `Record ID`。
- 每条 Zotero 文献保留 条目 key。
- 读书卡有 `generated_at`。
- 排除文献有排除原因。
- Zotero 写入未被脚本自动执行。
