# Zotero 文献库治理试运行

本流程默认只读。事实源为 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite` 与 `corpus/fulltext/zotero-library-normalized/`。

## 先选任务

- 补足/重建文献内容 `#tags`：选择 `content-tags`。
- 审查领域、主题文献集或库结构：选择 `library-structure`。
- 两者同时需要时分别运行，不得把项目/collection 选择上下文送入内容标签判断。

## 内容标签

```powershell
python tools\zotero\zotero_ai_governance.py prepare-corpus --task content-tags
python tools\zotero\zotero_ai_governance.py build-agent-packet --task content-tags
python tools\zotero\zotero_ai_governance.py build-plan --task content-tags --results-jsonl RESULTS.jsonl
```

检查生成的语料记录：必须有 `semantic_scope=document_content_only`、`selection_is_not_evidence=true` 和 `evidence_hash`；不得出现 `current_state`、当前 tags、collection paths 或项目用途。当前 agent 只从文献内容生成六类 `#` 命名空间标签。

## 文献库结构

```powershell
python tools\zotero\zotero_ai_governance.py prepare-corpus --task library-structure
python tools\zotero\zotero_ai_governance.py build-agent-packet --task library-structure
python tools\zotero\zotero_ai_governance.py build-plan --task library-structure --results-jsonl RESULTS.jsonl
```

此任务可在 `current_state` 中单列现有 tags 和 collection paths，只用于审查库结构，不输出内容标签。

## 普通阅读上下文

```powershell
python tools\zotero\build_zotero_library_context_packet.py --profile content --item-key ITEMKEY --include-text
```

只有明确治理库结构时才使用 `--profile library`。

## 审批边界

`build-plan` 产物仍是只读语义计划。若用户要求写 Zotero，必须另行构造绑定来源包哈希和完整条目快照的 item mutation plan，再按 Web API 写入 runbook 预检、审批、金丝雀、执行和回读。

完成标准：语义任务边界明确、证据可回溯、代码未作科研语义判断、未写入 Zotero。
