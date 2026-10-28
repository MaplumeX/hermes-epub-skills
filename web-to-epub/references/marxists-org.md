# marxists.org 中文文库站点特征（web-to-epub 技能参考）

## 通用特征

- 页面编码 **GB2312**（`<meta http-equiv='Content-Type' content='text/html; charset=gb2312'>`）。
  解码链: gb2312 → gb18030 → utf-8。
- 目录页结构（index.htm）:
  - `<p class='title0'>` 中文书名, `<p class='author'>` 作者/译者, `<p class='date'>` 年份/出版信息
  - 章节链接 `<a href="NN.htm"><b>第X章 ...</b></a>`，小节锚点 `<a href='NN.htm#K'>`
- 正文页结构:
  - 面包屑 `<a href='../../index.html'>中文马克思主义文库</A> -&gt; ...` 到第一个 `<hr>` 为止
  - `<p class='title1'>` 章节标题
  - 章内目录 table（含 `<a href='#K'>`）
  - 小节标题 `<h4 style="text-align: center">`
  - 段落 `<br>` 分隔（无 `<p>` 包裹！必须做流式段落化）
  - 脚注: `<a name='_ftnrefN' href='#_ftnN'><sup>[N]</sup></a>` + 文末 `<a name='_ftnN' href='#_ftnrefN'>`
  - 翻页 `<p style="text-align: center; ...">上一篇 回目录 下一篇</p>`
- 文件命名: `00a/00b/00c.htm` 前言 + `01..NN.htm` 章节 + 末尾 `文献目录`/`索引` 页。

## 马恩全集单篇摘取（2026-10，神圣家族）

`/chinese/marx-engels/02/` = 《马恩全集》第二卷（`000` 全卷说明 + `001`-`032`）。
《神圣家族》= **001–010**（001 = 扉页+序言，002–010 = 第一至九章，010 含“历史的结语”）。
项目 `/root/shensheng_jiating/`（build.py / verify.py / verify2.py，venv=`epubenv`）。

本卷是第三种版式，与前面几本的三处关键不同：

1. **脚注不是 `_ftnref` 锚点**：正文是纯文本 `[N]`，注释在页末 `<hr width="60%">` 之后的
   `<span>…注释：[N]…</span>` 区里（每页自成一套，全书 90 条）。链接要自己造：
   正文 `[N]`→`<a id="ftnrefN" href="#ftnN"><sup>[N]</sup></a>`（只首次带 id），
   注释区 `[N]`→`<a id="ftnN" href="#ftnrefN">[N]</a>`。
   **标题里的 `[N]` 也要 linkify**（如 `《MüHLEIGNER》[4]`），否则注释的回链指向不存在的
   `#ftnrefN`，epubcheck 报 `RSC-012 Fragment identifier is not defined`（实测 003/004 各一处）。
2. **标题交叉闭合**：`<h4 …>…</h3>`、`<h3 …>…</h4>`（005/007/009 共 7 处）。直接交给 bs4 会把
   后面正文吞进标题（实测一个 h4 里塞进上千字）。解析前先用
   `<h([34])([^>]*)>(.*?)</h[34]>` → `<h\1\2>\3</h\1>` 拉直。
3. **注释区整块包在一个 `<span style="font-size:10.5pt">` 里**，条目间是 `<br>`。`<br>` 在 span
   *内部*，通用“裸文本+`<br>`”流式切段抓不到它（会把整块注释吞成一个段落）——注释区要单独处理：
   剥掉最外层 span 标记 → 按 `<br>` 切行 → 每行单独 parse 成段，行首 `[N]` 换成回链锚点。

另外：（a）`div.a3` = 引文缩进块（本书量很大）→ `blockquote`；`<font color="#003E00">` 专用于包
译者注/编者注 → `span.note`。（b）009 有全书唯一一张**真表格**（“奖赏和惩罚。双重裁判”附表，
Word 导出，左列 | 全空分隔列 | 右列）→ 保留为 `table` 并丢掉全空列；其余单格表是版式表，
要 unwrap（连 `tr/td/tbody` 一起去掉）。（c）站点源码自身有 **9 处 `?`**（002 页德语变元音位置，
如 `Kunstgeb?udes`），原样保留、不猜补，并在交付报告里说明。（d）插图只有 `02/03.jpg`
（神圣家族第一版扉页），图题取自目录页「插图」清单。

