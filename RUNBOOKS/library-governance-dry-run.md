# Library Governance Dry Run Runbook

本操作手册用于 Zotero 文献库治理试运行。默认只读，只生成矩阵、报告和 plan。默认事实源是 ResearchOS 共享事实源：`corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`；`.researchos/outputs/machine/` 保存可再生成的机器留存。

## 适用场景

- 盘点 Zotero 文献库字段、文献集、tag 和期刊。
- 发现无分类、无 标签、元数据缺失、主题相近或疑似重复文献。
- 形成可人工审批的治理 plan。

## 步骤

### 1. 父文档上下文盘点

```powershell
python tools\build_zotero_library_context_packet.py --query "KEYWORD" --limit 20
```

输出：

- `zotero-library-context-packet.md`
- `zotero-library-context-packet.jsonl`
- `zotero-library-context-index.csv`

### 2. Library matrix

```powershell
python tools\zotero_ai_governance.py prepare-corpus
```

输出：

- `ai-governance-corpus.jsonl`
- `ai-governance-corpus-preview.csv`

### 3. Topic clusters

```powershell
python tools\zotero_ai_governance.py prepare-corpus
```

输出：

- `zotero_similar_pairs.csv`
- `zotero_topic_clusters.md`
- `zotero_topic_cluster_plan.json`

### 4. Governance semantic plans

```powershell
python tools\zotero_ai_governance.py build-plan
python tools\zotero_ai_governance.py aggregate-directions
python tools\zotero_ai_governance.py build-collection-plan
python tools\zotero_ai_governance.py build-tag-plan
```

输出：

- `ai-governance-classification-plan-report.md`
- `research-direction-aggregation-report.md`
- `collection-restructure-plan.md`
- `tag-aggregation-plan.md`
- 相关 CSV/JSON 计划文件；仅供审批，不自动写入 Zotero。

### 5. Local API 维护入口

只有父文档缺失、过期或需要排障时，才显式允许 Local API 维护工具读取 Zotero：

```powershell
python tools\zotero_library_index.py sync
python tools\zotero_fast_collection_sync.py --include-items
```

## 人工审批

审批前必须检查：

- 每条建议是否保留 条目 key。
- 分类依据是否来自题目、摘要、标签、期刊或用户规则。
- 疑似重复是否只是候选，而非删除指令。
- 是否需要进入 `RUNBOOKS/zotero-web-api-write-canary.md`。

## 完成标准

- 已生成只读矩阵、聚类、报告和 plan。
- 未写入 Zotero。
- 写入相关内容仅作为待审批计划。
