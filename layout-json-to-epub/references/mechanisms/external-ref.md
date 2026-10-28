# M10 外部参照（英文原文、扫描页、术语）

> **什么时候读**：要从原扫描页读回上标、对照英文原版补标记、校对德文术语或希腊字母时。
>
> **相关脚本**：`scripts/read_marks_from_scan.py`、`scripts/read_marks_from_scan.py`

> 本篇内容自 SKILL.md 拆出，条目逐字保留（含实测数字与原节出处）。

## 相关篇

> 一条结论常跨两个机制：**正文只在主归属那篇写一份**，这里只放指针。

- **M3** —— 补回缺失标记（英文原文/DJVU/扫描页三条路径）
- **M7** —— 德文标题结构提取与层级判定

## 来自「尾注（附注）制 + 跨册合订（本册无注释文本）」

- **英文原书对不上版本时，编号不可搬运**：用户给的「英文原文」可能是**另一版**（本例中译据 1982 年第 1 版，用户给的是 2010 年第 4 版，且改成了页底脚注）。实测编号偏移（中译第7章注10=英文注13、第13章注3=英文注14…）。可用做法：先做**中英附注对照表**（引证前缀在英文文本里的命中次数），再按「英文句子内容 → 中文同义句」逐条定位；**绝不能按编号直接搬**。
- **拿到扫描页后怎么读上标（vision 路线）**：`pdftoppm -f <页> -l <页> -r 300 -png book.pdf p`（上标是小字号，≥200–300 dpi）→ `vision_analyze(image_url=<png>, question="这句话末尾引号后的上标数字是几？")`；整页定位后用 `region=[x1,y1,x2,y2]` **按原图像素裁剪（缩放前生效）** 放大只读那一处。机制：vision_analyze 是**转交**型工具——图片编码为 base64 data URL，交给 Hermes 辅助模型路由（`agent/auxiliary_client.py`）中的**多模态模型**，回给主模型的是文字，所以主模型是纯文本也能用。auto 解析顺序：主 provider（若本身是受支持的视觉后端）→ OpenRouter → Nous Portal → 原生 Anthropic → 自定义 endpoint（Qwen-VL/LLaVA/Pixtral）→ None；配置在 config.yaml `auxiliary.vision.{provider,model,base_url,api_key}`（另有 timeout 120s / download_timeout 30s / max_concurrency）。**上标读不准时不要换主模型**，单独给 vision 换更强的 VL 模型：`hermes config set auxiliary.vision.provider openrouter` + `hermes config set auxiliary.vision.model <id>`。SVG/BMP/TIFF 会先被栅格化。**读不清就报「读不清」，不许猜数字**（与上一条「宁缺勿错」同一原则）。
  - 双归属 → **M3**（读回上标之后仍要按 M3 配对与建链）

## 来自「陷阱」

- **扫描件缺 § 标题**：据原版（德文）补入，正文残句归位

## 来自「德文术语校对（对照 1830 原文）」

- hegel-system.de/de/enz0.htm（§1-18）、enz1.htm（§19-244）有 1830 版《哲学科学百科全书》全文
- zeno.org 走 HTTP 会被拦、Wikisource 页面为空 —— 用 hegel-system.de
- 按 § 编号对齐比对括号内术语；变音容错（ä→ae 等）；相邻 §±2 放宽
- 已发现案例：Akosmimus→Akosmismus（漏字母）、denk-ende→denkende（断行连字符误读）、terminus meidus→medius（§190）、Entge-gensetzung→Entgegensetzung（断行连字符）
- **未匹配≠错误**：hegel-system.de 无口授附释（Zusätze），附释中术语（~30 个/部分）无法比对，凭德语知识判断；只修正文中的未匹配
- 检查脚本：check_terms.py（可复制改造）——解析德文 § 区间 → 提取中文括号术语 → fuzzy_in 比对（大小写/去连字符/变音 unify）

## 来自「希腊字母 OCR 检查」

- 全书扫描 `[α-ωΑ-Ωάέήίόύώ]` 出现位置；重点核查：
  - **编号序列**：α) β) γ) δ) 应按逻辑递增（§23 "8)" 是 δ 被识别成数字 8）
  - **希腊引文完整性**：对照希腊语原文（§88 德谟克利特引文 ἐσί 缺 στ→ἐστίν；§236 亚里士多德 νόησις νοήσεως 中 ν 被识别成拉丁 v + 缺空格）
  - **拉丁/希腊混排**：v→ν、o→ο、p→ρ、拉丁字母紧跟希腊字母
  - **LaTeX 转义残留**：OCR 可能把希腊字母识别成 `\alpha`/`\beta`/`\gamma`（字面反斜杠+命令名，18 处案例：1 处标题 `\gamma) 根据(Der Grund)` → `γ) 根据`，17 处正文列举编号 `\alpha  )` → `α)`）。扫描正则 `r'\\[a-zA-Z]+\s*\)?'` 全书检索；修复 `re.sub(r'\\\\(alpha|beta|gamma)\s*\)?\s*', lambda m: {'alpha':'α','beta':'β','gamma':'γ'}[m.group(1)] + ') ', t)`；对照德文原文验证编号是希腊字母还是拉丁字母（德文站转写 ß 代表 β，a) 代表 α)）
- 德文源无希腊文（附释），凭希腊语知识判断

## 来自「英文版核对（marxists.org Wallace 译本）」

- 目录：marxists.org/reference/archive/hegel/works/sl/slconten.htm → 18 个章节页（slintro/slbeing/slquant/slactual/... 编码 latin-1）
- 英文版有 197 处单词级 `<strong>`（原书黑体强调，如 §87 matter、§88 Being、§79 notions），§ 标题加粗 21 处为网站样式
- 德文源 hegel-system.de 纯文本无加粗

## 来自「OCR 标记缺陷修复（对照英文原文，用户要求）」

- **第二步：获取英文原文**（archive.org 需登录 401，用 libgen）：
  - libgen.li 搜索 → edition.php?id=... → 页面含 IPFS 链接和 `get.php?md5=...`（需先访问 get.php 拿 `&key=...` 再下载）
  - **DJVU 版文本层可能保留上标**（本案例第1-4章有、第5-10章无）：`apt-get install djvulibre-bin` 后 `djvutxt en.djvu en.txt`
  - PDF 版（pymupdf 提取）上标通常丢失，仅作语义参考
  - PEP 668 环境：`python3 -m venv .venv && .venv/bin/pip install pymupdf`
- **第四步：中文定位插入**：英文上下文 → 找中文译文对应句子（人名/引文/关键词，如 "commensurating vocabulary"→"通约的词汇表"）→ 在句末插入 `[[MARK:N]]` 并追加到 marks 列表
