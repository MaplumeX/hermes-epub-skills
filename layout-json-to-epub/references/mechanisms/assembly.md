# M8 EPUB 组装（pandoc、锚点、封面、元数据）

> **什么时候读**：book.md 已就绪，要出 EPUB；或 epubcheck 报错、锚点失效、封面不显示时。
>
> **相关脚本**：`scripts/fix_epub_links.py`、`scripts/validate_epub.py`

> 本篇内容自 SKILL.md 拆出，条目逐字保留（含实测数字与原节出处）。

## 相关篇

> 一条结论常跨两个机制：**正文只在主归属那篇写一份**，这里只放指针。

- **M3** —— 双向脚注锚点与跨文件修正
- **M7** —— `#`/`##`/`###` 层级与 `--toc-depth` 的配合
- **M9** —— epubcheck 通过后仍要抽读 xhtml
- **M1** —— 成品体积与 Telegram 20 MB 上限

## 来自「教科书（MathML 公式 + HTML 表格 + 页面圈码脚注 + 缺失插图）」

- **pandoc 默认 EPUB CSS 没有 `img` 规则**：900px 宽的插图在手机上溢出 → 注入 `img { max-width:100%; height:auto; }` + `p > img { display:block; margin:.8em auto; }`

## 来自「中译本学术专著·双注释体系（页脚圈码 + 章末「译注」数字） / 收尾阶段实测（第二…」

- **注入封面的三个 epubcheck 硬错（本会话一次踩齐）**：① `ERROR(RSC-005): @refines missing target id: "epub-creator-1"` —— pandoc 已生成 `<meta refines="#epub-creator-1" property="role">aut</meta>`，改写 `<dc:creator>` 时用 `re.sub(r'<dc:creator[^>]*>.*?</dc:creator>', …)` 会把 pandoc 给的 `id` 属性一起吃掉 → 替换时必须**保留原属性**（`<dc:creator%s>` 回填 `m.group(1)`）；② 见上条 nav mathml；③ `ERROR(RSC-007): Referenced resource "EPUB/text/cover.jpg" could not be found` —— `cover.xhtml` 放在 `EPUB/text/` 下，图片引用要写 `../cover.jpg`，写成 `cover.jpg` 就指到 text/ 目录里。

## 来自「尾注（附注）制 + 跨册合订（本册无注释文本）」

- **每册的脚注/锚点 id 必须带册别 tag**：无页号的页用 `pi` 兜底会与另一册撞号（`build.py <pages> <out.md> [tag]`）；`FIXES`/`NOTE_MARK_OVERRIDE` 这类按印刷页码的修正表，**只在 `page['pageno']` 精确相等时应用**，否则退化到 pi 会跨册误命中。

## 来自「学术专著（全书 MathML + HTML 表格 + 页脚圈码脚注 + 图目录/索引…」

- **pandoc 2.17 没有 `--epub-title-page`**（报 `Unknown option`，exit 2、EPUB 根本不生成）；要去掉自动标题页就 post-process 删 `title_page.xhtml`，或留着当扉页
- **双向脚注直接用 pandoc 原生**：正文 `[^p1-22-1]`（`file-pi-seq`），定义集中在文末；`validate_epub.py` 报 `noteref 74 / backlink 74 OK` 即通过。不需要手写 `<a id>` 锚点（那是尾注/拆章场景的方案）

## 来自「中译本学术专著（页脚圈码脚注 + MathML 公式 + HTML 表格 + 少量插…」

- **`Could not load translations for zh-CN` / `The term Abstract has no translation defined` 是 pandoc 2.17 良性噪声**，可忽略
- **豆瓣 `subject_suggest` 可能只返回带书脊的立体展示图**（800×800）：仍可用，但交付时说明「不是平面书影」；先用 `vision_analyze` 确认是不是真封面
- **交付前跑 epubcheck**（本机 `/root/epub_work/epubcheck-5.1.0/epubcheck.jar`，有就用）：`java -jar epubcheck.jar out.epub`，0 errors 0 warnings 才算过；比自写校验更权威

## 来自「中译本教科书·多分册（圈码页脚注按**章**连续编号 + 答案/术语表双栏 + 图组…」

