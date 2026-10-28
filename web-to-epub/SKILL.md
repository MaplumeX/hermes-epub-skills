---
name: web-to-epub
description: Convert books into EPUB ebooks — website HTML (做epub/制作epub) or Markdown/layout.json pipelines.
platforms: [linux, macos]
---

# Web → EPUB

Turn multi-page website books (marxists.org 中文文库, online docs, text archives) into a polished EPUB: chapter TOC, footnote hyperlinks, embedded images, cover.

## Triggers

- User provides a book URL and asks to 做成epub / 制作成epub / convert to ebook
- User replies "同样" (same again) referencing a prior epub conversion
- Any multi-page book site where each chapter is one `.htm` page
- User sends a PDF OCR layout JSON (`layout.json` / `*_layout.json`) or a Markdown file and wants it turned into a clean book/EPUB
- 用户发来一个**已经做好的 .epub**,要求"优化 toc""把正文里的 1. 1.1 1.1.1 也设置成标题""目录跳转不对/不全"
  —— 这不是转格式而是**改结构**,走 `references/epub-toc-rebuild.md`,不要重写正文

## Two pipelines

| Source | Pipeline |
|--------|----------|
| Website HTML (`.htm` chapters) | ebooklib + BeautifulSoup — see Workflow below |
| Markdown / pandoc | pandoc CLI — see `references/pandoc-markdown-epub.md` (footnote-integrity verification is the critical step) |
| PDF OCR layout JSON | schema-driven extraction — see `references/layout-json-extraction.md` (footnote pairing, cross-page merging, mis-zoned footnote continuations vs. true scan gaps, missing-line marking, foreign-term proofreading via `scripts/check_terms.py`) |
| 已有 .epub 改目录/改结构(不重写正文) | unzip → 改 XML → 重新打包 —— see `references/epub-toc-rebuild.md` |

## Workflow

