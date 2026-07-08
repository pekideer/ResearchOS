# ResearchOS 分发说明

本文档只保留面向人的分发版本说明和发送前检查。导出 kit 时的智能体执行规则、隐私扫描细则和剔除清单以 `docs/modes/AGENTS.kit-export.md` 为准。

## 1. 分发版本

### 1.0 GitHub Public Repository

适合公开传播。它必须让新用户 pull 后能直接让 Codex 作为科研助理工作，而不是先面对一个代码开发项目。

应包含通用规则、自然语言入口、quickstart、隐私边界、skills、工作流、质量检查、模板、示例配置和经过审查的通用工具。

不得包含真实 Zotero 数据库、规范化全文、真实读书卡、项目进展、具体课题材料、本机路径、密钥或本地报告。公开仓库中的 `corpus/` 只保留说明文件；真实语料由用户在本地生成。

### 1.1 ResearchOS Personal Reuse Kit

适合发给可信合作者或自己的另一台电脑。它可以保留完整框架文档、质量检查、工具契约层、评测规则、操作手册、模板、参考资料、`.agents/skills/` 和经过审查的通用 `tools/`。

不应包含个人 Zotero 数据、PDF、缓存、真实输出、密钥、本机路径、具体课题材料或未公开论文材料。

### 1.2 ResearchOS Starter Template

适合发给新用户作为空白模板。它保留核心智能体规则、自然语言路由、标准工作流、质量检查、策略、操作手册、skills、模板、参考资料和低风险通用工具。

不应包含项目状态记录、真实点子、真实读书卡、真实 PRISMA 状态、评测记录、个人配置或具体课题痕迹。

## 2. 发送前检查

打包前应确认：

1. 已读取并执行 `docs/modes/AGENTS.kit-export.md`。
2. `.env`、真实密钥、令牌和代理账号没有进入压缩包。
3. `outputs/`、`local-cache/`、`.researchos/` 中的真实状态和本机配置没有进入压缩包。
4. Zotero PDF、Zotero storage、`zotero.sqlite` 和真实 Zotero 导出没有进入压缩包。
5. 真实课题目录、读书卡、综述矩阵、PRISMA records、论文草稿、审稿意见和未公开材料没有进入空白模板包。
6. README、配置示例和模板中没有发送者个人绝对路径。
7. `TOOL_CONTRACTS.md` 和 `TOOL_CONTRACTS/` 已随框架一起分发，除非导出模式明确裁剪。
8. `KIT_MANIFEST.md` 已列出包含路径、剔除路径、隐私扫描摘要、已知限制和接收者本地配置说明。

## 3. 推荐分发方式

优先发送 `outputs/release/<release-id>/` 下生成的 zip 文件，而不是直接压缩整个工作区。直接压缩整个工作区容易误带缓存、输出和个人配置。