- **epubcheck 报 `OPF-014: The property "mathml" should be declared in the OPF file` 时**：pandoc 只给 `text/*.xhtml` 加 `properties="mathml"`，导航标题含公式时 nav 也需要 → 把 `<item id="nav" … properties="nav"` 改成 `properties="nav mathml"`。**但这条按 epubcheck 版本分裂（本会话实测）**：epubcheck 5.1.0 / EPUB 3.3 下给 nav 加 mathml 反而报 `ERROR(OPF-015): The property "mathml" should not be declared in the OPF file`。所以注入脚本默认**不要**加；只有 epubcheck 明确报 OPF-014 指向 nav 时才加，且加完立刻重跑 epubcheck 确认不是反向报错
- **豆瓣取封面必须带版次关键词**：只搜书名会返回别的版次/别的书（本案例搜 `微观经济理论` → 2005 版 + 2024 版，都不对）；`subject_suggest?q=微观经济理论 第11版` 才命中正确条目。拿到 `pic` 把 `/s/` 换 `/l/`、带 `Referer` 下载，再 `vision_analyze` 确认是平面书影还是 3D 展示图（本案例是 3D 立体图，交付时要说明）

## 来自「中译本教科书·单册拆多文件（`title` 自带 level + 图题被拆散 + 书…」

- **`dc:date` 只能有一个**：pandoc 已生成 `<dc:date id="epub-date">`，注入出版年要用 `re.sub` **替换**而不是再插一条，否则 epubcheck 报 `element "dc:date" not allowed here`

## 来自「中译本教科书·单册拆多文件（`title` 自带 level + 图题被拆散 + 书…」

- **豆瓣封面**：`subject_suggest?q=经济学` 命中「经济学 (第19版)」id 25922243，但图是 3D 立体书影；同页其他 `s5757950.jpg` 是别的书（《经济分析基础》）。**必须 `vision_analyze` 确认书名与平面/立体**再交付

## 来自「陷阱」

- **交付前必须同步 /tmp 副本**：重新生成 EPUB 后 `cp` 到 /tmp 并 md5sum 对比；用户通过 Telegram 下载的是 /tmp 路径，旧副本会导致用户看到旧格式并误报"格式乱了/换行没了"（本会话两次因此误报）；**改了 extract.py 必须重跑 extract.py 重建 pages.json**——只跑 build.py 用的是旧 pages.json，改动静默无效，交付出去还是旧内容
- **文件过大投诉：先看字节数再下结论（本会话教训）**：Telegram 机器人收发上限 **20 MB**。用户上传超限时平台回执会作为**入站消息**转给 agent（"The document is too large or its size could not be verified. Maximum: 20 MB."），gateway.log 同时记 `[Telegram] Document too large: <bytes>`。**先拿日志里的字节数跟自己发出去的/对方声称的文件大小比对**——本例 115,269,237 字节显然是用户那个 zip 被拒，不是自己 841 KB 的 EPUB 投递失败（曾误判成"中文/全角文件名导致投递失败"并白白换名重发一次）。用户说"文件已发给你"而 `~/.hermes/cache/documents/` 里没有新文件时，先查 `grep 'Document too large' ~/.hermes/logs/gateway.log` 再回复，别让对方重复上传
  - 双归属 → **M1**（附件与体积属于输入协作）
