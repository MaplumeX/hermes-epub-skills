# 案例：范里安《微观经济学：现代观点》（第九版）三部分合并

## 源数据
- 3 个 layout.json：A=封面/前言/第1-13章（200页）、B=第14-29.2章（200页）、C=第29.3-38章+数学附录+各章复习题答案+英汉名词对照表+OCR元数据（193页）
- 必须丢弃：A p0-2（封面/书名页/CIP）、A p23-28（原书目录，表格+文本）、C p178-192（版权页、封底广告、超星 OCR 元数据页 [General Information]/目录页）
- 该书**没有**章末注释，只有页脚注释（page_footnote）：A 20 条、B 35 条、C 53 条，共 108 条；正文用圈码 ①，**每页从 ① 重新编号**；另有 1 条译者注用 `*`（OCR 成 inline_equation `^{*}`）

## 关键实现（本项目脚本：extract.py / build.py，在 /root/work_epub/varian）
1. **公式**：inline_equation span → `$latex$`；interline_equation 块 → 独立 `$$latex$$`。pandoc `--mathml` 出 EPUB3 MathML。
   - `\tag{4.1}` 会被 MathML 丢弃 → 改写成 `\qquad\text{(4.1)}` 保留公式编号（正文常引用“方程式(14.1)”）。
   - **texmath 不接受列格式空格**：`\begin{array}{r l}` 报 `unexpected "l"`（全书 66 处）→ 正则去空格 `{rl}`。
   - OCR 残留 `(\ref {e q : 1})` 也要删（texmath 报 unexpected control sequence）。
   - 校验方法：把所有公式各占一段 `$eq$` 丢给 `pandoc -t html --mathml --wrap=none`，输出按行对齐，行内无 `<math` 即失败（**必须用空行分隔**，否则多式并成一段无法对齐）。修完应为 0 失败（本例 2551 式去重后）。
2. **表格**：table_body 的 span 里有 `html`（`<table>...`），table_caption 是块内独立 sub-block。31 个表格（含博弈收益矩阵 rowspan/colspan）→ 直接保留 raw HTML + 表格外一行表题。
   - **raw HTML 不经过 markdown 解析**，所以表格单元格里的 `$latex$` 必须自己预转 MathML 再嵌进 HTML（同一批 pandoc 转换复用）。
3. **脚注**：页脚 page_footnote 按圈码拆条 → 正文第 k 个圈码替换为 markdown 脚注标记 `[^A37-1]`，定义 `[^A37-1]: ...` 按**章**集中放在每章末尾 → pandoc 自动生成 `epub:type="noteref"` 与 `footnote-back` 双向跳转（实测 108/108），配 `--epub-chapter-level=1` 时定义与引用落在同一 xhtml。
   - 标记按 (页, 顺序) 配对；实测每页正文圈码数 == 页脚条目数（除 CIP 页被丢）。
   - 无标记的 `*` 注释要单独处理：`*` 作为该页的 marker，正文里的 `*` 同样替换。
   - 章切换时必须 flush 上一章的脚注定义（`if ch != cur_ch: flush(cur_ch)`）——`ch=None`（前言区）也要 flush，否则前言那条注释只有引用没有定义（本例 A21-1 曾漏定义，靠“引用数==定义数”计数才发现）。
4. **插图**：image/chart 块只有 `image_path` 文件名、**layout.json 不含图像数据**（本书 302 张 jpg，正文引用 295 处）→ 输出 `〔图〕` 占位；图题（`^图\s*[A-Za-z]?\d+`、短、无句末标点）先挂到同页最近的图块，渲染成 `〔图〕 图 1.1 …`。
   - **补齐路径**：导出 `figures.json`（每块的 tag/pi/bbox/src/path）与唯一文件名清单 `needed_images.txt` 发给用户；用户把 jpg 放进 `<项目>/images/` 后**同一份 build.py 自动换成真图**（`os.path.exists` 判定：存在→`![](images/<hash>.jpg)` + 下一行斜体图题；缺失→`〔图〕`），不需要改代码。缩略图/内联小图（w<60 或 h<40，如书名页的 5 个小 logo）不输出。
   - 图缺失的副作用：约 50 处被插图打断的句子没法接上（续文以拉丁字符开头时 `can_join` 拒绝，“A 无差异曲线”这类图内标签也会混进正文）——这是数据缺口不是脚本 bug，报给用户。
5. **跨页/跨图断行合并**：段落被页边界或被插图打断是常态。合并规则：前块无句末标点 + 后块以中日韩字符开头（或两侧均为字母数字）+ 后块不是列表项 → 合并；**允许跨过中间的 fig 块**（图让到合并后的段落之后）；**冒号结尾不合并**（“框架：”引出下文，误合并会把定义段吞进上一段——“最优化原理:…”“均衡原理:…”两段曾被吞）。
   - 正则：`TERMINAL = [。！？….!?"”’」』）)\]】]$`，`LISTLIKE = ^(\d+\.\s|[-—–·]\s|[①-⑳]|[IVXLC]+\.)`，`CJK_START = ^[\u4e00-\u9fff（(“‘【《…]`。
   - 合并要**迭代到稳定**（一段可能跨 3 页），每次合并后 key 取后一块，才能继续与下一页合并。
   - 剩余未合并段落的体检方法：从 book.md 里找“不以终止标点结尾”的段落，**跳过下一非空行是 `$$` 的**（公式引导句“我们就有/可以写为”本来就不完整）和列表项、对照表条目——本例 5918 段里剩 101 段属正常/数据缺口。