核验（2026-10-02 交付）：脚注 90/90 双向可达、零断链；25 字窗口双向比对仅差“站点面包屑导航”
（按设计剥离）与新增图题/附录标签；epubcheck 5.1.0：0 error / 0 warning。

## 外文转录损伤的校订（2026-10，神圣家族）

站点是 GB2312，外文（德／法／拉丁）里集中出现五类损伤，全部可以靠外文原文订正：

| 类别 | 例（原 → 校） | 量（本书） |
|---|---|---|
| `?` 吞掉变音符/重音符 | `Kunstgeb?udes` → `Kunstgebäudes`；`par ?à` → `par çà` | 11 |
| 希腊 `β` 当 `ß` 用 | `preuβischen` → `preußischen` | 4 |
| 词内断行连字符 `—` | `entrep—reneurs` → `entrepreneurs`；`Phäno—menologie` → `Phänomenologie` | 45 |
| 全角连字符 `－` 混入外文 | `mill－owners` → `mill-owners`；`Begriffs－Affektion` → `Begriffs-Affektion` | 3 |
| 外文缺空格 | `droitdes gens` → `droit des gens`；`fürWissen—schaft` → `für Wissenschaft` | 4 |

**校对源（德文原文）**：archive.org 开放条目 `marx-engels-werke-band-2`（opensource 集合）里的
`Marx-Engels-Werke Band 2 …_djvu.txt`（1.6 MB，全卷 OCR 全文）与
`heilige Familie, Die …_djvu.txt`（单行本）。一次下载，可离线检索任意德文/法文词形。
**借阅受限的扫描件不要浪费时间**：`collection:printdisabled` 的卷（如 `karlmarxfriedric0002marx`）
其 `_djvu.txt`、`_hocr_searchtext.txt.gz`、`fulltext/inside.php` 书内检索全部 403。
德文原文的另一个旧途径 mlwerke.de 已下线，只存在于 Wayback，且 Wayback 对连发请求会临时封 IP
（`code=000`，等十几分钟自愈）。以 archive.org 那个开放条目为首选。

书目/专名/报刊名若不在德文卷里（傅立叶两部书名、`Der Social-Demokrat`、`Guy Delavau`、
洛克《Essay》等），用维基百科 REST summary 逐条核对（`/api/rest_v1/page/summary/<标题>`，注意 429 限流）。

**工作流**：
1. 先在实体反转义后的文本上枚举候选（正则：`[A-Za-zÀ-ÿ]+\?[A-Za-zÀ-ÿ]+`、`β`、
   `[A-Za-zÀ-ÿ]{2,}[—–][A-Za-zÀ-ÿ]{2,}`、`[A-Za-zÀ-ÿ]{2,}\uff0d[A-Za-zÀ-ÿ]{2,}`）——
   **不要跳过反转义**，源文里 `ö/à/î/é` 有一半是 `&ouml;` 这种实体写法，不反转义会漏掉一批。
2. 把规则写成「原形 → 校订形 + 依据句」的表格（见项目 `emend_data.py`），逐条在校对源里检索。
3. 在构建脚本里应用，并**断言应用数 == 清单数**（对不上说明某条词形写错或文中是不换行空格）。
4. 校订记单独成附录（位置／原文／校订／依据），内容必须 `html.escape`。
5. 终检：把校订表先应用到源文，再与 EPUB 做**双向 25 字窗口比对**，应当 0 差异。

**陷阱**：源文用不换行空格连外文短语（`deus ex ma—china`、`quel—que chose`），所以规则里的空格
必须用 `[\s\u00a0]+` 匹配，否则这类词会静默漏替（本书漏了 4 处，靠上面第 3 步的断言才发现）。

## 单页长文型页面（2026-10，德意志意识形态节选）

有些条目不是多章书，而是**一个 `.htm` 装完全文**（`/chinese/marx/<slug>.htm`）。项目
`/root/deyizhi_ideologie/`（parse.py → check_text.py → build.py → finalize.py → verify_all.py）。
结构：面包屑 → 第一个 `<hr>` → 正文（~86 KB）→ `<div style="mso-element: footnote-list">`
注释区。此页 14 万字符、脚注 82 条、无图片。

四处与多章书不同的陷阱：

1. **`<br>` 全部成对**（实测 `{1: 36, 2: 123}`：单个 36 处、连写 2 个 123 处，无更长连写）。
   源站用 `<br><br>` 分段、单个 `<br>` 只在**标题内换行**（如 `费尔巴哈<br/>唯物主义观点…`）。
   所以切段条件是 **`<br>` 连续数 ≥ 2**；把单个 `<br>` 也当分段会切出碎段，把连写当段内换行会吞段。
