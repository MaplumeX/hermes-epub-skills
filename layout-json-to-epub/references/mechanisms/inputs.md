# M1 输入与外部协作

> **什么时候读**：收到多个 layout.json、分卷 zip、超大附件、图片包，或要先把图片清单发给用户时。
>
> **相关脚本**：`scripts/validate_epub.py（最后统一跑）`

> 本篇内容自 SKILL.md 拆出，条目逐字保留（含实测数字与原节出处）。

## 相关篇

> 一条结论常跨两个机制：**正文只在主归属那篇写一份**，这里只放指针。

- **M7** —— 多文件合订时章节起点、`title` 自带 `level`、跨册缺编名页
- **M8** —— 分卷压图 → 成品 EPUB 体积与 Telegram 20 MB 上限
- **M9** —— 多阶段重建链与校验顺序（raw 备份 → 合并 → 挂题注 → build）

## 来自「教科书（MathML 公式 + HTML 表格 + 页面圈码脚注 + 缺失插图）」

- **用户发大 zip 必先过 20 MB 上传上限**：分卷 `zip -s 19m -r 1.zip <目录>` / 给 http 直链 / 先压小——不要默默等文件到达
- **分卷 zip 用 `7z x`，不要 `cat` 合并后 unzip**（曼昆图片包实测）：用户常发 `images.z01..z04 + images.zip`。`cat *.z0* images.zip > all.zip` 后 `unzip` 报 `20971520 extra bytes at beginning`、`bad zipfile offset`、`invalid zip file with overlapped components (possible zip bomb)`——分卷的中央目录偏移按卷内位置算，拼接后全部错位。正确做法：把分卷放同一目录、**保留原卷名**，`7z x -y -o<out> images.zip`（7z 自动按 `images.z01..z04` 补齐卷，实测 5 卷 634 图全解，`Everything is Ok`）
- **压图用 ffmpeg（mogrify 不一定有，PIL 也可能没装）**：逐张 `ffmpeg -loglevel error -y -i f -vf "scale='min(900,iw)':-2" -q:v 6 out`。两个坑：① **输出文件名必须带 `.jpg` 后缀**（写 `f + '.tmp'` 会报 `Unable to find a suitable output format`，改成 `f + '.tmp.jpg'` 再 `os.replace`）；② 只压「book.md 里实际引用到的图」（正则 `!\[\]\(images/([^)]+)\)` 取集合），未引用的封面/装饰条不必进 EPUB。实测 575 张、900 px 宽、q:v 6 → 25 MB 降到 9.9 MB，成品 EPUB 10.1 MB（Telegram 20 MB 内）
- **同一本书的新版本要重新探索，不要复用旧脚本的阈值**：曼昆第十一版（references/mankiw-macroeconomics-11e-case.md）与第十版同社同版式，却有五处致命差异——①**页脚不再带章名**，章边界要从页首 title 块 `re.search(r'第\s*(\d+)\s*章')` 取（标题语序是乱的：`国民收入：源自何处？第3章 去向何方？`，startswith 必失败），且只能看**首块 + y<180**（序言里有个小节就叫「术语表」，扫全页 title 会把章判错）；②**篇分隔页页眉会 OCR 错**（实为第二篇却写「第一篇」）→ 篇号用出现顺序计数器，篇名查常量表；③**双栏阈值按页宽换算**（第十版 310/300 在第十一版漏掉整个右栏 `x0≈239`，症状是左右栏句子交替串栏）；④正文裸 `*` 译注与数学 `$r^{*}$` 撞车 → 用私有区占位符 `\ue000` 在 extract 阶段区分，不要 build 阶段全局替换 `*`；⑤`^{[^id]}` 是**行内公式里嵌了脚注引用**，必须还原成 `[^id]`（pandoc 报 `Note with key ... defined but not used` 就是它）
  - 双归属 → **M7**（差异清单里的版式阈值属 M7）

## 来自「尾注（附注）制 + 跨册合订（本册无注释文本）」

- **判定用户给的扫描件是上册还是下册**：把两个候选 PDF 同一页号渲染成左右拼接图（ffmpeg `hstack` + `drawtext` 标 LEFT/RIGHT），一次 vision 提问「左右分别是什么章节、页码」即可（本案例据此确认 部分1=上册 / 部分2=下册 / 部分3=附注）。比逐页 OCR 猜测快得多。

## 来自「中译本教科书·单册拆多文件（`title` 自带 level + 图题被拆散 + 书…」

- **分卷图包解压会多一层目录**：`7z x -o images images.zip` 可能解出 `images/images/*.jpg`，要 `mv images/images/* images/` 摊平，否则 `![](images/xxx.jpg)` 全部 missing（build 前先跑一次「引用到的文件名 vs images/ 实有」集合差）
- 触发：5 个左右 layout.json **按页连续切分**（本例 200/200/200/200/64 页）、`title` 块**自带 `level` 字段**（1=编/章/前置章节，2=小节）、`chart`/`image` 块题注在子块 `chart_caption`/`image_caption`、`table` 块的 HTML 在 `table_body`、书前有**多页 OCR 目录**、书末有「专业术语表 / 索引 / 译后记」

## 来自「多文档合并（同一本书分多个 layout.json）」

- 每部分独立跑 extract/build（tag 前缀区分：第一部分 `pXX-N`，第二部分 `p2-XX-N`）
- 合并：正文区拼接 + 脚注区拼接（去重）；注意：
  - 第二部分封面标题去掉，从 `---` 后开始接
  - 两个 `## 脚注` 区合并为一个
  - 层级修复（如 `## C. 尺度` → `### C. 尺度`，与第一部分同级）
  - 标题上的脚注引用（如 `# 第一版序言[^p15-1]`）移到正文首段，否则删标题时引用丢失
  - 合并后统一补标题前后空行（pandoc TOC 识别）
- 验证：§ 跨部分连续无缺失（如 §1-244）、脚注总数 == 两部分之和

## 来自「逐节讲解+注释（圈码脚注，每节重新编号）」

- **用户重新上传的文件 md5 可能全变**：第二套文件（doc_756a5d6126cc / doc_342945bdff38 / doc_e9818afeca4e）与旧案例文件 md5 全不同、P3 页数也不同（10→8 页）——必须重新探索、重新 extract，不能复用旧 pages.json；旧参考文件里的源文件名已过时

## 来自「陷阱」

- **教科书类任务第一步就导出图片清单发给用户**：layout.json 只给哈希名，图永远不在本机，用户找图/传图是最长的外部等待。先把唯一 `image_path` 列成清单发出去（顺带说明「放哪、怎么压」），再回头跑 extract/build——本次把索图留到最后，结果 build 全绿却交付不了。
- **工作目录含 PDF 二进制时 terminal 命令报 "embedded null byte"**：Hermes 生命周期守卫会扫描命令引用的脚本/目录，遇到 PDF 等二进制文件抛 `ValueError: embedded null byte`（exit -1）。绕过：用 execute_code 的 `subprocess.run([...])` 跑命令，或把 PDF 移到独立目录（如 /tmp/enpdf/）再操作

## 来自「章末注释（prose 类书籍，无 § 结构）」

- **跨文件续章**：正文分多个 layout.json 时，续章页区间（如 P2 p0-14 → 第5章、P3 p0-6 → 第9章）须在 chapter_of() 特判，不能只靠页区间
