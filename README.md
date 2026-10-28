# hermes-epub-skills

把 `layout.json`（PDF/扫描件的 OCR 版面数据）或网页书源转换成干净 Markdown / EPUB 的**实战操作手册**。

这不是一套开箱即用的库，而是从多本中译本（黑格尔、曼昆、萨缪尔森、斯威齐、藤森赖明等）的实际转换里沉淀出来的**规则、踩坑清单和校验脚本**。每条规则的背后都有一个「曾经做错、被用户指出来」的具体案例。

## 包含两个技能

### `layout-json-to-epub/`
主技能。处理 `layout.json` → Markdown → EPUB 的完整管线。

覆盖的书籍形态（每种形态的坑完全不同，**开工前先判定属于哪一类**）：

| 变体 | 特征 | 案例文件 |
|---|---|---|
| 黑格尔式 § 结构 | `**§ N**`、`说明/附释` 类型状态机、德文术语校对 | `references/hegel-encyclopedia-case.md` |
| 章末注释（prose） | 正文 `^{N}` 上标、注释集中在书末、页脚 `*` 译注 | `references/houlgate-introduction-case.md` |
| 逐节讲解 + 圈码注释 | 每节从 ① 重新编号、裸圈码=丢失上标 | `references/zhang-shiying-yizhu-*.md` |
| 尾注（附注）制 + 跨册合订 | 注释在另一册、英文原版版本不匹配时编号不可搬运 | `references/ordeal-by-fire-case.md` |
| 教科书（MathML + HTML 表 + 图组） | 数百行间公式、图题/表题被 OCR 拆散或丢进 discarded | `references/mankiw-*.md`、`micro-theory-11e-case.md`、`samuelson-economics-19e-case.md`、`varian-microeconomics-case.md` |
| 学术专著（全书 MathML） | 双栏、索引跨页、网格表格 | `references/marx-math-econ-case.md`、`sweezy-capitalist-development-case.md` |
| 中译本学术专著·双注释体系 | 页脚圈码注（每页从 ① 重编）+ 章末「译注」数字注、`ref_text` 独立块类型 | `references/harvey-limits-to-capital-case.md` |

关键内容（都写在 `SKILL.md` 里）：

- **标记对齐**：正文上标 vs 注释条目的逐章/逐节比对，OCR 错读变体（`^{42}`、`^{[1]}`、Unicode 上标 `¹²³`、`^{*86}` 合体标记）
- **从原扫描页读回上标**：`pdftoppm` 渲染 + 双模型一致 + 三道闸校验（`scripts/read_marks_from_scan.py`）
- **图题/表题恢复**：四类来源穷举（子块 / 同页正文 / discarded / 图内），六种错位形态
- **多面板图重建**：按 bbox 归组、面板标签不臆造、行聚类排序
- **跨页断行合并**：必须在 `pages.json` 层做，不能事后改 `book.md`
- **插图/表格插入位置**：不切断正文、上下加分隔线、续文接回（`scripts/reflow_inserts.py`）
- **引文段落转引用格式**：区分「整段转引他人原文」与「作者自己的分析段（即使段末带出处）」，含跨段引文的识别与分块（`scripts/blind_read_quotes.py`、`check_quote_paragraphs.py`）
- **保真度自检**：字符数比值 + 块级清单 + 图片引用集合差

### `web-to-epub/`
网页书源（marxists.org、在线文档）→ EPUB，以及已有 EPUB 改目录结构。它的 `references/epub-internal-structure.md` 是**跨管线通用的 EPUB 格式规范**（拆章、双向脚注、content.opf/nav、EPUB2 vs EPUB3），`layout-json-to-epub` 里遇到格式疑问要回查这一份。

## 脚本

`scripts/` 下 29 个脚本都能单独跑，大多接受「输入文件 + 退出码即结论」的形态：

```bash
# 校验成品
python3 layout-json-to-epub/scripts/validate_epub.py out.epub
java -jar epubcheck.jar out.epub

# 诊断：标记对齐 / 图题完整性 / 表格合法性 / 块丢失
python3 layout-json-to-epub/scripts/align_marks_notes.py ...
python3 layout-json-to-epub/scripts/diag_two_note_systems.py pages.json
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

这些文件是 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的技能目录格式（`SKILL.md` + `references/` + `scripts/`）。放进 `~/.hermes/skills/<category>/` 即可被 agent 按需加载；也可以直接当人工操作手册读——`SKILL.md` 里的每一条都是可直接执行的判据。

## License

MIT（仅限本仓库的文字与脚本；`references/` 中出现的书名、引文片段版权归原权利人，仅作技术案例说明之用。）
