# 张世英《黑格尔〈小逻辑〉绎注》EPUB 生成阶段实录（第三套文件）

承接 repair-session（213→0 不匹配）。本阶段：严格递增校验 → 重编号 → 双向锚点 → pandoc → 跨文件锚点修正 → 封面。所有脚本在 /root/hegel_yizhu/（mdlinks.py、renumber.py、fix_epub_links.py）。

## 关键发现

### 1. count 对齐 ≠ 编号正确
align.py 报 `mismatch: 0 / 243` 后，mdlinks.py 生成的锚点出现 59 个重复 id + 45 个缺失目标。根因：**数量对但编号错**——正文标记序列 `1,2,3,1,5`、`8,3,10`、`1,3,3,4` 等，OCR 把缺号重读成前面已出现的数（"缺 N 补 1"）。全书 37 处，覆盖节（28）、章节（c6 第三版序言）、附录。

校验脚本（逐区域严格递增）：
```python
marks = sec_marks[sec]   # 正文 [[MARK:N]] 按出现顺序
notes = sec_notes[sec]   # 注释圈码按出现顺序
ok = (marks == list(range(1, len(marks)+1))) and (marks == notes)
```
附录按页：`marks == list(range(1, len+1))` 每页独立。

### 2. 重编号修复（一次清 37 处，勿逐节写 fix）
renumber.py 核心逻辑：
- 正文/注释**独立计数器**（正文第 k 个标记→k，注释第 k 条→k，两者按位置 1:1 对应）
- 区域重置：新节、新章、附录换页
- 附录正文标记保留页码前缀 `[[MARK:pg-N]]` → `[[MARK:pg-k]]`（曾丢前缀导致 mdlinks 无法配对）
- **SKIP_SEC = {146}**：第146节是语义验证过的顺序颠倒（`5,6,4` 对应注释"萌芽⑤→潜在⑥→实在④"，作者有意为之），重排会破坏语义锚点

### 3. mdlinks.py 锚点命名（全局唯一）
- 节：`s{真实节号}-ref-{N}` / `s{真实节号}-note-{N}`（跨章唯一）
- 章：`c{运行章号}-ref-{N}`（序言/导言等无节结构）
- 附录：`a-{page}-ref-{N}`
- 正文：`<a id="...-ref-N" href="#...-note-N"><sup>N</sup></a>`
- 注释条目：`<a id="...-note-N"></a><sup>圈码</sup>{文本} <a href="#...-ref-N">↩</a>`
- **每章重置的 sec_idx 做锚点 → 严重重复**（s1-ref-1×6、s20-ref-1×4）
- 生成后校验：`Counter(ids)` 重复==0 且 href 目标全部在 ids 中

### 4. 章节/附录 apply_fixes 键
- 章节级正文分支（cur_sec is None）用**章节标题**作键：`"第二版序言"`、`"第三版序言"`
- 附录正文分支用 `"附录"` 键
- 漏加则 fix 静默失效：第二版序言 ⑦（波麦）/⑫（斯宾诺莎）/⑬（哲学与宗教）落点最初全没生效；附录 p370 注释②（《小逻辑》第247页）落点 `[[MARK:370-2]]` 靠 `附录` 键注入

### 5. fix 的 old 形式取决于 apply_fixes 执行点
- 正文分支在 norm_marks 前 → old 用原始 `^{①}` 或裸文本
- 个别路径（第121节）在 norm 后 → old 用 `[[MARK:2]]`
- 不命中就 showsec.py 查证换形式；被漏的错号由严格递增校验+重编号兜底

### 6. fix_epub_links.py 校验路径陷阱
nav.xhtml 的 TOC 链接 `text/ch001.xhtml#第三卷说明` 相对 **EPUB/ 根**（不是 nav 所在目录）——校验时 `os.path.join(WORK, parts[0])` 失败须 fallback `os.path.join(WORK, curdir, parts[0])`，否则 TOC 全报假错（108 条 parse fail，实际 0 错）。

最终指标：ids=1744 unique=1744、重复 0、缺失 0、XML 0 错、zip OK。

## 封面（尚未注入，待续）
豆瓣 subject_suggest API 命中：`https://book.douban.com/j/subject_suggest?q=黑格尔小逻辑绎注` → id 26804495（张世英，2016），封面 `https://img3.doubanio.com/view/subject/l/public/s29186887.jpg`（s→l 换大图，260x281 已下载 cover.jpg）。注意 URL 需 URL-encode 中文 + Referer 头。
