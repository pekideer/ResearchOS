# Tools 治理记录（2026-07-12）

## 目标

按功能主题组织 `tools/`，减少重复 Python 实现，修复移动造成的代码、文档、skill、
测试和 PowerShell 路径依赖。

## 结果

- Python 文件从 29 个减少到 28 个；`tools/` 顶层 Python 文件从 21 个减少到 1 个。
- 建立 `zotero/`、`reading_cards/`、`project/` 和 `runtime/` 四个主题目录。
- Zotero governance 和 Web API write 作为 `zotero/` 下的内部功能组保留。
- 将读书卡元数据解析和期刊等级格式化合并到 `reading_cards/card_common.py`，删除两份旧
  helper，其他读书卡脚本统一引用新共享模块。
- 将两个 Zotero 写入脚本重复的环境配置、脱敏代理选择和 HTTP 请求逻辑集中到
  `zotero/write/zotero_web_api.py`。
- 修正所有 Python 包导入、ResearchOS 根目录层级和三个 PowerShell 脚本的根路径计算。
- 同步更新工具契约、索引、策略、runbook、skills、README、模板和测试引用。

## 未合并项及理由

- 项目 collection overlay、通用追加式写入和 deleted-collection 引用修复仍保留独立
  执行入口。它们的计划格式、权限范围、版本控制和回滚语义不同，合并会扩大单个高风险
  工具的权限面。
- Zotero Local API 库与 CLI 保持分离：前者是共享只读客户端，后者是人工排障入口。
- 父文档全量索引与文献集快同步保持分离：前者处理附件、全文和 OCR，后者只维护轻量
  collection/metadata 状态。

## 验证

- 28 个 Python 模块通过 AST 解析。
- 20 个 Python CLI 入口通过 `--help` 冒烟检查。
- 3 个 PowerShell 脚本通过语法解析。
- 专项测试 16 项通过。
- 完整测试套件 22 项通过。
- 全仓旧工具路径和旧模块导入残留为 0。
