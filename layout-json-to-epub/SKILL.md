---
name: layout-json-to-epub
description: 从 layout.json 版面数据提取书籍全文为干净 Markdown/EPUB。
---

# layout.json → 干净 Markdown/EPUB

## 触发条件

用户发送 layout.json 文档（保存在 `~/.hermes/cache/documents/doc_*_layout.json`），要求「提取全文并整理为干净的 Markdown/EPUB，整理好目录、脚注、引用」。

## 开工前读什么（固定顺序）

1. **本文件**（读到「形态开关表」即可，不必通读）
2. **`references/mechanisms/` 里与本书开关相关的 1–3 篇**（按开关表的「打开」列选，**不要全读**；M2 / M8 / M9 无条件必读）
3. **`web-to-epub` 技能的 `references/epub-internal-structure.md`** —— 跨管线通用的 EPUB 格式规范（拆章、双向脚注写法、content.opf/nav、EPUB2 vs EPUB3）。本技能只管内容抽取与排版，格式层疑问一律回查那份
4. **一本同形态的 `references/*-case.md`**（见「案例库索引」）—— 只看「差异清单」，**不复用其阈值**
5. 按需：从原扫描页读上标 → `ocr-and-documents`、`pdf`（pdftoppm/qpdf）；书源不是 layout.json 而是网页 → 整体换成 `web-to-epub`
6. **反方向**（用户发来一本现成 EPUB，要「还原成原 md、一章一文件、图注引用块、例题/定义用分隔线」）→ `references/epub-to-markdown.md`。**第一件事是 `find` 全盘找原工作区**（同一本书常有多版 `book.md`，用逐章 CJK 比对认出与 EPUB 同源的那份，优先直接用它）；公式取 MathML 的 `x-tex` 注解；**图注≠图题**（图注=图下解释文字→引用块，图题保持加粗）；例题边界止于「请回答」；最后 pandoc 重出 EPUB 并核对 blockquote/math 计数

**同一本书的新版本只读旧 case 的「差异清单」，不复用旧脚本的阈值**（如曼昆 11e vs 10e 的五处致命差异）。

**回答「你会读什么」这类元问题时**：先给结论（主技能一个 + 必读交叉引用一份），再列按需项；不要展开到 pages.json/book.md 等中间产物的细节——用户追问才展开。

## 数据格式（layout.json）

- 顶层 `pdf_info`：页列表（每页一个 dict）
- 每页 `preproc_blocks`：正文块（type: text/title）；块文本 = 各 line 的 span content 用空格 join
- 每页 `discarded_blocks`：噪声块（type: header 页眉 / page_number 页码 / footer 出版社页脚 / page_footnote 脚注文本）
- 脚注标记：正文内嵌 ①②③（圈码）、`*`、`**`；脚注文本块以同样标记开头
- 页码边注 `[11]` `[44]` 内嵌正文流 —— 用户明确要求去掉
- span 类型还有 `inline_equation`（内含 `^{N}` 上标 / `^{①}` 标记 / 其余是公式）、`ref_text`（参考书目、注释条目、索引条目——**独立块类型，不是 text**）、`table_body`（表格 HTML 藏在子块里）

### pages.json 契约（scripts/ 复用的前提）

`scripts/` 里读中间产物的脚本，**各自绑定了三套互不兼容的字段名**。换项目前先看这张表，否则脚本会静默返回 0 或直接 KeyError（哈维案例实测：`check_caption_completeness.py` 崩在 `KeyError: 'type'`，`merge_page_breaks.py` 崩在 `KeyError: 'body'`）。

| 脚本 | 页级键 | 块级键 | 出处 |
|---|---|---|---|
| `align_marks_notes.py`、`batch_report_marks.py`、`merge_page_breaks.py` | `body` / `footnotes` / `file` / `pi` | `text` / `y` | 黑格尔·张世英期 |
| `attach_captions.py`、`check_caps.py`、`check_caption_completeness.py`、`rebuild_panels.py` | `blocks` / `file` / `pi` | `type` / `text` / `cap` / `fnote` / `bbox` | 曼昆·萨缪尔森期 |
| `check_end_matter_and_loss.py` | `file` / `pi` | `type` / `bbox` / `lines` | 同上 |
| `diag_two_note_systems.py` | — | `t` / `s` | 哈维期 |
| `check_loss_blocks.py` | 直接读 **raw layout.json** | `type` / `lines` | 通用 |
| 其余（成品级：`validate_epub` / `check_grid_tables` / `check_tables_pandoc` / `check_figure_pairing` / `check_quote_paragraphs` / `fix_epub_links` / `wrap_math` / `blind_read_quotes`） | 吃 `book.md` 或 `.epub`，**与 schema 无关，可直接用** | | |

