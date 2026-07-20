# 共享 corpus 发布与项目写入门禁契约

## 1. 工具

- `tools/runtime/publish_corpus.py`
- `tools/runtime/project_write_guard.py`
- `tools/runtime/project_handoff.py`
- `tools/reading_cards/zotero_library_pipeline.py`

## 2. 作用

摄取和语料准备默认写入本机 `M-006` staging。共享 corpus 只能由 `corpus_role=publisher` 的终端通过冻结计划发布；所有可识别的项目文件写入入口必须在首个写操作前通过项目 `check-write`。

跨多个 Junction 的发布不是单一文件系统事务。实现采用“逐文件同目录原子替换，最终 release manifest 提交”的语义原子模型：manifest 最后写入；读取端发现 manifest 所列文件缺失或哈希不符时必须停止，不得消费混合版本。

## 3. 发布流程

1. `plan` 只读取 staging 和目标基线，校验允许区域、文件哈希和 SQLite `PRAGMA quick_check`，不写 corpus。
2. 人工核对冻结的 `plan_hash`、文件范围、基线和回滚范围。
3. 真实写入必须另行批准金丝雀；`apply` 同时要求 Corpus Publisher 角色和显式 `--apply`。
4. apply 重新校验源哈希和目标基线，备份旧文件，再逐文件原子替换；release manifest 最后提交。
5. `verify` 对 manifest 中全部文件回读哈希，并复查 SQLite。
6. rollback 需要独立冻结计划、Corpus Publisher 角色和显式批准；新增文件的回滚会删除该精确文件，不能扩展到计划外目标。

## 4. 允许区域

- `corpus/zotero/M-001-zotero-library/`
- `corpus/fulltext/zotero-library/`
- `corpus/fulltext/zotero-library-normalized/`
- `corpus/reading-cards/cards/`
- `corpus/reading-cards/indexes/`

计划不支持“以 staging 缺失代表删除”，因此不会隐式删除共享文件。

## 5. 项目写入门禁

- 项目写入前必须校验项目 identity、活动写入终端、Agent Core commit、corpus snapshot ID 和 content hash。
- 写入目标必须解析在同一项目根目录内；越界、跨项目、handoff 缺失、所有权不匹配或锚点漂移时整体停止。
- `create_project_workspace.py` 的新项目初始化是唯一 bootstrap 特例：创建 manifest 后立即建立 handoff；已有项目没有有效 handoff 时不得继续修改。
- `dry-run` 和纯读取不申请项目写权限。
- tmp、cache、preview 和 render 不得写入项目 `.research/`；项目内需保留的语料包进入 `02-证据材料/`，可重建机器材料优先进入本机 `.researchos/`。

## 6. 当前审批状态

实现、自动测试和脱敏临时目录金丝雀已获批准。真实 corpus 冻结计划 `corpus-74add221724a0848` 已获单独批准并在发布端完成 apply/verify；这次批准不延续为后续 apply、rollback、删除、项目换端或 Zotero 写入授权，跨端同步后回读仍只允许只读验证。
