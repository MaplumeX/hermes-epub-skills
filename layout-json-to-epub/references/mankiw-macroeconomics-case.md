# 案例：曼昆《宏观经济学》第十版（中译本）layout.json → EPUB

（已交付：`/tmp/宏观经济学（第十版）.epub`，10.1 MB，epubcheck 5.1.0 0 错 0 警）

## 源文件（2026-10，用户一次上传三份 layout.json + 后补一份分卷图片包）
| tag | 文件 | 页数 | 覆盖 |
|---|---|---|---|
| A | doc_669cad964a58_layout.json (8.0 MB) | 200 | 封面/总序/序言/目录 + p1–180（第1–8章） |
| M | doc_eec5fe84b722_layout.json (9.4 MB) | 200 | p181–380（第8章末–第17章前） |
| B | doc_36512a8a810f_layout.json (3.3 MB) | 79 | p381–454（第17–19章、结束语、术语表、译后记） |

**注意：这是 3 份而不是 2 份。** 用户同一时刻上传，Telegram 只把其中两份写进消息正文，第三份（`doc_eec5fe84b722`）在 `~/.hermes/cache/documents/` 里但没出现在 prompt 里——**收到多份 layout.json 时先 `ls -lt ~/.hermes/cache/documents/` 按 mtime 找同批文件**，否则会把中间 200 页整段丢掉。

## 结构
- 页脚章名是唯一可靠章边界：`第 N 章 XXX`（可带页码后缀 `第2章 宏观经济学的数据 15`）；另有 `序言`/`辅助材料和媒介`/`术语表`/`译后记`/`结束语` 前缀页脚（译后记页脚是作者名 `卢远瞩`）
- 篇分隔页：只有 1–4 块（竖排篇名 text + `第N篇` title），页眉是 `第N篇`
- 页眉只在章首页/分隔页出现，且会混入正文续句（`于国外产品变得较便宜了。`、`方面提供了见解。`）
- 页脚注：discarded `page_footnote`（多为文献引证）+ preproc 里 y>380 的 `① 数学注释：…` 块 + **discarded `footer` 里的 `① Robert J. Barro, …`**（三处都在用）
- 每页脚注从 ① 重新编号，正文里是裸圈码字符（不是 `^{}`）
- 术语表 p443–453 是双栏（左 x1≈302 / 右 x0≈316），词条格式 `中文（English）释义` → 用 `re.sub(r'^([^（）]{1,40}（[^（）]{1,60}）)', r'**\1**', t, 1)` 加粗词头
- 表格 span 带 raw `html`（含 rowspan，表题常塞在首列并跨行重复）；图/表块只有 `image_path` 哈希名

## 管线
`/root/mankiw_macro/`：`extract.py` → `pages.json` → `build.py` → `book.md` → pandoc → `epub_build/out.epub` → `add_metadata.py` → `epub_build/final.epub`

- extract 输出 `{file,pi,pageno,chapter_no,chapter_name,part,two_col,items,footnotes}`；text 里的 `inline_equation` span 转成 `$...$` / 裸圈码 / `<sup>N</sup>`
- 跳过页：A 的 {0,1,2,4}（封面/扉页/编委会/空白）+ {14..20}（原书目录，EPUB 用 `--toc` 重建）；B 的 {77,78}（封底杂图）
- build：标题分级（`x.y` → `##`、`附录` → `##`、`第N篇` → `#`、其余短 title → `###`）、`图/表 X-Y` 题注、HTML 表格 → pandoc grid table、脚注 `[^p{页}-{序}]`
- pandoc：`--mathml --toc --toc-depth=3 --epub-chapter-level=2 --resource-path=. --metadata lang=zh-CN`（`--toc-depth=2` 只出两层，`####` 不进目录；`--split-level` 在 pandoc 2.17 不存在）

## 关键决策：公式用裁切图，不用 OCR 的 LaTeX
`interline_equation` 的 span 同时有 `content`（OCR LaTeX）和 `image_path`（原公式裁图，1×1 px 占位头 + 真实 199×37 之类）。OCR 版错误清单（实测）：`2 0 1 7` 数字被空格拆开、`\alpha`→`a`、`L`→`I _ {L}`、`72\%`→`72\\%`。
→ **有图就用图**：build 的 interline_equation 分支 `src = img(it.get('figs'))`，有则 `![](images/<hash>.jpg)`，无则 `$$...$$`。代价：公式不可复制/不可重排，需向用户说明。本书 358 个公式全部走裁图。
（extract.py 的 interline_equation 分支必须把 `figs = fig_paths(b)` 一起带出，否则 build 拿不到。）