6. **章起始检测**：页面**前 4 个块**里出现章名（38 章名单）即为章首页；章号来源优先级＝独立数字 title 块（`33`、`▶25`，须跳过不输出）→ 该章页区间内首个 `N.M` 节号 → 页眉 `head`；再用“向后传播”给所有非章首页赋当前章（漏了这步会导致 `ch=None`，跨章页码合并与脚注归章全错——症状：合并静默失效、脚注全挤到一章）。38 章编号连续性是第一道体检。
7. **双栏页**（英汉名词对照表 p167-177）：按 `(x0<246, y)` 排序。**不要用“左右块数阈值”自动判定双栏**——插图页右半页的图/公式块会被误判（A/B 各有 12+ 页误报，还会把正文顺序打乱），改用显式页区间（`TWOCOL = {'C': range(167,178)}`）。
8. 原书系列标题（主编的话/译者的话/第九版前言）、章、节、例子(`例子：X`)、`小结/复习题/附录`、`A.1 函数`、`第N章 名称`(答案区)分级：h1=章/前言/后附、h2=节/小结/复习题/附录、h3=例子/子标题（含 `- xxx` 标题块去短横）。`1. 2. 3.` 条目转义成 `1\.` 保持普通段落（不做列表，避免 pandoc 列表嵌套）。
9. 对照表（英汉名词对照表）条目本身不以标点结尾，正在被合并规则误伤的判定条件是“后块以 ASCII 开头”——`CJK_START` 正好挡住它们，不要放宽这条。

## 图题/图释的 EPUB 标记（用户会追问“是不是搞成正文了”）
- 图题**不能**写成 `**图 N.M**` 加一段普通段——渲染出来是普通正文，看不出是图题。
- 更关键的教训：**不要靠自定义 CSS 类做图释样式**（用户明确反馈“小字浅色的 note 样式大多数阅读器都不支持”）。可靠的只有**结构 + 内联语义**：
  - 图题：`![图 N.M 标题](images/x.jpg)`（alt 非空才会生成 `<figure>`）→ 后处理把 `<figcaption>` 内容换成 `<figcaption><strong>标题</strong></figcaption>`，忽略 CSS 也加粗。
  - 图释：不要留在 figure 外的 `div`，后处理合并进同一个 figcaption：`<figcaption><strong>标题</strong><br /><span class="figure-note">图释</span></figcaption>`。忽略 CSS 时就是图题下一行普通文字，仍在图块内，不会散成正文。
  - 无图题的裸图（空 alt → pandoc 只给 `<p><img/></p>`）+ 图释：用 `<p><img/></p>`+note 模式包成 `<figure><img/><figcaption>图释</figcaption></figure>`（本例 24 处）。
  - 懒尾落下：任何仍未挂到图上的 note div 就去掉类名降级为普通段落（内容不丢）。
- 校验：`figure` 元素数、残留 `figure-note` div 应为 0、epubcheck 0/0；打开任一图确认 `<figure>` 里既有 `<strong>` 标题又有 note span。

## 公式序列化必须全路径统一（用户报“符号显示成 p_{c}”）
- 症状：EPUB 里出现裸 LaTeX（`p_{c}`、`y^{2}`、`\bar{x}_1`），或被 markdown 当成强调（`p^{*}` → `<em>`）。
- 根因：正文块走了 `block_segments()`（把 `inline_equation` span 包成 `$...$`），但 **caption/footnote 子块、page_footnote、table_caption 当时用的是 raw_text（只拼 span.content，丢了数学定界符）**。
- 修法：抽一个 `sub_text(bb)`＝对任意块跑 `block_segments()` 后 `tx` 原样、`eq` 包 `$...$`；把 caption/footnote 子块、page_footnote、table_caption 全部改成用它。
- 修复后 MathML 计数上升（本例 3992 → 4050），即找回 58 处公式。
- **残留扫描器**（改完必跑）：解包 EPUB，对每个 xhtml 先 `re.sub(r'<math.*?</math>',' ')` 屏蔽已渲染公式，再扫 `\\[a-zA-Z]{2,}`、`[_^]\{[^}]{1,12}\}`、`\$`；同时扫 `<img alt="...">` 里的 LaTeX（pandoc 会把 figcaption 里的公式在 alt 属性中纯文本化，需后处理清理）。合法的 `$400 000` 美元金额会被误报，人工判一下。