**新项目开工时做一件事就能让大半脚本直接可用**：extract 输出的块同时写 `t` 和 `type`、`s` 和 `text` 两个别名；页级同时写 `blocks` 和 `body`。多两个字段，换掉一轮「脚本崩了→改脚本→再崩」。

**哪些脚本一定得改**：凡是内含书名/章节名常量或依赖特定块类型的（`align_marks_notes` 的章节名表、`reflow_inserts` 的术语表排除规则、`check_end_matter_and_loss` 的「快速测验/复习题」小节名），换书必须改常量——它们的**算法**通用，**常量**不通。

## 形态开关表

**判型只问数据特征，不问「像哪本书」。** 探型阶段把这 8 个开关填完，然后只读对应机制篇，直接进「主线」。

| 开关 | 取值 | 判定依据（可验证） | 打开 |
|---|---|---|---|
| **S1 公式** | 无 / MathML / 裁图 | `interline_equation` 块数（0、数十、数百）；span 是否带 `image_path`（有=可裁图，无=只能 MathML） | M5 |
| **S2 注释体系** | 无 / 页脚圈码 / 章末数字 / 星号译注 / 尾注另册 | `discarded page_footnote` 块数；书末是否有「译注/注释/附注」章；正文标记形态（圈码 / `^{N}` / `*`） | M3 |
| **S3 注释重编粒度** | 每页 / 每章 / 每节 | 同一标记是否在相邻页重复出现（逐页打印 `body marks` vs `note marks` 序列即知） | M3 |
| **S4 表格** | 无 / grid / HTML 双栏 | `table` 块 span 是否含 `<table>`；有无 `table_body` 子块；页内左右块数是否双栏 | M5 |
| **S5 插图** | 无 / 少量插页 / 图组 / 图在别处 | `image`/`chart` 块数；`image_caption` 子块是否存在；图文件是否在本机（只有哈希名=不在） | M4 |
| **S6 结构** | § 结构 / 章-节 / 多级子标题 / title 自带 level | `title` 块形态：`§N`、`第N章`+`第N节`、`A./a./α)`、`level` 字段 | M7 |
| **S7 附属** | 索引 / 参考书目 / 术语表 / 答案 / 无 | 书末章节标记命中；`ref_text` 块占比 | M7 |
| **S8 多文件** | 单文件 / 多册合订 / 跨册（注释在另一册） | JSON 个数与页数切分；注释章是否落在另一个 JSON | M1 |

**两个开关的判错代价最大**：S3 判错（每页 vs 每章）会让整套注释错位；S2 漏掉第二套注释（本书常有「页脚圈码 + 章末数字」并存）会让缺口互相掩盖。先跑 `scripts/diag_two_note_systems.py` 再动手。

## 主线（唯一流程）

```
① 探型    页数 / 块类型统计 / 注释标记分布 / 噪声形态 → 填 §4 开关表
② extract layout.json → pages.json（噪声过滤、标记归一、公式占位、来源页戳）
③ build   pages.json → book.md（跨页合并、状态机分章、注释建链、图组归位）
④ pandoc  book.md → raw.epub → 注入封面/元数据 → final.epub
⑤ 校验    保真度比值 / 注释对齐 / epubcheck + 链接 → 交付
```

- 中间产物全部落盘，**每一步都能单独重跑**；改了 extract 必须重跑 extract，只跑 build 用的是旧 pages.json（改动静默无效）
- 所有变体都是这条线上的开关组合，**没有第二条主线**
- 跨页段落合并：页末块以非终止标点结尾 → 续接（TERMINAL 正则 `[。！？….!?]["」』”’)\]]*$`）；细节与陷阱见 M2
- 段落合并只能在**页边界**做，页内各块本就是独立段落（按「前块无终止标点」合并会把相邻两段粘成一段：某案例 3750 段 vs 修正后 4072 段）
- 修复必须进 build 脚本：直接改 book.md 会被重新生成覆盖，用 `fix_text()` / `TEXT_FIXES` 统一处理已知缺陷
- **build 之后的后处理链要固化成一张清单**（每次改任何一环都从头跑）：`build.py → fix_marks.py（补残留裸数字上标）→ fix_backlinks.py（补 ↩）→ merge_cont.py（合并跨页续表）→ pandoc → meta.py（元数据）→ fix_epub_links.py（跨文件锚点）→ validate_epub.py + epubcheck`。跳环顺序或只跑其中一段，会出现「注释有落点无回链」「续表合了但锚点没修」这类半成品；`fix_backlinks` 之所以必须存在，是因为 `fix_marks` 在 build 之后才插入的落点不会回写 `refs_seen`。