## 图片包（第二轮用户补发，5 卷分卷 zip）
- 用户发 `images.z01..z04 + images.zip`（各 5 MB / 尾卷 2.6 MB）。`cat` 合并后 `unzip` 三种报错：`extra bytes at beginning`、`bad zipfile offset`、`invalid zip file with overlapped components (possible zip bomb)`
- 正解：保留原卷名同目录，`7z x -y -oout images.zip` → 634 图，`Everything is Ok`
- 交叉核对：layout.json 里唯一 `image_path` 634 个 = 解压文件数 634，**missing 0 / unused 0**（这个双向核对一定要做，能立刻发现卷缺/图错配）
- 体积：原图 25 MB（image 11.9 + table 5.5 + chart 5.2 + 公式 1.5）。`ffmpeg -vf "scale='min(900,iw)':-2" -q:v 6`（输出名必须带 `.jpg`）→ 9.9 MB → EPUB 10.1 MB
- 只压 book.md 里实际引用的 575 张（86 张 image 里 11 张是竖排篇名装饰条/重复图，不必进）

## 实测数据（成品基线，含标题层级修正后）
- 466 页；**12 个 `#`**（总序/序言/辅助材料和媒介/5 篇/结束语/术语表/译后记/宏观经济学的八个重要变量）、**57 个 `##`**（篇下 19 章 + 前置章节的小节）、**92 个 `###`**（`x.y` 小节）、**419 个 `####`**（案例研究/参考资料/小标题）
- 575 张图（358 公式裁图 + 217 图表）、47 张表、141 条脚注双向链接（noteref/backlink 141/141）
- 内部链接 517 条 0 失效；重复 id 0；epubcheck 0 错 0 警；TOC 162 条（三层）
- 源非空白字符 482,864 vs md 481,755 → 0.998（保真）

## 标题层级：用户第二轮纠正「章不是应该在篇下吗」
第一版把所有章都做成 `#`（与篇同级），用户立刻指出层级错。正确结构：

| 层 | 内容 | 例 |
|---|---|---|
| `#` | 篇 / 前置与后置章节 | 第1篇 导言、序言、结束语、术语表、译后记 |
| `##` | 篇下的章；前置章节的小节 | 第1章 宏观经济学科学；序言里的「本书的方法」 |
| `###` | `x.y` 小节 | 1.1 宏观经济学家研究什么？ |
| `####` | 小节内小标题 | 案例研究、参考资料、生产要素 |

实现与两个坑：
1. `ch_level = 2 if (cur_part and isinstance(ch, int)) else 1`，无篇的 front matter 章保持 h1、其小节 `off=1`，有篇的章 `off=2`。
2. **第一次改完仍错**：`ch` 来自本页页脚，页脚漏识别的页 `chapter_no is None` → `ch_level` 退回 1，同一章里出现 h1/h2 混排（`1.1` 是 `###` 而 `1.3` 是 `##`）。修正：`eff_ch = ch if ch is not None else cur_chapter` 再算层级。
3. 特殊项：「启示 2/3」降到 h3（挂「四个启示」下）；「宏观经济学的八个重要变量」单独升 `#`。
4. pandoc 参数随之改为 `--toc-depth=3 --epub-chapter-level=2`；自查用 `grep '^#\{1,2\} ' book.md` 打层级树——**TOC 条数对不代表嵌套对**。

（交付后 md5 `7e4095c8…`，10.6 MB，epubcheck 0/0/0。）

## 收尾仍存在的已知瑕疵（已向用户声明，未硬编）
1. 约 11 张图的题注是 OCR 单独成行的，排在图下；其余图题已烘焙在图内
2. 章末「复习题/问题与应用」个别双栏页条目顺序按左右栏排（1、3、2、4），文字没少
3. 双栏串栏碎片（孤立 `稳定性？`）直接丢弃 → 极少数句子尾部缺失（原书该句在上栏已被截断）

## 值得记住的坑
- 三份文件章名空格不一致（`第 11 章 总需求 I：…` / `第11章 总需求I：…`）→ 按章号取众数，否则重复出章标题
- `\begin{array}{r l}` 的修正只加在 text 分支、独立公式分支漏了 → pandoc 只给 WARNING 并把公式退化成 TeX 源码，`validate_epub.py` 仍全绿（MathML 只统计成功的），**必须看 pandoc stderr**
- 页脚把 14.1 算进第 13 章 → 小节号整数部分与当前章不符时补发章标题（见 SKILL.md）
- 段落合并只在页边界（`mergeable=first_in_page`）：页内合并把快速测验的 A./B./C. 选项、复习题条目全吞进一段
- 页脚噪声会粘在正文块尾部（`22. 宏观经济学（第十版）`、`204 宏观经济学（第十版）`、`续前表`）→ fix_text 里按行尾正则清，并单独 skip 整块就是 `宏观经济学（第十版）` 的 title
- 正文里 `F(zK,zL)=zAK^{a}I_{L}^{1-a}` 这类 OCR 错号用 FIXES 表定点替换（`a`→`\alpha`、`I_{L}`→`L`），不要全局替换 `a`