- **`<br>` 必须写成自闭合 `<br/>`**：markdown 里的裸 HTML `<br>` 会被 pandoc 原样输出到 XHTML，`xml.etree` 解析报 mismatched tag（EPUB 校验才暴露，pandoc exit 0）。诗行/署名行分组时尤其容易踩。
- **raw HTML 表格内的脚注要用 HTML 锚点**：pandoc 不解析 raw HTML 里的 markdown（表格单元格里的 `[^id]` 不会生效）→ 星号表注写成 `<a href="#tn{页}-{i}"><sup>&#42;</sup></a>` + 表后 `<a id="tn{页}-{i}"></a>` 注释行；同一条注被两格引用时**复用第一个锚点**并只输出一次注文。
- **pandoc 块识别需要空行**：`**§ N**` 标题、`> **说明**` 引用块、`#` 标题前后都必须有空行，否则 pandoc 把它们并进前一段，渲染成字面文本（`&gt;`）或整段粘连——render 函数里每个段落/标题后都要 append('')
- **pandoc 段落开头数字+点 → 有序列表**：段落以 `2. ` 开头会被解析为 `<ol>`，且段内 `(a) (b)` 子项会嵌套列表导致标签不匹配（XML 校验报 mismatched tag）。修复：render 时 `re.sub(r'^(\d+)\.\s', r'\1\\. ', text)` 转义
- **EPUB 双向跳转脚注（用户要求，勿只输出死文本上标）**：用户问"脚注注释没配置？"说明上标必须是**可点击链接**，不是纯 `<sup>` 文本：
  - 双归属 → **M3**（锚点命名与配对规则在 M3）
  - **markdown 阶段生成锚点链接**（mdgen.py）：
    - 正文数字标记：`<a id="chN-ref-M" href="#chN-note-M"><sup>M</sup></a>`（id 是返回锚点）
    - 正文星号译注：`<a href="#chN-tr"><sup>★</sup></a>`（本章译注区）
    - 章末注释：`<a id="chN-note-M"></a><sup>M</sup> 文本 <a href="#chN-ref-M">↩</a>`（↩ 返回正文）
    - 译注区标题：`#### 译注<a id="chN-tr"></a>`
    - 导言（ch0）正文无标记 → 注释不加 ↩（避免死链）
  - **必须 `--epub-chapter-level=2`**（pandoc 2.17 用 `--epub-chapter-level`，不是 `--split-level`）：不拆章则正文+注释全在一个大 xhtml，锚点反而有效但文件巨大；拆章后跨文件锚点需要 post-process
  - **跨文件锚点修正脚本**（pandoc 拆章后同一文件内锚点变跨文件）：解包 → 建 `id → 文件` 映射 → 每个 xhtml 内 `href="#id"` 若目标在其他文件则改为相对路径 `posixpath.relpath(target_file, dirname(cur_file))` → 重新打包
  - **锚点命名必须全书全局唯一（第三套实测）**：节用真实节号 `s{sec}-ref-{N}`（跨章唯一），章用运行章号 `c{idx}-ref-{N}`，附录 `a-{page}-ref-{N}`。**每章重置的节索引做锚点会严重重复**（s1-ref-1 出现 6 次、s20-ref-1 4 次、c6-ref-1 2 次）。正文/注释双向链接在 markdown 阶段生成（mdlinks.py 模式）：正文 `<a id="s{sec}-ref-{N}" href="#s{sec}-note-{N}"><sup>{N}</sup></a>`、注释条目 `<a id="s{sec}-note-{N}"></a><sup>{圈码}</sup>{文本} <a href="#s{sec}-ref-{N}">↩</a>`；附录条目解析 `[页码]` 前缀，正文标记 `[[MARK:pg-N]]` 拆 page+num。生成后立即用 `Counter` 校验：重复 id == 0 且 href 目标全部存在
  - **校验路径陷阱（第三套实测）**：nav.xhtml 的 TOC 链接 `text/ch001.xhtml#标题` 相对 EPUB/ 根而非 nav 所在目录——校验时 `os.path.join(WORK, parts[0])` 失败须 fallback `os.path.join(WORK, curdir, parts[0])`，否则 TOC 全报假错（108 条 parse fail，实际 0 错）。跨文件 href 修正只改 `href="#id"` 形式的锚点，`href="file#id"` 已带路径的不动
  - **验证**：所有 `href="file#id"` 目标解析（相对当前文件目录）后存在且 id 存在；nav.xhtml 的 TOC 链接按 `EPUB/` 为基准解析；输出统计：前向链接数、返回链接数、无效链接应为 0
- **EPUB 生成后必须 XML 校验**：`xml.etree.ElementTree.fromstring` 逐个解析 xhtml/opf/ncx，mismatched tag 只有校验才能发现（pandoc 本身 exit 0 不报错）
- **pandoc 标题识别**：标题行前后必须有空行，否则不进 TOC（合并文件后要补空行）

## 来自「EPUB 元数据 + 真实封面（用户要求）」

- **封面必须用真实书影，不要程序生成**：用户明确拒绝自绘封面。豆瓣搜索 API 拿真实封面：
  - 最快路径：`curl "https://book.douban.com/j/subject_suggest?q=<书名>"` → JSON 数组，直接含 `title/url/pic/id`（pic 是 s 尺寸，把 `s` 换 `l` 拿大图）——比 subject_search 页面解析 `window.__DATA__` 简单可靠
  - 备选：`https://search.douban.com/book/subject_search?search_text=<书名>` → 页面内 `window.__DATA__` JSON（用 `json.JSONDecoder().raw_decode` 解析，尾部有截断）
  - **豆瓣图床需要 Referer**：`curl -H "Referer: https://book.douban.com/"`，否则返回 "cdn error 001"（418）
- 注入脚本（add_metadata.py 模式）：解包 EPUB → 加 `EPUB/cover.jpg` + `EPUB/text/cover.xhtml` → content.opf 加 `<item id="cover-image" ... properties="cover-image"/>` + spine 首位 `cover_xhtml` → nav.xhtml 的 `<ol class="toc">` 后插封面条目 → 重新打包
- 元数据补充：dc:creator 拆作者/译者（contributor role=trl）、dc:publisher（查豆瓣确认出版社，勿凭印象——本会话误写商务印书馆，实为人民出版社）、dc:subject、dc:description、dc:rights、dc:source
- **脚本非幂等**：对已注入的 EPUB 重跑会 assert 失败——从 pandoc 原始输出重新生成再注入
- 验证：spine 首位是 cover、nav 含封面、`properties="cover-image"` 存在、zipfile.testzip() OK