### 1. Recon
- `curl -sL <index>` and detect charset. Legacy Chinese sites are **GB2312** — decode with `iconv -f gb2312 -t utf-8` (fallback chain: gb2312 → gb18030 → utf-8).
- Extract page list: `grep -oP 'href="[^"]*\.htm"'`. Common shape: `00a/00b/00c.htm` front matter + `01..NN.htm` chapters + trailing 文献目录/索引 pages.
- Map filenames → chapter titles from the TOC page (`<p class='title0'>` = book title, `<p class='author'>`, `<p class='date'>`).
- Scan for images: `<img src>` plus Word-style `<page>.files/` subdirectories (formula images often numbered `image001.png`, `image002.gif`, … with gaps — collect every referenced number, don't assume contiguous).

### 2. Download
- All pages + all images. Zero-pad with `printf "%03d"` — **`seq -w` pads to 2 digits only** (`image59.png` vs `image059.png`).
- Verify downloaded images with `file` (404s return HTML error pages).

### 3. Environment
```bash
python3 -m venv epubenv && ./epubenv/bin/pip install ebooklib beautifulsoup4 pillow lxml
```
lxml is needed for verification; pillow for the cover; CJK cover font: `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc` (文泉驿正黑).

### 4. Clean + build — use the template
`templates/make_epub.py` is a complete, proven pipeline. Copy it and edit only the CONFIG block (PAGES_DIR, OUT_EPUB, CHAPTERS, metadata). It handles:

- **Legacy HTML cleanup**: breadcrumb (everything before first `<hr>`), in-page TOC tables (contain `<a href="#...">`), pager `<p>` (上一篇/回目录/下一篇), `p.title1` → `<h1>`, `h4` → `<h2>` with `id="secN"`.
- **Footnotes**: `_ftnrefN` → `<a href="#ftnN" id="ftnrefN"><sup>[N]</sup></a>`; `_ftnN` → `<a id="ftnN">[N]</a>`; footnote block (first `<a id="ftnN">` paragraph onward) wrapped in `.footnotes` div.
- **Flow-based paragraphization**: `<br>` = paragraph break; transparent containers (span/div/font/center) recurse; inline tags (a/sup/i/em/b/…) kept as **nodes**; block elements kept as-is. Rebuild body as `<p>` blocks.
- **Images**: every `<img src>` rewritten to `images/<basename>` **globally before paragraphization** (catches `<center><img>` nested inside `<p>`), all image files added to EPUB under `images/`, `style.css` has `img { max-width: 100% }`.
- **TOC**: static `toc.xhtml` (chapters + sections) AND structured `book.toc` = `[epub.Link(title page)] + [(epub.Section(title, href=file), tuple(sec_links))]`.
- **Spine**: `["nav"] + [title_page, toc_page] + chapters`.

### 5. Word-converted pages (VML formulas) — ORDER MATTERS
Formula-heavy pages converted from Word have dual copies: VML `<v:imagedata src="X.files/imageN.png">` (inside `<!--[if gte vml 1]>`) plus fallback `<img>` (inside `<![if !vml]>…<![endif]>`). `preprocess()` in the template does, in this exact order:
1. Delete `<![if !vml]>…<![endif]>` blocks (the fallback copies) — **must come first**, a generic `<![if…>…<![endif]>` regex will swallow the imagedata too.
2. Unwrap `<!--[if gte vml 1]>` so VML is exposed.
3. Convert `<v:imagedata src=…>` → `<img>` (basename src).
4. Strip remaining conditional markers (`<!--[if…>`, `<![endif]-->`, `<![if…>`, `<![endif]>`).
5. Strip `</?(?:v|o|w|st1|st2):…>` namespace tags — **with `re.DOTALL`** (they span lines).
6. Strip `v:shapes="…"` from `<img>`, `lang/style` from `<span>`, `MsoNormal` classes.

### 6. Cover
`templates/make_cover.py` — PIL, dark red `#8C1F28` + `#F5E9D0` text, wqy-zenhei font. `book.set_cover("cover.jpg", bytes)`.

### 7. Verify — run `scripts/verify_epub.py <book.epub>`
Checks: every `.xhtml/.opf/.ncx` XML-valid via lxml; every `<img src>` exists in package; no garbage residues (`\u0000`, `�`, `&lt;a id=`, `<v:`, `![if`, `msEquation`); metadata present; total body char count. Spot-check chapter first/last lines too.

## 封面素材：去网上找真实书影（而不是自己画一张）

用户说“去网上找书籍封面”时，要真的找原书扫描件，不要拿 PIL 画的红底字封面交差：

1. **先查 archive.org 的公有领域扫描件**（比图片搜索引擎可靠得多）：
   `advancedsearch.php?q=title:(...) + date:[1840-01-01 TO 1850-12-31]&output=json`。搜书名+年份区间能找到初版；
   看 `collection` 字段：`german-online-libraries` / `bavarian` ✓ 开放，`printdisabled` ✗ 处处 403。
2. **取页图**：`https://archive.org/download/<id>/page/n{0..6}_w1400.jpg`（n0=书封，印刷扉页常在 n3-n5）。
   同一本书可能有多个馆藏扫描，**全下载后拼对照图，用 vision_analyze 逐张判页型/洁净度**——单个来源可能有
   藏书章、手写号或 “Digitized by Google” 扫描水印带（水印在扫描背景上，裁掉书页边界即无）。
3. **处理封面**（PIL + numpy）：按行/列纸像素占比检测书页→裁扫描背景；再按“有墨迹行列”收紧取景；
   用**块状最大值估背景**（不用高斯模糊，否则笔画周围出白晕）做除法归一→去透印；硬阈值+“仅保留墨迹邻域”
   去掉淡印章与噪点；最后映射到暖白纸+深墨（不要纯白，屏幕上刺眼）。输出 ~1400px 宽 JPEG。
4. **每步用 vision_analyze 验**（文字是否完整、印章/透印是否清除、有无误删小号字与横线）——
   模型会直接指出“白晕/残印/留白过多”，比肉眼看更快。
5. 封面的出处要写进书名页（`封面：1845 年初版扉页（archive.org 公有领域扫描件）`）——便于用户核对。

## Pitfalls

- **ebooklib `epub3_pages` 会造假目录**：默认 True，它把正文里**任何带 `epub:type` 且有 `id` 的锚点**
  当成 EPUB2 分页（`get_pages()` 只判 `'epub:type' in elem.attrib`），于是 165 条脚注锚点会变成
  165 条 page-list 目录条目。必须 `epub.write_epub(path, book, {'epub3_pages': False})`。
- **ebooklib 写的 toc.ncx 缺 `playOrder` 且 `dtb:depth` 恒为 0**（旧阅读器据此排目录）。
  补一个后处理：按文档顺序补 `playOrder="1..N"`、把 `dtb:depth` 改成实际嵌套层数，
  再按规范重打包（mimetype 首位 + ZIP_STORED）。打包器会重写 `<?xml?>` 头，故要在**打包前**改。
- **`<br>` 未必是分段符**：先统计连写分布（`Counter(r.count('<br') for r in re.findall(r'(?:<br[^>]*>\s*)+', body))`）。
  单 `<br>` 常是标题内换行，`<br><br>` 才是分段。写死「一个 br 一段」或「连写才分段」都可能错。
- **源站未闭合内联标签会吞文**：剥标签前先跑一遍栈检查，遇到块级边界把未闭合内联标签补上闭合，
  再交给 bs4/切块器；否则一个未闭合 `<span>` 能把几千字吞进一个居中短段。
- **跨段强调标签**（`<span style="font-family:SimHei">` 跨 `<br><br>`）：段末补 `</strong>`、下段开头重开，
  否则粗体范围被阅读器吃到段末。空段也要补（否则配对错位）。
- **校订外文转录损伤时，规则里的空格要用 `[\s\u00a0]+` 匹配**：旧站常用不换行空格连接外文短语，
  写死普通空格的替换会静默不命中。应用后必须断言「实际替换数 == 清单条数」。
- **把校订当成可审计的动作**：改动只针对外文，每条都要有外文原文依据句中，原文一字不动；另出「校订记」附录，
  且终检用「源文 + 校订表 == EPUB」的双向窗口比对证明——否则用户无法区分「校订」与「篡改」。
- 校订记表格内容要 `html.escape`：依据句里会有 `<ehemaligen>` 这类尖括号，不转义 epubcheck 会报
  `RSC-005 element "…" not allowed here`。

- **交叉闭合的标题标签**（`<h4 …>…</h3>`）会让 bs4 把后续正文吞进标题（一个 h4 里塞进上千字）。
  marists 旧站有这种页面，解析前先拉直：`<h([34])([^>]*)>(.*?)</h[34]>` → `<h\1\2>\3</h\1>`。
- **`<br>` 藏在内联元素（span/font）内部**时，流式切段抓不到（整块内容变成一个段落）。
  症状：页末注释区全挤在一段里、脚注锚点一个都没生成。对策：该区块单独按 `<br>` 切行处理。
- **站点源码自带的损坏字符要原样保留**（如变元音位置被写成 `?`）——不猜补，但要在交付报告里列出来，
  否则用户会当成我们的转换失误。
- **`align` 属性在 EPUB3 里非法**（epubcheck `RSC-005`）。统一把 `align` 转成内联 `text-align`。

- **ebooklib/lxml: never put `<?xml version='1.0' encoding='utf-8'?>` in `EpubHtml.content`** — lxml raises `ValueError: Unicode strings with encoding declaration are not supported`. ebooklib writes the declaration itself.
- **ebooklib 0.20 `get_body_content()` silently swallows parse errors and returns `b''`**. When `write_epub` fails with `lxml.etree.ParserError: Document is empty`, the root cause is almost always an XML declaration in a content string — not the content itself.
- **BeautifulSoup: `p.string = html_string` escapes the HTML** (you get `&lt;a id=…&gt;`). Append parsed nodes instead: `for node in nodes: p.append(node)`.
- BeautifulSoup `html.parser` is fine for these pages; no need for lxml backend.
- Footnote sibling collection: gather the list of siblings **before** `.extract()` (extract mutates the tree).
- Don't hardcode image counts — scan the page for referenced numbers (`re.findall(r'image(\d+)\.\w+')`) and download each.
- Cover text baseline: use `draw.textbbox()` to center text; wqy-zenhei renders full CJK.
- If a chapter title differs from the TOC (`p.title1` wins), prefer the in-page title; fall back to the TOC entry for title-less pages.
- **改造别人做的 EPUB 时**:先 `cp -a src src_orig` 留底,`build` 脚本必须幂等(每次从 src_orig 重建再改),否则第二次运行就是在污染后的文件上再动一遍。
- **不要动 spine 顺序**。发现分册/章节物理顺序异常(如 初→高→中)时**先问用户**,重排 = 动 spine,风险等级完全不同。附录里的 `（一）（二）`、答案页 `Chapter N` 这类 h4 不收进目录。
- **交付报告给真实数字**(条目数、层级、链接校验结果、epubcheck 输出),不要"已优化完成"。此项用户会逐项核验。

## Files

- `templates/make_epub.py` — full pipeline template (edit CONFIG, run).
- `templates/make_cover.py` — PIL cover generator.
- `scripts/verify_epub.py` — epub validation (XML, images, garbage, metadata).
- `references/marxists-org.md` — marxists.org 中文文库 site specifics + already-converted books.
- `references/pandoc-markdown-epub.md` — pandoc Markdown→EPUB build + footnote-integrity verification (nested notes silently dropped!).
- `references/layout-json-extraction.md` — PDF OCR layout JSON → clean Markdown (footnote pairing, cross-page merging, heading inference, missing-content marking, §-scoped 正文/[说明]/[附释N] type-block state machine, missing-§-heading repair, foreign-term proofreading vs original-language source).
- `references/epub-internal-structure.md` — **EPUB 标准内部结构规范(格式层,跨管线通用)**:顶层目录/ZIP 约束、mimetype/container.xml/content.opf 解析、章节如何拆分与标识(两层目录体系 + 锚点)、脚注两种方案与严格双向跳转写法、epub:type 语义、EPUB2 vs EPUB3 差异、高频踩坑清单、验证方式。
- `scripts/check_terms.py` — verify translated-book parenthetical foreign terms against original-language text aligned by § number (usage: `check_terms.py <german.txt> <book.md>`).
- `references/epub-toc-rebuild.md` — **已有 EPUB 的导航目录重建**:把正文 h1/h2/h3(1. / 1.1 / 1.1.1)同步进 toc.ncx、补唯一 id、剥 `sigil_not_in_toc`、修书内目录页链接、EPUB2/EPUB3 取舍、epubcheck 基线对比法、重打包、可选的源文件卫生修复清单。
- `scripts/epub_toc_audit.py` — 体检任意 EPUB/解包目录:导航目标是否可解析、正文标题是否都进目录、书内目录页活链、重复 id、playOrder/dtb:depth 一致性。重建前后各跑一次。
- `scripts/epub_repack.py` — 合规重打包(mimetype 首位 + 不压缩,其余 deflate,自带自检)。
