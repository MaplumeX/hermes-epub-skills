# 案例：《马克思主义哲学的历史和现状》上下卷（南京大学出版社 2004）

同一本书分两次交付（上卷 3 文件 440 页 / 下卷 3 文件 423 页）。管线是自建 `book.html` 而非 md：
`extract.py`（layout.json→pages.json）→ `build.py`（pages.json→book.html，含注释建链）→ `assemble.sh`（pandoc→元数据修补→python zipfile 打包）。

## 差异清单（换册必看）

1. **pandoc 2.17.1.1 没有 `--split-level`，只有 `--epub-chapter-level=N`**。报 `Unknown option --split-level` 就是这个。h1 = 章 → `--epub-chapter-level=1`。
2. **章节 id 必须唯一**：`cn2int` 写错（「二十X」被算成 2）会让第二十二/二十三/二十四章都拿到 `id="c2"`，epubcheck 报 4 条 `NAV-011 toc nav must be in reading order`（链接目标在文档顺序中倒退）。修 count 逻辑即消失。
3. **`toc.ncx` 的 `dtb:uid` 必须等于 `content.opf` 的 `dc:identifier`**，否则 `NCX-001`。ncx 里不是 `<dc:identifier>`，是 `<meta name="dtb:uid" content="urn:uuid:…"/>`，要单独改。
4. **厢页/篇名页不能整页 `blocks[2:]` 输出**：该页是「目录 / 下卷 / 篇名 / 然后紧跟目录正文」四个块起，取 `[2:]` 会把 6 页目录全文吐进厢页。只取前 3 块。
5. **后记署名行会被 `clean_spaces` 吞空格**：「主编 孙伯鍨 侯惠勤」→「主编孙伯鍨侯惠勤」。把这类行做显式 `SIGN_FIX` 字典（12 行）复原，不要放宽全局空格规则。
6. **主编姓名 OCR 一体五形**：孙伯鍥/鍬/镁/镔/揆 → 统一为「孙伯鍨」（作者上卷已确认）；全书 9 处，8 处为改写。
7. **章首页标题行可能整行丢**：下卷第十六章首页只剩章名，块 y 比其它章标题低 20px（章号那行被漏检、页眉页码也都没有）。用 y 偏移 + 目录对照判定，`HEAD_FIX` 补回。
8. **目录与正文不一致**：目录「苏联东欧哲学演变的历史**进程**」/ 正文「历史**过程**」，以正文为准（同书工卷也有同类一处：历史唯物主义的捍卫/马克思主义）。
9. **注文块末尾悬空冒号**（「…问题”：」）说明出处那半句源数据就没了，照原样保留并在说明里写明，不要自己补出处。
10. **按页顺序配对容错够用**：423 页里 4 页圈码 OCR 误读（①读完、顺序颠倒、④读成①），只要「页内正文标记顺序 ↔ 页脚注文顺序」一一对应就不受影响；不要逐页做集合相等校验就报错。
11. **下卷封面用上卷实拍封面改卷次**（豆瓣上下卷共用上卷图）：PIL 先 `MedianFilter(21)` 差分定位标签 bbox，再用邻近干净块 + 高斯羽化 inpaint，最后用 Noto Serif CJK（36px 汉字 + Liberation Serif 44px 窄括号手工定位）写「（下卷）」、Liberation Serif Italic 27 画 `(Volume II)`。vision 复核两轮。无 PIL 时 `pip install --break-system-packages`。
12. **交付校验四件套**（比 skill 通用清单更适合自建 HTML 管线）：
    - `class="nref noteref" / note footnote / back backlink` 三个计数相等（正则要写完整 class，pandoc 会追加 `noteref`/`footnote`/`backlink`）
    - 链接解析要在 `unz/EPUB/` 里跑（相对 `../styles/` 在错 cwd 会假报 1200+ 失效）
    - 字符守恒：`book.html` 去标签 vs 成品 `ch*.xhtml` 去标签，差值必须 0（pandoc 会给 `↩` 加 U+FE0E，差 617 就是这个，按需 normalize）
    - 逐段回溯：源块按 `{{C:}}` 切段，每段≥4 字在 `book.html` 里必须能逐字找到；剩余未命中项应恰好等于主动修改（本例 7 段 = 署名空格 + 主编名）
13. **页码口径**：上卷 A pN−22 / C pN+178 / B pN+378；下卷 A pN+411 / B pN+611 / C pN+811。同书两卷偏移完全不同，必须在说明里分开写。
