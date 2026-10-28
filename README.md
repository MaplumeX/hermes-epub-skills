# hermes-epub-skills

把 `layout.json`（PDF/扫描件的 OCR 版面数据）或网页书源转换成干净 Markdown / EPUB 的**实战操作手册**。

这不是一套开箱即用的库，而是从多本中译本（黑格尔、曼昆、萨缪尔森、斯威齐、哈维、藤森赖明等）的实际转换里沉淀出来的**规则、踩坑清单和校验脚本**。每条规则的背后都有一个「曾经做错、被用户指出来」的具体案例。

## 结构：主文件 + 机制篇 + 案例库

```
layout-json-to-epub/
├── SKILL.md              # 入口：开关表 + 主线 + 症状检索表（约 7 K 字符，可通读）
├── references/
│   ├── mechanisms/       # 10 篇机制，按需加载（合计约 82 K 字符）
│   ├── *-case.md         # 17 份案例，一本书一份，只看「差异清单」
│   └── ...
└── scripts/              # 25 个可单独运行的诊断 / 修复 / 校验脚本
```

**为什么这样分**：同一条机制在不同书籍形态里被反复踩到（「跨页合并」在旧版里被复述了 16 遍，「页眉噪声」11 遍）。按书组织会让人先问「我像哪本书」，按机制组织则只问数据特征。

### 主文件怎么用

`SKILL.md` 只有五件事：**8 个形态开关 → 填表判型 → 只读命中的机制篇 → 走唯一主线 → 查症状表**。

形态开关（判型只问数据特征，不问书目）：

| 开关 | 取值 | 判定依据 |
|---|---|---|
| S1 公式 | 无 / MathML / 裁图 | `interline_equation` 块数；span 是否带 `image_path` |
| S2 注释体系 | 无 / 页脚圈码 / 章末数字 / 星号译注 / 尾注另册 | `page_footnote` 块数；书末注释章；标记形态 |
| S3 注释重编粒度 | 每页 / 每章 / 每节 | 同一标记是否在相邻页重复 |
| S4 表格 | 无 / grid / HTML 双栏 | `table` span 是否含 `<table>`；有无 `table_body` |
| S5 插图 | 无 / 少量插页 / 图组 / 图在别处 | `image`/`chart` 块数；`image_caption` 是否存在 |
| S6 结构 | § 结构 / 章-节 / 多级子标题 / title 自带 level | `title` 块形态 |
| S7 附属 | 索引 / 参考书目 / 术语表 / 答案 / 无 | 书末章节标记；`ref_text` 占比 |
| S8 多文件 | 单文件 / 多册合订 / 跨册 | JSON 个数与页数切分 |

主线只有一条：`探型 → extract → build → pandoc → 校验 → 交付`。所有变体都是这条线上的开关组合。

### 10 篇机制

| 篇 | 内容 | 条目 |
|---|---|---|
| M1 `inputs.md` | 多文件合订、分卷 zip、20 MB 上限、图片清单先发 | 14 |
| M2 `page-break-merge.md` | 跨页断句合并，及合并引发的连带故障（错页、y 坐标、附录） | 24 |
| M3 `notes.md` | 多套注释识别、编号修复、双向链接 | 89 |
| M4 `figures.md` | 图题/表题四类来源、六种错位、面板归属、插入位置 | 56 |
| M5 `tables-math.md` | grid 转换、rowspan、双栏、`wrap_math`、单元格内公式 | 58 |
| M6 `quotes.md` | 引文段判定（四轮演进到盲读清单） | 7 |
| M7 `structure-noise.md` | 页眉边注竖排书名、标题层级与子标题判定 | 46 |
| M8 `assembly.md` | pandoc 参数、拆章锚点、封面注入、元数据 | 26 |
| M9 `checks.md` | 三道校验口径，以及「校验全绿但成品是错的」 | 19 |
| M10 `external-ref.md` | 对照英文原文 / DJVU / 扫描页读上标 / 德文术语 | 16 |

M2 / M8 / M9 是主线必读，其余按开关命中才读。

## 关键内容

- **标记对齐**：正文上标 vs 注释条目的逐章/逐节比对，OCR 错读变体（`^{42}`、`^{[1]}`、Unicode 上标 `¹²³`、`^{*86}` 合体标记）
- **从原扫描页读回上标**：`pdftoppm` 渲染 + 双模型一致 + 三道闸校验（`scripts/read_marks_from_scan.py`）
- **图题/表题恢复**：四类来源穷举（子块 / 同页正文 / discarded / 图内），六种错位形态
- **多面板图重建**：按 bbox 归组、面板标签不臆造、行聚类排序
- **跨页断行合并**：必须在 `pages.json` 层做，不能事后改 `book.md`
- **插图/表格插入位置**：不切断正文、上下加分隔线、续文接回（`scripts/reflow_inserts.py`）
- **引文段落转引用格式**：区分「整段转引他人原文」与「作者自己的分析段（即使段末带出处）」，含跨段引文的识别与分块（`scripts/blind_read_quotes.py`）
- **保真度自检**：字符数比值 + 块级清单 + 图片引用集合差

### `web-to-epub/`

网页书源（marxists.org、在线文档）→ EPUB，以及已有 EPUB 改目录结构。它的 `references/epub-internal-structure.md` 是**跨管线通用的 EPUB 格式规范**（拆章、双向脚注、content.opf/nav、EPUB2 vs EPUB3），`layout-json-to-epub` 里遇到格式疑问要回查这一份。

## 脚本

`scripts/` 下 29 个脚本都能单独跑，大多接受「输入文件 + 退出码即结论」的形态：

```bash
# 校验成品
python3 layout-json-to-epub/scripts/validate_epub.py out.epub
java -jar epubcheck.jar out.epub

# 诊断：标记对齐 / 双注释体系 / 图题完整性 / 表格合法性 / 块丢失
python3 layout-json-to-epub/scripts/diag_two_note_systems.py pages.json
python3 layout-json-to-epub/scripts/align_marks_notes.py ...
python3 layout-json-to-epub/scripts/check_caption_completeness.py pages.json fig
python3 layout-json-to-epub/scripts/check_tables_pandoc.py book.md
python3 layout-json-to-epub/scripts/check_loss_blocks.py book.md A=docA_layout.json

# 引文判读（拆成盲读版 → 逐章人工/并行 subagent 判读 → 段号回映射成段首清单）
python3 layout-json-to-epub/scripts/blind_read_quotes.py split book.md read/
python3 layout-json-to-epub/scripts/blind_read_quotes.py merge answers.json read/ quotes.py

# 排版后处理
python3 layout-json-to-epub/scripts/merge_page_breaks.py ...
python3 layout-json-to-epub/scripts/reflow_inserts.py book.md book_final.md
```

## 三条贯穿全篇的原则

1. **只认实读，绝不猜。** OCR 整处丢失的上标，没有扫描页就如实报缺口（附逐章清单），不用启发式硬插。
2. **数量对 ≠ 编号对。** 必须校验「严格递增序列」和「正文序列 == 注释序列」，并检查锚点 id 唯一性。
3. **交付前换新文件名 + 报 md5。** 同名附件反复交付时，对方点开的往往是旧版。

## 用法

这些文件是 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的技能目录格式（`SKILL.md` + `references/` + `scripts/`）。放进 `~/.hermes/skills/<category>/` 即可被 agent 按需加载；也可以直接当人工操作手册读——`SKILL.md` 与 `mechanisms/` 里的每一条都是可直接执行的判据。

## License

MIT（仅限本仓库的文字与脚本；`references/` 中出现的书名、引文片段版权归原权利人，仅作技术案例说明之用。）
