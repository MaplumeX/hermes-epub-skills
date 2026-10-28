# 案例：《马克思经济学与数理分析》（藤森赖明、李帮喜，社科文献 2014）

## 源数据
- 两个 layout.json：`doc_59220d519e75`（p1，200 页，第一～十二章第二节）、`doc_6ffd2682533b`（p2，123 页，第十二章第三节起 + 附录 A/B + 参考文献 + 索引）
- p1 无章号页眉，p2 页眉带章名（"第十三章 …"）；两册页脚注释各自独立编号
- 块类型：text / title / interline_equation(811) / table(33) / image+chart(21)；span 含 inline_equation(1606)
- 每页页脚 `page_footnote` 用圈码 ①②（每页从①重新编号），另有 `***` 是**式号被 OCR 吃掉**（`式(***)`、`式(****)`），不是注释标记

## 关键技术点

### 1. 公式：全部 MathML，可复制
- `interline_equation` → `$$…$$`，`\tag{X}` 转 `\qquad\text{(X)}`（pandoc 对 `\tag` 支持不稳）
- `inline_equation`：`^{①}` 形式还原成圈码标记、`^{N}` 转 `<sup>`、其余包 `$…$`
- **`clean_tex` 只做 array 列格式去空格，绝不要 `replace('\\\\','\\')`**：本案例源数据里的换行已经是 `\\`（JSON 解码后就是双反斜杠字符串 `\\`），再替换一次会把 `\\` 变成单 `\`，于是 `\begin{pmatrix}6000\\0\end{pmatrix}` 里那个 `\\0` 被 texmath 读成 `\0` 控制序列 → pandoc 报 `unexpected control sequence \0` 并退化成纯 TeX 源码。症状是 `pandoc` 对 811 个公式里的少数几个报 warning，但 exit code 仍 0
- 验收：解包 EPUB 剥掉 `<math>` 后搜裸 `\\[a-zA-Z]{2,}` 必须为 0

### 2. 网格表格：**单元格内容不要截断换行**（本案例核心教训）
- 第一版给列宽设了 `maxw=14` 并自己按显示宽度切行，pandoc 会在**切开的半行处插空格**：`| 马克思的资本分 |` + `| 类 |` → 渲染成 "马克思的资本分 类"，用户一眼看出字被拆开
- 正确做法：**列宽 = 内容最大显示宽度，不截断**，宽表交给阅读器横向滚动；`grid_md(rows)` 不要传 maxw
- 中文宽度用 `unicodedata.east_asian_width(ch) in ('W','F')` 计 2
- 验收（比 `check_grid_tables.py` 更直接）：把每张 grid table 单独喂 pandoc 转 html，检查 ① `<table>` 存在 ② 每行 `<td>` 数一致 ③ 去标签后无 `|` 残留

### 3. OCR 把整列零值读成一串 `. 0. 0. 0. …`
- 表 A-3/A-9 里 `| . 0. 0. 0. 0. … . 15 |` 长达 100 字符，`clean_cell` 按 `c.count('. 0') >= 5` 判为无法还原 → 输出 `⋯`
- 其余 `\. 0\.00000` / `\.0.00000` 是小数点被单独识别，用正则还原成 `0.00000`

### 4. 页脚注释里混入纯公式重复块
- OCR 把正文旁挂的公式、或页脚内联公式重复输出成独立 `page_footnote` 块（39 处），会污染注释
- 判定：`re.fullmatch(r'\$[^$]*\$', t)` 且**归一化后（去空白/`$`/`\\`/`{}`）在本页正文+注释里出现 ≥2 次** → 丢弃
- 极短碎片（`ω`、`g`、`r=0`）且已出现在上一条注释正文里 → 也丢

### 5. 注释标记错位与补回
- 正文标记 76 个 vs 注释条目 66 个，缺口集中在"注释区跨页续页首块被误分类成正文"：块以圈码开头且 `len<80` → 归入当前页 notes（本案例 6 页）
- 剩余 `式(***)` 是式号不是标记，`sub_marks` 里对非圈码标记原样返回
- 最终 74 条注释、noteref 74 / backlink 74 全配对

### 6. 图片：layout 只给哈希名，用户补包后自动嵌入
- `image`/`chart` 块的 `blocks[]` 里 `image_body`/`chart_body` 的 span 带 `image_path`；图题在 `image_caption`/`chart_caption`（chart 块同理，别只收 `image_*`）
- build 里 `os.path.exists(images/<hash>)` 决定输出 `![](images/<hash>.jpg)` 还是 `〔图〕`；图题一律排在**图后**加粗
- 用户补的包是**分卷 zip**（`images.z01 + images.zip`）：`7z x -y -o<out> images.zip` 自动补齐卷，`Everything is Ok`；**不要 `cat` 拼接后 unzip**
- 21 个 fig 块里有 1 个是 CIP 页 logo（无 caption）→ 跳过，最终 20 图与「图目录」20 条一一对应
- 用 vision 抽查 2 张（图1-1 劳动二重性、图14-1 g_{t+1}/g_t 映射图）确认图题配对正确

### 7. pandoc EPUB 默认 CSS 没有 `img` 规则
- 900px 宽的图在手机上会溢出 → 注入 `img { max-width:100%; height:auto; }` + `p > img { display:block; margin:.8em auto; }`

### 8. 其他
- Ground Truth 噪声（`The Ground Truth image displays a single, solid horizontal line…`）8 块，extract 阶段按子串过滤
- 原书 OCR 目录页（p1 pi 12–17）整块删除，用 pandoc 自动目录；图目录/表目录/索引保留为 `- ` 列表项（索引跨 6 页 pi 117–122）
- 页眉 "马克思经济学与数理分析" 是 title 类型，靠 `is_heading_title` 返回 None + 文本等于书名丢弃
- 层级：`#` 章/附录/前置章节，`##` 节 + `B.x` 小节，`###` 一/二/三 小标题（可能是 text 类型，需正则 + len<45 + 无 `。！？，、；` 判定）
- 正文 `TeX`/`LaTeX` 的 OCR 错读（`$\\mathrm{T_{EX}}$`、`$IATEX$`）用 `FIXES` 表修
- 交付：696 KB，55 个 zip 条目（35 + 20 图），`validate_epub.py` 全绿