**语义归属必须自己读原文判断，不能用脚本推断**（用户多次强调：引文段落 vs 作者分析段、图题归属、插图插入位置、索引层级都属于这一类）。做法固定为三步：脚本只负责**导出候选 + 上下文**（能缩范围，不能下结论）→ 读完全部候选后把结论写成**显式清单**（段首指纹 / 坐标 / 条目）→ 代码只按清单执行。**清单是唯一真相源，不要留任何语义启发式与它并存**——并存时启发式会覆盖人工结论（某次因此把作者段落吞进引用块，用户直接要求撤回整版）。

**批量判读交给并行 subagent 时，必须先剥掉已有标记**：带着「哪些已经是答案」的暗示去读，模型只会核对旧结论、不会找漏判（实测同一批章节，含标记版报 0 处漏判，剥标记重派后补出 20 余段）。

**批次按篇幅切，不按篇切**：subagent 单次 600 秒硬超时，超时不返回 summary，但**已改的文件已落盘**——既不能当「没做」，也不能采信「已完成」的自述，一律重跑字符级比对 + 读 diff 复核（实测 10 个 agent 里 7 个超时，其中 1 个把一处的跨图断句改坏了半句）。容量参考：8–16 个小文件（≈20–40 K 字）一批能跑完；一整章 90 K 字 / 1131 个公式必超时。派活时写死：只改分配到的文件、临时脚本只写 `/tmp/<task>/`（有 agent 往项目目录写 `check.py`，覆盖了旧 pipeline 的文件）。

## 机制篇索引（M2/M8/M9 必读，其余按开关加载）

**读法**：M2 / M8 / M9 是**主线必读**（每一步都要用到）；其余按「形态开关表」的「打开」列命中才读；M6、M10 只在书里有引文排版需求 / 需要外部参照时读。

| 篇 | 读法 | 什么时候读 | 条目 |
|---|---|---|---|
| M1 `mechanisms/inputs.md` | S8 多文件 / 有外部协作 | 多个 JSON、分卷 zip、超大附件、图片包、要先发图片清单 | 14 |
| M2 `mechanisms/page-break-merge.md` | **必读** | 页末半句 + 下页半句被切成两段；改动了任何合并逻辑 | 24 |
| M3 `mechanisms/notes.md` | S2 / S3 有注释 | 书里有任何注释形式，或上标与注释条目对不上 | 89 |
| M4 `mechanisms/figures.md` | S5 有插图 | 有插图/图组/图目录，或图题位置不对、丢题注、插页切断正文 | 56 |
| M5 `mechanisms/tables-math.md` | S1 / S4 有公式或表格 | 有表格（HTML/双栏/rowspan）或公式（MathML/裁图/散落 LaTeX） | 58 |
| M6 `mechanisms/quotes.md` | 需引文排版时 | 要把整段转引原文排成引用格式 | 7 |
| M7 `mechanisms/structure-noise.md` | S6 / S7 或任何页眉噪声 | 页眉页脚边注混进正文、章节标题被误删、标题层级判错 | 46 |
| M8 `mechanisms/assembly.md` | **必读** | book.md 已就绪要出 EPUB；epubcheck 报错、锚点失效、封面不显示 | 26 |
| M9 `mechanisms/checks.md` | **必读** | 每轮 build 之后、交付之前 | 19 |
| M10 `mechanisms/external-ref.md` | 需外部参照时 | 要从扫描页读上标、对照英文原版补标记、校对德文/希腊字母 | 16 |

补充：`references/figure-caption-recovery.md` 是图题恢复的专门方法篇（四类来源穷举 + 六种错位形态），与 M4 配合读。