## ⚠ 图题/图释在结构化子块里（极易漏）
- `image`/`chart` 块的 `blocks` 里有四种 sub-block：`image_body`/`chart_body`（真正的图，span.image_path）、**`image_caption`/`chart_caption`**、**`image_footnote`/`chart_footnote`**；`table` 块则有 `table_caption`/`table_body`。
- **绝大多数图题只存在于 caption 子块，正文块里没有**（实测：196 个 caption 子块中只有 1 个同时以 text 块出现）。只看 preproc 的 text 块（或只看 `^图\d` 短行）会丢掉一大半图题，并且正文里那些“图 N.M 中标记为……”的片段会被误当图题。
- caption 子块里可能是**两条**：一条描述句（“在短期内，住房的供给是固定的。”）+ 一条真图题（“图 1.3 短期供给曲线”）；`image_footnote` 也是图释说明句（如“纵轴表示市场价格,横轴表示每一个价格上将租出的住房数量。”）。两类都不能丢。
- 实现：fig 块携带 caps/fns 两个列表；build 里 `^图\s*[A-Za-z]?\d` 的那条当图题（加粗），其余 caption + footnote 合为图释段（普通字体）；**仅当图块没有结构化图题时**才启用“正文短行充当图题”的几何兜底；同页与结构化图题同文的 text 块要去重。
- 矢量校验：逐个 caps/fns 文本查 `in book.md`，应为 0 丢失（本例 295 个图块、111 个有 caption 子块、88 个有 footnote 子块）。
- 尺寸过滤（w<60 或 h<40）会连带丢掉图题：本例只有 1 处（封底的微博二维码，本就在丢弃页），基本无损失。

## 插图补回（MinerU 分卷 zip）
- `zip -s` 分卷包（MinerU.z01…z10 + MinerU.zip，共 115MB）**不能直接 `cat` 拼接**：各分卷开头带 spanning 标记，Python `zipfile` 报 `Bad magic number for file header`。用 `apt-get install unzip p7zip-full` 后 `7z x MinerU.zip -o<dir> -y` 直接解压（7z 会自动识别 .z01+的分卷，且 GBK 文件名解码正确）。
- zip 内结构：`<书名的乱码目录>/部分N.pdf-<uuid>/images/*.jpg` + layout.json + full.md + origin.pdf。**里面 layout.json 的 md5 与用户先前发的完全一致**。
- 图片按 **basename（内容 hash）** 平铺到 `work/images/` 即可；302 个引用文件全部命中（zip 里共 1347 张，含未引用的）。
- build.py 渲染分支：`os.path.exists(IMGDIR + path)` 则输出 `![](images/<path>)` + `*图题*`（斜体独立行），否则 `〔图〕`。**注意：extract 阶段新加的字段（如 `path`）必须在 load_stream 的 stream item 显式带上，否则静默丢失**（曾因此图全没插进去）。
- 图幅：MinerU 剪切图为原页面分辨率，中位宽约 590px、~14KB/张，295 张共 4.7MB；纯线图在手机上可读，但高 DPI 下略软。
- 抽检方法：从 book.md 捉 `![]`与图题配对，把图片丢给 vision 模型确认“图像内容 == 图题”（本书抽查图3.8 离散商品 / 图29.2 新进入博弈 / 图15.4 线性需求曲线弹性 / 图35.4 公地的悲剧，全部对得上）。

## 交付形态
- `pandoc book.md -o out.epub --mathml --toc --toc-depth=2 --epub-chapter-level=1 --epub-cover-image=cover.jpg --css style.css --epub-metadata=epub-metadata.xml`
- 封面用豆瓣 `book.douban.com/j/subject_suggest?q=` 取真实书影（`s`→`l` 大图，需 `Referer: https://book.douban.com/`）；下载后用 vision 核对封面书名/译者/出版社确实对得上再注入
- 校验：`python3 scripts/validate_epub.py out.epub` + `java -jar epubcheck.jar out.epub`（本例 0 fatal / 0 error / 0 warning）+ 公式批量转 MathML 0 失败
- 规模参考：正文 696K 字符、5385 段、2551 个去重公式（1013 行间）、3991 MathML、31 表格、108 脚注、44 个 h1 分文件、841 KB EPUB

## 交付/取件（本会话踩的坑）
- Telegram 机器人上限 **20 MB**。用户 115 MB 的图片 zip（1.zip）被平台拒收，回执 "The document is too large…Maximum: 20 MB." 以**入站消息**形式出现，agent 易误读成“自己发出去的 EPUB 失败了”并去折腾文件名。**正解**：`grep 'Document too large' ~/.hermes/logs/gateway.log` 拿字节数（本例 `115269237 bytes`）跟自己的文件（841 KB）比对——差两个数量级就是对方的入站被拒。用户说“文件已发给你”但 `~/.hermes/cache/documents/` 里没有新文件时，先查这条日志再回复。
- 给用户的取件方案（按省事排序）：① 分卷 `zip -s 19m -r 1.zip <图片目录>` 后逐个发；② 丢到自己服务器/网盘给 http 直链（agent 可 curl）；③ 只取需要的 302 张，`mogrify -resize 900x -quality 75 -path small *.jpg` 压小再打包
