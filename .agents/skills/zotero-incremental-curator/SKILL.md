---
name: zotero-incremental-curator
description: 编排 Zotero 增量治理：条目身份、读书卡、单位、内容 #tags、项目 collection 与受控写入分别取证和验收。
---

# Zotero 增量治理编排

## 固定边界

- 读取走父文档或只读 Local API；不得读取 `zotero.sqlite`，不得改动 PDF 或 annotation。
- 作者单位、精读结论、内容标签和项目用途由当前 agent 判断；工具只准备证据、验证状态和应用已批准计划。
- 内容 `#tags` 与项目 collection 是两条独立语义管线：前者只看文献自身内容，后者才使用项目目标和用途。
- 阅读状态以集中读书卡为事实源，可在批准后镜像互斥的 `rs:read/todo`、`rs:read/initial-card`、`rs:read/deep-read`。
- note、item tags、project collection 的真实写入分别审批；本 skill 不自动取得写权限。

## 执行顺序

1. 冻结同步前后的顶层条目 `key + version` 快照，识别新增、修改、删除和 DOI 重键。
2. 在本机 staging 更新父文档；未由 Corpus Publisher 发布前不得报告共享 `corpus/` 已更新。
3. 审计每个父条目下 ResearchOS 读书卡 note：允许 0 或 1 条；多条立即阻断该条目的 note 写入。
4. 当前 agent 从首页证据识别第一作者一级机构与国家；保存原文和页码，显示为“中文一级机构，中文国家”。
5. 有规范化全文时执行 `paper-deep-reading`；摘要卡不得冒充 `full_text_reviewed`。
6. 对新增/需补足条目单独运行 `zotero-library-governance` 的 `content-tags` 管线。不得把项目名称、现有 collection、项目用途或当前 tags 放进内容标签证据。
7. 需要项目归属时另用 `project-collection-overlay`，以项目目标和用途判断 collection；该结果不得反向改变内容标签。
8. 分别生成 note plan、冻结 item mutation plan 和 project overlay dry-run。item mutation plan 必须绑定来源包哈希，并冻结每条目的 `version + tags + collection_keys` 与预期写后状态。
9. 真实写入前对整批所有条目做全局预检；任一审批后漂移，整批在任何 PATCH 前停止。写后逐条回读并保存 rollback。

## 完成报告

报告新增/修改/删除/重键、卡片 0/1/多条、全文精读、中文单位、内容标签、项目 collection、note、共享语料发布的完成/待审批/阻断状态。不得把占位卡报告为精读完成，也不得把 staging 报告为共享主库已更新。