**篇与篇之间已做交叉索引**：每篇头部有 `## 相关篇`（该机制与哪些邻篇相交、为什么，共 35 条指针）；跨两个机制的实测结论在条目下方标 `双归属 → **Mx**`（21 条），正文只在主归属篇写一份。读到「这件事好像该在另一篇」时，先看这两个标记。

**改互链不要直接改 md**：`references/mechanisms/*.md` 是生成产物。互链表在 `scripts/mechanism_links.json`（`REL` + `DUAL`），改完跑 `python3 scripts/apply_mechanism_links.py`（幂等，可反复跑）。

## 症状 → 查哪里

| 症状 | 去查 |
|---|---|
| 页末句子被切断，下页开头半句 | M2 |
| 脚注指向错误页 | M2（来源页戳 `{{MARK:①@A30}}`） |
| 正文有上标、注释区无该条 | M3（缺口 / 占位条目） |
| 注释有条目、正文无落点 | M3（诚实边界：不硬插） |
| 页脚注文整条消失（不报错、校验全绿） | M3（注文只在有落点时才建 defs；收尾必须「源注文数 vs 成品注文数」对账） |
| 补注后 epubcheck 报 `p not allowed here` / `mismatched tag` | M3（`## 第N章` 在正文与「注释」章各出现一次，插入区必须先 `partition("\n# 注释\n")`） |
| markdown 里用 `<p class="cap">…</p>` 写段落，pandoc 把内容当 markdown 解析（`1. ` 变 `<ol>` 套进 `<p>`） | M8（改 fenced div `::: cap`，CSS 改 `div.cap p`） |
| 表格下方的表注（`table_footnote`）消失 | M5（extract 存了 `fnote`、build 忘了输出） |
| 页脚有注文、正文无标记（孤儿注）全堆在章末 | M3（先按「人名/地名/术语」回正文补位，补不上才留章末并标来源页） |
| 附录长表断成两张、残留「(续前表)」 | M2（两半首行结构相似度 ≥0.9 才合并；循环遇「不合并」别 break） |
| epubcheck 报 `element "eq" not allowed here` | M5（OCR 塞进单元格的 `<eq>^{N}</eq>` 伪标签） |
| 注释编号出现 `1,2,3,1,5` | M3（按出现顺序重编号） |
| 两套注释的缺口互相掩盖 | M3（先跑 `diag_two_note_systems.py`） |
| 译注整章为空 | M3（`ref_text` 独立块类型 / 译注落在 `table` 块里） |
| 图没有标题 | M4（`chart_caption`，不是 `image_caption`） |
| 图题跑到图前面 | M4（挂起图题，按固定输出顺序） |
| 图注只有第一段有格式，后面几段变正文 | M4（`split_cap` 拆出的续段走回 `para`；全段统一 `<p class="cap">`） |
| 插入物前后多出横线／要求去掉分隔线 | M4（分隔线是开关，不是硬规则；定口径后全书一致） |
| 图题整条消失 | M4（掉进 `discarded_blocks`，必须专门扫一遍） |
| 面板标签张冠李戴 | M4（按坐标归属，不按字符串排序） |
| 插图切断正文 | M4（插入组整体搬 + 上下 `---`） |
| 反解时把「图切断正文」当成源缺 | `references/epub-to-markdown.md`（回查 `pages/`+`raw/` 的下一页首块，别只信 `book.md`） |
| 表格整个消失 | M5（HTML 在 `table_body` 子块里） |
| 表格首列重复 | M5（`rowspan` 展开；改源 HTML 加 colspan，别改渲染器） |
| 表格列错位 / pandoc 拆坏 | M5（列宽按显示宽度算，中文当 2 列） |
| 公式渲染成一坨 TeX | M5（`clean_tex` 必须走所有公式输出路径） |
| 引用块吞了作者的话 | M6 |
| 竖排书名混进正文 | M7 |
| 章节标题消失 | M7（`FORCE_START`；章节标记必须在宽度过滤之前判） |
| 标题层级错（章跑到篇同级） | M7（`#`=篇、`##`=章、`###`=节） |
| 索引层级还原不了 | M7（如实交付，只保文字） |
| epubcheck 报 `@refines missing target id` | M8（改写 dc 标签必须保留原 id 属性） |
| epubcheck 报封面图找不到 | M8（`cover.xhtml` 里写 `../cover.jpg`） |
| 内部链接全失效 | M8（拆章后跨文件锚点，跑 `fix_epub_links.py`） |
| 保真度比值异常 | M9（>1.01 查重复渲染，<0.97 才查丢块） |
| 正文有圈码、该页页脚无此注文 | M3（先查章内序列空缺：很可能是数字注号被读成圈码；**别急着插同号**） |
| **校验全绿但成品是错的** | M9（解包抽读 xhtml） |
| 注释序列 `1..N` 严格递增、链接全通，但个别落点明显挂错了句子 | M3（缺号被"另插同号"补圆；`insert` 必须逐条回注文语义复核，说明里标明哪几条是补的） |
| 圈码改判成注号后整章序列错位一格（`…55, 57, 58, 38, 60…`） | M3（改判必须排在章内重编号之后：renumber → 改判 → drop → insert） |

