# Zotero 与 ResearchOS 工作流

## 分工

Zotero 是文献库主系统，负责：

- 文献条目
- PDF 附件
- collection
- tag
- note
- 引文信息

ResearchOS 是方法论与生成物工作区，负责：

- 检索路线
- 读书卡
- PRISMA 检索筛选状态
- 综述矩阵
- 写作大纲
- 论断-证据审计
- 审稿回复草稿

## Collection、Tag、Note 配合方式

- Zotero collection 用于保存项目或主题下的文献集合。
- Zotero 标签 用于标注文献属性，如方法、对象、场景、数据类型、待读、已读。
- Zotero note 可用于保存最终人工确认后的读书卡摘要。
- ResearchOS 生成的读书卡优先保存在 `corpus/reading-cards/cards/`；无课题目录时先确认项目路径或进入平级 `0.Inbox/`。
- PRISMA 主状态保存在 `03-文献矩阵/prisma/prisma-records.csv` 和读书卡 YAML 头部；Zotero 只镜像少量 `rs:*` 标签。
- Zotero note 可用于保存最终人工确认后的摘要，但默认脚本不自动写 note。

## 父文档优先读取流程

1. 先查询 `corpus/zotero/M-001-zotero-library/zotero_library.sqlite`。
2. 通过 条目 key、标题、作者、DOI 或关键词确认候选条目。
3. 使用 `tools/zotero/build_zotero_library_context_packet.py` 构建题录、attachment 和 规范化文本 上下文包。
4. 优先读取 SQLite 中 `text_normalized_cache_path` 指向的文本。
5. 如果 SQLite 中的绝对路径因跨设备同步失效，回退到当前工作区 `corpus/fulltext/zotero-library-normalized/ITEMKEY__ATTACHMENTKEY.txt`。
6. 将父文档中的题录和 规范化文本 交给阅读、综述、AI 分类或治理 skill。

## Local API 维护流程

1. 只有父文档缺失、过期、路径失效或需要增量同步时，才打开 Zotero 桌面端并启用 Zotero Local API。
2. 使用 `tools/zotero/zotero_library_index.py sync` / `watch` 更新 SQLite 父文档和 PDF text 缓存链接。
3. 使用 `tools/zotero/zotero_library_index.py normalize-text-cache` 维护 `zotero-library-normalized/`。
4. `tools/zotero/zotero_local_api_cli.py` 只作为底层排障或维护工具，不作为普通阅读、综述或治理的默认入口。

## 读书卡与 Zotero note

默认不由脚本自动写回 Zotero note。推荐流程：

1. 在 ResearchOS 中生成读书卡。
2. 用户核查事实、引用和页码。
3. 删除不确定或未经证实的内容。
4. 手动复制最终版摘要到 Zotero note。
5. 如用户手动回填 Zotero note，应保留 ResearchOS 输出日期和核查状态。

## PRISMA 状态如何镜像 Zotero 标签

1. 在 `prisma-records.csv` 和读书卡 YAML 头部 中维护主状态。
2. 使用 `tools/reading_cards/build_prisma_status_outputs.py` 生成 `zotero-tag-mirror-plan.json`。
3. 复核 plan 中的 `rs:*` 标签。
4. 如需写入 Zotero，转入 `POLICIES/ZOTERO_WRITE_POLICY.md` 和 `RUNBOOKS/zotero-web-api-write-canary.md`。

## 安全边界

- 默认不写入 Zotero；任何写入必须由用户单独确认具体 plan。
- 不读取或修改 `zotero.sqlite`。
- 不移动、复制、删除或重命名 Zotero PDF。
- 不保存 API key。
- 不把 Zotero storage 放进 ResearchOS。
