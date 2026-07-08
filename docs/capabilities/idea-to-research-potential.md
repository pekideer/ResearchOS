# 点子到研究潜力能力说明

## 定位

点子捕获不是 ResearchOS 根目录中的长期内容库。ResearchOS 只维护能力规则、模板、质量边界和触发链路；具体点子正文、研究简报、来源记录、候选文献和阶段性判断必须写入用户指定项目工作区。

## 默认存储边界

- 已有项目路径：写入该项目工作区，优先使用项目内 `04-决策记录/`、`06-报告材料/`、`10-批注/` 和必要的 `.research/` 索引。
- 暂无项目归属：写入 `00_ResearchOS` 平级的 `0.Inbox/02-unassigned-ideas/`，等待人工分流。
- ResearchOS 本体：只保存本说明、模板、skill 规则和治理记录，不保存具体点子正文。

## 触发链路

```text
用户点子/碎片知识
-> TRIGGERS.md
-> idea-to-research-potential skill
-> templates/idea-*
-> QUALITY_GATES.md
-> 指定项目工作区或 0.Inbox
```

## 持久化入口

点子捕获由 skill、模板和项目工作区/平级 `0.Inbox` 完成。