## 交付清单（不可协商项）

- 文件名带**版本 + 时间戳**（`…-v5-10281606.epub`）；报 **md5 + 字节数**
- 同步 `/tmp` 副本（用户通过 Telegram 下载走 /tmp 路径；旧副本会导致「格式乱了」的误报）
- 制作说明写清：**识别口径 + 排除了哪几类各多少处 + 缺口清单**
- **页码口径必须写明，且两套分开写**：说明文档里一律用「书 pN」= 印刷页码（与页面上的页码、原书目录一致）；工作区定位用「A p25」= layout.json 的 `page_idx`（从 0 起）。两者差一个各册不同的偏移，交付时给出偏移公式（某四册合订本：A `pageno = pi − 14`、B `+186`、D `+386`、C `+586`）。混用会让用户直接问「你的这些 p 是原书的还是 pdf 的」。
- **缺口清单粒度到「页 + 原句 + 注文摘要」**：每条缺口写「印刷页 · 原句片段 · 对应注文首句」，只报「缺 3 处」会被要求「具体告诉我」。同时区分三类：① 上标整处丢失（源数据没有任何残留）；② 页脚有注文、正文无标记；③ 源数据里就没有该条注文。
- **排版开关要在开工时定下来并全书一致**：插入组（图/表）是否上下加 `---` 分隔线、图注用哪种样式——同一本军事史/图册型书用户要的是**不加分隔线**（原话「本书的插入的东西不需要分隔线隔开」），而早期教科书要求加。不要照抄旧案例的默认值；定下后交付前解包验一次（`<hr>` 计数、`class="cap"` 段数 ≥ 有题图数）。
- 源数据缺陷只占位不猜（`〔源数据缺该条注释：…〕`），逐条列出
- `epubcheck` 0 error / 0 warning + 内部链接全通 + 双向脚注数相等（noteref ↔ backlink）
- **解包抽读 2–3 处表格 / 公式 / 引用块的 xhtml** —— 校验全绿 ≠ 渲染正确
- 同名附件反复交付时换新文件名；用户会打开旧版并认为没修

## 案例库索引（只看差异清单，不复用阈值）

