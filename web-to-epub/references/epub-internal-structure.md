# EPUB 内部结构规范(标准格式细节)

EPUB 本质是一个 **ZIP 压缩包**,通过规范文件组织书籍内容。本节是跨项目通用的格式规范参考(不绑定某个具体管线),回答"章节怎么拆、脚注怎么做、文件怎么组织"这类格式层问题。

## 顶层结构

```
book.epub
└── mimetype                  # 必须第一个出现、且不压缩,内容固定 application/epub+zip
├── META-INF/
│   └── container.xml         # 告诉阅读器 opf 文件在哪
├── OEBPS/  (或任意名,被 container.xml 引用)
│   ├── content.opf           # 元数据 + 内容清单 + 阅读顺序(核心之一)
│   ├── toc.ncx (EPUB2)       # 旧版导航
│   ├── nav.xhtml (EPUB3)     # 新版导航文档(必需)
│   ├── chapter1.xhtml ...    # 正文内容
│   ├── styles/               # CSS
│   ├── images/               # 图片
│   └── fonts/                # 内嵌字体
```

三个必成对遵守的约束:
1. **mimetype 必须放 ZIP 首位且不压缩**,文件名全小写,无签名/魔数前缀。打包工具若按目录遍历顺序或压缩了它,EPUB 会损坏。
2. `container.xml` 的 `full-path` 指向 opf 的实际位置(目录名可任意,不一定叫 OEBPS)。
3. opf 的 `manifest` 必须列出**全书所有文件**,漏一个阅读器就打不开那个资源。

## 关键文件

### META-INF/container.xml
```xml
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
```

### content.opf —— 三段
- `<metadata>`:Dublin Core 词汇(title/creator/language/identifier/publisher/date…);EPUB3 加 `<meta name="cover" content="cover-image"/>` 声明封面,`meta property="dcterms:modified"` 修订号。
- `<manifest>`:**全书所有文件清单**,每个 item 有 `id`/`href`/`media-type`。
- `<spine>`:阅读顺序。`<itemref idref="..."/>` 按序指向 manifest 里的内容文件。`linear="no"` 表示非正文序列(前页/附录/版权页),阅读器可能跳过其分页但不丢资源。

## 章节拆分与标识

### 拆分粒度
- 每个"阅读单元" = 一个 XHTML 文件,通常一章,可细到节/粗到部分(part/volume)。reflow 排版下文件边界即重排单元。
- 分卷/分部可独立成 part 文件。

### 两层"目录"体系(极易混淆)
1. **文档内结构(HTML 语义层)**:`<h1>卷</h1> <h2>章</h2> <h3>节</h3>`。决定阅读器目录缩进。
2. **文件级结构(OPF 层)**:spine 决定阅读顺序,manifest 项 = 物理文件。

**关键坑**:正文 `<h2>` 层级与 nav 目录层级是**两个独立系统,不会自动同步**。手动保证"正文标题层级 == nav 目录层级",否则阅读器跳转错乱。pandoc `--toc` 是从 markdown 标题自动同步的,但手工建 EPUB 时必须自己对齐。

**实际症状**:第三方转换器产物常见"正文标题整齐、toc.ncx 只有章一级"或"目录条目指向兄弟节点"。要**逆向把已有标题同步进导航**时,按 `epub-toc-rebuild.md` 的流程做(补 id → 层级栈建树 → 重写 ncx → 修书内目录页 → `scripts/epub_toc_audit.py` 校验)。

顺带一层容易漏的目录:**书内那几页手写的"目录"页**(`class="contents-chapter-N"`)是第三套链接,和 nav 各自独立。用户点的是它,所以它也必须逐条指向正确锚点。

### 锚点定位
章节文件给需要定位的元素(句子/小节/aside)加全局唯一 `id`:
```xml
<section id="sec-1-3"><h3>第三节</h3>...</section>
```
全书 id 唯一,跨文件跳转靠 `href="file.xhtml#id"`,同文件内 `href="#id"`。

## 脚注(footnote)做法

EPUB 对脚注有官方推荐写法,但阅读器兼容性差异大(尤其中文 app)。两种主流方案:

### 方案一:脚注放在章节末尾(最稳,兼容最好)
```xml
<p>正文<sup id="fn1-ref"><a href="#fn1">[1]</a></sup>继续...</p>

<!-- 章末脚注区 -->
<aside id="fn1" epub:type="footnote">
  <p>脚注/译注内容。</p>
</aside>
```
- `aside` = 语义化脚注容器;`epub:type="footnote"` = EPUB3 语义标记(阅读器可浮出预览)。

### 方案二:独立 footnotes.xhtml 文件(iBooks 支持好)
正文跨文件跳转:
```xml
<a epub:type="noteref" href="footnotes.xhtml#fn1">[1]</a>
```

### 严格双向跳转(正文↔脚注↔回正文)
"双向"= 正文能到脚注、脚注还能**回来**:
```xml
<!-- 正文 -->
<sup id="fn1ref"><a epub:type="noteref" href="#fn1">[1]</a></sup>

<!-- 脚注区 -->
<aside id="fn1" epub:type="footnote">
  <a href="#fn1ref">↩返回</a>
  <p>译注内容...</p>
</aside>
```
fn1ref(正文锚)→fn1(脚注锚)→fn1ref(返回锚),三个 id 一一对应,缺一个就成死链。本项目黑格尔译著 70 条星号译注正是此模型。

### epub:type 语义值
- `noteref`:脚注引用处
- `footnote`:脚注本体
EPUB2 无此属性,只能靠裸 `<a>` 模拟。

## 高频踩坑清单
1. **脚注文件务必加进 manifest**,否则阅读器打不开。
2. **EPUB3 下 ncx 可选但 nav.xhtml 必需**;旧工具只生成 ncx → 新阅读器目录空白。
3. **跳转锚点全用 `id`,不要靠 CSS class** 做目标。
4. **跨文件 href 路径相对 opf 所在目录**(实际相对引用该链接的当前文件目录),文件嵌套子目录时易写错相对路径。
5. **epubcheck 验证**:每个 `href` 目标必须存在,否则报错。
6. **manifest/spine 的 id 引用**:spine 的 itemref idref 值必须能匹配 manifest 里的 item id(严格字符一致,含 `_xhtml` 之类后缀)。

## 版本差异速查 (EPUB2 vs EPUB3)
| 项 | EPUB2 | EPUB3 |
|---|---|---|
| 内容文件 | XHTML 1.1 | HTML5 / XHTML5 |
| 必选导航 | toc.ncx | nav.xhtml(ncx 可选) |
| 音视频/脚本 | 受限 | 原生支持 |
| 固定版式/CSS 分页 | 无 | 支持 |
| 语义标记 | 无 | epub:type(footnote/noteref 等) |

## 验证方式
- zipfile 遍历核对 mimetype 首位未压缩(脚本层)。
- `xml.etree.ElementTree.fromstring` 逐个解析 xhtml/opf/ncx,揪 mismatched tag(pandoc/ebooklib 常 exit 0 不报但内部 XML 坏死)。
- 渲染后统计:正文脚注链接数 == 脚注定义数;所有 `href="#id"` 与 `href="file#id"` 目标解析后存在且 id 存在。