2. **源码有大量未闭合 `<span>`**（本例 28 处，集中在页末「手稿片段摘录」区，形如
   `<p align="center"><span>————</p><br>　　…</span>`）。交给 bs4 会把后续几千字吞进
   那个居中段（实测「国家和法同所有制的关系」段被吞 2 300 字、「[IV]」段被吞数千字）。
   对策：**自写线性 token 切块器**，遇到块级开/闭标签时把栈里未闭合的内联标签自动补上 `</…>`，
   然后再解析。比事后修树可靠得多。
3. **编号形式混用 `①` 与 `[N]`**：`<font size="3">①</font>`（Unicode）与前 10 条之外的
   `[11]`…`[82]`（ASCII 方括号）。统一时剥掉 `[\[\]［］]` 即可；正文锚点 `_ftnrefN`、
   注释区 `<div style="mso-element: footnote" id="ftnN">`（**每页自成一 div**，不是单页末 `_ftnN` 锚点）。
4. **黑体 `<span style="font-family: SimHei">` 可跨 `<br><br>` 跨段**（源站用它标手稿片段）。
   段末补 `</strong>`、下一段开头重开 `<strong>` —— 否则 `</strong>` 落单，阅读器把粗体吃到段末。
   注意 `flush()` 即使文本为空也要补闭合，否则空段吃掉配对（本例 2 处）。
   段首 `　　` 紧跟在 `<strong>` 之后要剥掉，否则 `<strong>\n　　笃信宗教者…` 里带缩进空格。

另外：标题只有三种（`<h3>` 章标题 + 居中 `<p>` 的 `[Ⅰ]`/`[Ⅱ]…` 分部标记 + 4 个居中 `<p>` 小节），
其中 `1.一般意识形态，特别是德国哲学` 与 `A.` 被源站拆成**两个相邻居中 `<p>`**，要合并成一行 h4。

核验（2026-10-11 交付）：正文 45 667 字 + 注释 5 054 字与源文逐字一致；82 条脚注双向零断链；
内部链接 200 条 0 坏链；epubcheck 5.1.0：0 error / 0 warning。

## 已知非问题（免得每次重查）

- `scripts/epub_toc_audit.py` 对「带 properties=nav 的 nav.xhtml」会把它自身的
  `<h2>书名</h2>` 也算作「正文标题」，报 2 条假问题（「1 个标题缺少 id」「1 个未进入导航」，
  例子里是 `EPUB/nav.xhtml#`）。确认 `nav.xhtml` 里只有那一个无 id 的 `<h2>` 即可忽略。

## 已转换书目（2026-08，复用 `web-to-epub` 模板）

| 书名 | 原书 | 页面 | 特点 |
|---|---|---|---|
| 经济危机理论：马克思的视角 | Marx's Theory of Crisis (1994), Simon Clarke | 14 | 常规页面，12 脚注/章 |
| 重读《资本论》 | Rereading Capital (1979), Ben Fine & Laurence Harris | 13 | 附录为 Word 转换页: 30 个 VML 公式图 |

## Word 转换页（鲍特凯维兹论文型）

- 公式双份存在:
  - `<!--[if gte vml 1]><v:shapetype ...>...<v:imagedata src="11.files/image001.png"/></v:shape><![endif]-->`
  - `<![if !vml]><img ... src="11.files/image002.gif" v:shapes="_x0000_s1054"><![endif]>`
- 图片文件在 `<页码>.files/` 子目录，编号**不连续**（image001, 003, 005, … 017, 019, … 059）。
  用 `re.findall(r'image(\d+)\.\w+')` 收集全部编号再下载，`printf "%03d"` 补零。
- 表格图可能单独命名（如 `11-1.jpg`, `11-2.jpg`）直接放页面同目录。
- `<center><img>` 结构嵌套在 `<p>` 里 —— img src 改写必须在段落化**之前**全局做。

## 下载清单模板

```bash
BASE="https://www.marxists.org/chinese/reference-books/<slug>"
mkdir -p pages && cd pages
for p in 00a 00b 01 02 ... 11; do
  curl -sL --max-time 30 -o "${p}.htm" "$BASE/${p}.htm"
done
# 公式图（Word 页）:
for n in $(seq 1 2 59); do
  nn=$(printf "%03d" $n)
  curl -sL --max-time 20 -o "image${nn}.png" "$BASE/11.files/image${nn}.png"
done
```