| 案例 | 形态 |
|---|---|
| `hegel-encyclopedia-case.md` | 黑格尔《哲学科学百科全书I 逻辑学》§1-244：§ 结构 + 说明/附释类型状态机 + 德文术语校对 |
| `houlgate-introduction-case.md` | 霍尔盖特《黑格尔导论》三部分合并：章末注释制、`ref_text` 误分类、索引 table 块 |
| `zhang-shiying-yizhu-case.md` | 张世英《小逻辑绎注》：逐节讲解 + 圈码注每节重编、裸圈码=丢失上标、节末+页脚双体系 |
| `zhang-shiying-yizhu-repair-session.md` | 同书标记修复实录（213→0 不匹配，约 30 节 fixes.json 明细） |
| `zhang-shiying-yizhu-epub-phase.md` | 同书 EPUB 阶段（严格递增校验 + 重编号、全局唯一锚点） |
| `zhang-shiying-yizhu-paragraph-fix.md` | 同书分段修复实录（跨页断行 100+ 处、book.md 后处理为何不可行） |
| `ordeal-by-fire-case.md` | 《火的考验》三册合订：页脚星号译注 + 书末附注尾注两套体系、跨册合订 |
| `mankiw-macroeconomics-case.md` | 曼昆《宏观经济学》第10版三文件合订 |
| `mankiw-macroeconomics-11e-case.md` | 同书第11版：用户改要**可复制 MathML**、页脚不带章名、双栏阈值按页宽换算 |
| `varian-microeconomics-case.md` | 范里安《微观经济学：现代观点》第九版三部分合并 |
| `marx-math-econ-case.md` | 《马克思经济学与数理分析》双文件：全书 MathML、单反斜杠 LaTeX、索引跨 5 页 |
| `sweezy-capitalist-development-case.md` | 斯威齐《资本主义发展论》三册合订：`table_body` 子块藏 HTML 导致表全丢 |
| `micro-theory-11e-case.md` | 斯奈德《微观经济理论》第11版四册：圈码页脚注**按章连续**编号、脚注编号必须懒分配 |
| `samuelson-economics-19e-case.md` | 萨缪尔森《经济学》第19版：`title` 自带 `level`、图题大量掉进 discarded |
| `harvey-limits-to-capital-case.md` | 哈维《资本的限度》：**页脚圈码 + 章末「译注」数字**双体系、译注整章落在 `table` 块里、引文段落判定四轮演进 |
| `scan-superscript-reading.md` | 方法记录：从原扫描页读回被 OCR 整处丢掉的上标（非单本书案例） |
| `glantz-titans-clashed-case.md` | 格兰茨/豪斯《巨人的碰撞》修订扩充版：四册按页码+书目字母序定序、章标题块类型三种形态（以目录为准）、篇分隔页只在目录里、注释章藏表、地图图题是独立 text 块、附录表 `<eq>` 伪标签 |
| `figure-caption-recovery.md` | 方法记录：图题/表题恢复的四类来源与六种错位（与 M4 配合读） |
| `defeat-to-victory-case.md` | C.J.迪克《从失败到胜利》两册相接：章末数字注 223 条 + 页脚圈码译注 11 条、**3 处圈码实为数字注号**（序列校验全绿也不代表落点正确）、表注与「被甩到页脚的正文」同块类型、章名缺「第N章」前缀、注释区内混 title 块、地图图题印在图内靠 vision 读、`<eq>1^{2}</eq>` 要保留前导数字 |

## 本技能的结构与维护

三层：本文件（入口：开关表 + 主线 + 症状表 + 交付清单）→ `references/mechanisms/`（按**机制**，10 篇）→ `references/*-case.md`（按**书**，14 篇）。

- **新学到的东西先判归属**：换本书还会踩 → 追加到对应机制篇末尾；只在某本书成立 → 进该书 case。**不要往本文件加机制细节**——它曾因 9 个「变体」各复述一遍同一机制膨胀到 85 K 字符（跨页合并被写了 16 遍）
- **改完结构必跑** `scripts/verify_skill_migration.py <旧SKILL.md> <技能目录>`：抽出旧版全部行首加粗结论逐条比对，**0 丢失**才算完成（上一次基线：298 条结论 / 392 条条目，含 35 条互链指针 + 21 条双归属标记）
- **一条结论可能双归属**（例「合并后圈码标记挂到错误页底注」＝跨页合并的连带故障 + 注释配对）：放主归属那篇，另一篇加一行 `双归属 → **Mx**（原因）` 指针，不要两处各写一份
- **改开关表要复查「必读篇」**：M2 / M8 / M9 是主线必经，不由任何开关决定，必须无条件读
- **大改结构前先给骨架提案**（分层方案 + 体积预估 + 防漏办法），用户确认后再动手——用户明确要求过「先做一份新骨架给你看」

组织理由、重构方法、**脚本可移植性审计（哪 10 个可直接跑 / 哪 6 个需改常量）**、改完回归与 GitHub 发布流程见 `references/skill-structure.md`。

**换项目先做一次脚本审计**：拿新书的数据把 `scripts/` 全跑一遍，别默认它们能用——技能自带的脚本默认绑定某个项目的中间层 schema 与章节名常量。审计结论与两个已知假警报/崩溃形态见该文件。

**再次大改本技能结构时**（合并/拆分机制篇、再压缩入口），先读 `skill-library-maintenance` 技能：量三个数 → 骨架提案 → 逐字搬运 → `verify_skill_migration.py` 机械防漏 → 互链进 JSON。那次 85 K → 7 K 的重构就是按它做的。

## EPUB 标准结构规范（跨管线通用）

格式层细节（章节拆分/标识、双向脚注写法、mimetype/container.xml/content.opf、EPUB2 vs EPUB3、踩坑清单）见 `web-to-epub` 技能的 `references/epub-internal-structure.md`。
