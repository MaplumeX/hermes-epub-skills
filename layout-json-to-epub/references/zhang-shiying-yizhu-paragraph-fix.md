# 张世英《黑格尔〈小逻辑〉绎注》分段修复 + 封面注入实录

第三套文件（doc_756a5d6126cc / doc_342945bdff38 / doc_e9818afeca4e）EPUB 生成后的
分段质量修复会话。标记对齐（243 节 0 不匹配）完成后，用户反馈"有些地方错误的分段了"。

## 问题 1：跨页/跨文件断行未合并（全书 100+ 处）

layout.json 每页块独立，句子在页末截断、下一页续接是常态。build.py 流构建默认不合并。

典型例子：
- P1 p3→p4："写成的。由于" + "作者水平有限"
- P1 p9→p10："真理的美" + "妙，但他们"
- P2 p199→P3 p0："Die setzende" + "Reflexion), 是指"（**跨文件**）
- P3 p0→p1："经过'根据'的规" + "定，达到"
- P3 p1→p2："纯粹的反思和规定的" + "反思的统一"

### 为什么不能在 book.md 层面做后处理合并（试过，撤销）

1. **无法区分页边界断行与页内正常分段**：book.md 没有页信息，会把页内合法分段也合并。
2. **单遍遍历不做链式合并**：L4934 被前一行合并后，合并行仍以"规定的"结尾（非终止），
   但循环已跳过该行，L4936"反思的统一"未并入。调试时 count=1 但 DEBUG 不触发——
   因为该行已被前一轮合并，循环索引已越过。

### 正确方案：pages.json 层面合并（scripts/merge_page_breaks.py）

- pass 1：y>635 的块按 `\n` 拆行，删除匹配 HEADER_FOOTER_RE 的行（块内嵌页脚噪声）
- pass 2：页末块以非终止标点结尾（先剥 `[[MARK:...]]`/圈码再判 TERMINAL）+ 下一页首块
  是纯续文（单行、非结构元素）→ 合并；结构元素绝不合并
- 跨文件边界（P2 尾 → P3 首）同样处理（pages 数组顺序即文件顺序）
- 备份 pages_raw.json，输出覆盖 pages.json，再跑 build.py

## 问题 2：块内嵌页脚噪声

- P1 p166 y=689 正文块内嵌"存在论"行（is_helper 只匹配整块所以漏网）
- P1 p100 y=608 孤立"逻辑学概念的初步规定71"

修复：HEADER_FOOTER_RE 扩展含 存在论/本质论/概念论（原只匹配第X篇）；
build.py 输出后 post-process 删孤立页眉行（`HEADER_FOOTER_RE.match(s) and not s.startswith('#')`）。

## 问题 3：重编号附录标记时丢失 `[[MARK:` 前缀

renumber 脚本附录分支曾输出 `361-1]]`（缺 `[[MARK:` 前缀），损坏 book.md。
恢复：重新 build.py 生成干净版 → 修 renumber → 重跑。教训：**改 renumber 后先检查
book_renum.md 附录区 `[[MARK:pg-N]]` 格式再 cp 覆盖 book.md**。

## 问题 4：封面注入 idref 实际带 `_xhtml` 后缀

pandoc 2.17 生成的 content.opf 中 item id 是 `title_page_xhtml`（不是 `title_page`），
spine itemref 也是 `idref="title_page_xhtml"`。add_metadata.py 若按 `title_page` 替换
会静默不生效（spine 首位仍是 title_page，cover 未注入）。修复：替换串用
`<item id="title_page_xhtml"` 和 `<itemref idref="title_page_xhtml"`。

验证：spine 前 3 = ['cover', 'title_page_xhtml', 'nav']、`properties="cover-image"` 存在、
nav 含 cover 条目、zipfile.testzip() OK、全部 xhtml/opf/ncx XML 解析通过。

## 问题 5：合并 5 大陷阱（第三套文件第二轮修复，逐一踩过）

首次合并（255 处）后 align 从 0/243 恶化到 7 处不匹配，逐轮排查：

### 陷阱 A：y 坐标污染（最隐蔽，第25节注释区整体崩溃）
- 现象：align 报 `第25节: body marks=0, note entries=113`——整节注释区被吞
- 根因：merge 时 `first_b['y'] = last_b['y']` 把下一页首块 y 改成上一页底部 y（640），
  该页按 y 排序后正文块被排到"注释："之后 → `in_notes` 状态机把整节正文当注释
- 修复：合并只改 text，**保留 first_b 原始 y**
- 教训：合并后必须重跑 align，不能只看合并数量

### 陷阱 B：TERMINAL 正则缺全角括号
- 现象：第三版序言注④（以"页）"结尾）被误判未结束，与下一页目录块错误合并，
  连锁污染第23-25节区域
- 修复：`TERMINAL = re.compile(r'[。！？….!?]["」』”’）)\]]*$')`（补全角 `）`）

### 陷阱 C：拆行页脚噪声 "导\n言\n23"
- 现象：第17节注③被拆断（"...集中讲了这个\n导\n言\n23问题。美国学者哈利士"）
- 根因：页脚"导言23"被 OCR 拆成三行，逐行匹配 HEADER_FOOTER_RE 全失败，
  pass1 未清除；pass2 把它当"最后正文块"与下一页首块合并
- 修复：pass1 对 y≥600 的块先 `re.sub(r'\s','',t)` 去空白拼接再匹配章节名，
  整块命中即删除

### 陷阱 D：pass1 误删真章节标题
- 现象：dropped 246 块（预期约 141），第25节区域章节标题被删
- 根因：最初对全页做噪声清理，y<600 的 title 块（"导言"）也被当噪声
- 修复：pass1 只处理 y≥600 的块，y<600 一律不动

### 陷阱 E：附录页脚注释标记错归
- 现象：check_appendix 报 P3 p375/376/377 错位（marks 6 vs notes 4 等）
- 根因：附录每页注释独立编号，跨页合并把上一页正文（含注释上标）并入下一页块，
  标记的页归属错乱
- 修复：附录区（P2 pi≥190、P3）页末块若含 `^{}`/圈码则跳过合并
- 教训：**校验必须三层全跑**——align.py（节级）+ check_appendix（附录每页）+
  check_chapters（章节级）；只跑 align 就进 EPUB 会漏掉附录错位

### 最终结果
- pass1：清 1 块内嵌噪声 + 删 247 个整块页脚噪声
- pass2：合并 205 处跨页断行（含链式合并：P3 p0+p1+p2 三段合一）
- align 0/243、check_appendix 66/66、check_chapters 全 OK
- 锚点 1744 个 0 重复 0 缺失，EPUB 断行抽查 6 处全部完整

## 调试技巧

- 跨页断行扫描：逐页取末块（按 y 排序），剥标记后 TERMINAL 不匹配且 len>15 → 报告，
  并打印下一页首块前 45 字符对照
- 孤立噪声行扫描：`re.match(r'^(章节名)(\d*)$', s) and not s.startswith('#')`
- 合并效果验证：`tail in ln and head in ln` 检查断行点是否已合并
- 残留断行扫描：正文段（非 #/注释/圈码开头）剥标记后 TERMINAL 不匹配且 len>15
