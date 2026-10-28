#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网站书籍 -> EPUB 完整流水线模板（web-to-epub 技能）。

用法：复制本文件到工作目录，只改 CONFIG 区（PAGES_DIR / OUT_EPUB / CHAPTERS / 元数据），
然后:  ./epubenv/bin/python make_epub.py

依赖: pip install ebooklib beautifulsoup4 pillow
已验证: marxists.org 中文文库（GB2312 旧式 HTML、Word 转换页含 VML 公式图）。
"""
import os, re
from bs4 import BeautifulSoup
from ebooklib import epub

# ============ CONFIG — 每次修改这里 ============
PAGES_DIR = "/tmp/book/pages"          # 已下载的 .htm 页面目录
OUT_EPUB = "/tmp/book/书名（作者）.epub"
BOOK_ID = "book-id-zh-0000"            # 唯一标识
BOOK_TITLE = "书名"
BOOK_AUTHOR = "作者 (Author Name)"
BOOK_DESC = "《书名》(Original Title, 年份)，作者著，译者译。中文马克思主义文库电子版整理为 EPUB。"
BOOK_PUBLISHER = "出版社 / 来源站"
BOOK_DATE = "2011"
BOOK_TITLEPAGE_LINES = [               # 标题页行: (文本, 字号class: book/author/meta)
    ("书名", "book"),
    ("〔英〕作者（Author）著", "author"),
    ("译者 译", "meta"),
    ("Original Title（1994）", "meta"),
    ("文本来源：中文马克思主义文库（marxists.org）", "meta"),
]
# 页面顺序与章节标题。标题取页面内 p.title1（若为空用此处 fallback）
CHAPTERS = [
    ("00a", "总序"),
    ("00b", "序言"),
    ("01", "第一章　标题"),
    ("10", "文献目录"),
    ("11", "索引"),
]
# ==============================================

CSS = """
body { font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif; line-height: 1.7; }
h1 { font-size: 1.4em; text-align: center; margin: 1.2em 0 0.8em; }
h2 { font-size: 1.15em; text-align: center; margin: 1.5em 0 0.6em; }
p { text-indent: 2em; margin: 0.4em 0; }
p.noindent { text-indent: 0; }
.footnotes { font-size: 0.85em; border-top: 1px solid #999; margin-top: 2em; padding-top: 0.5em; }
.footnotes p { text-indent: 0; margin: 0.3em 0; }
sup { font-size: 0.7em; }
img { max-width: 100%; height: auto; }
p img { display: block; margin: 0.6em auto; }
.titlepage { text-align: center; }
.titlepage .book { font-size: 1.6em; font-weight: bold; margin: 2em 0 0.5em; }
.titlepage .author { font-size: 1.1em; margin: 1em 0; }
.titlepage .meta { font-size: 0.95em; color: #555; margin: 0.3em 0; }
"""

def decode_page(filename):
    """GB2312 旧站解码；fallback 链 gb2312 -> gb18030 -> utf-8。"""
    raw = open(os.path.join(PAGES_DIR, filename + ".htm"), "rb").read()
    for enc in ("gb2312", "gb18030", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")

def preprocess(html_text):
    """Word/mso 遗留的 VML 与条件注释。顺序关键，见 SKILL.md §5。
    公式页有双份: VML <v:imagedata>(png) + fallback <img>(gif)，只保留 imagedata 版。"""
    # (a) 先整块删除 <![if !vml]>...<![endif]>（fallback img 版）——必须先做，
    #     泛化 <![if...> 正则会把中间的 imagedata 一起吞掉
    html_text = re.sub(r"<!\[if !vml\][^>]*>.*?<!\[endif\]>", "", html_text, flags=re.DOTALL)
    # (a2) 去掉 <!--[if gte vml 1]> 注释包装，让内部 VML 暴露
    html_text = re.sub(r"<!--\[if gte vml 1\]>", "", html_text)
    # (b) VML imagedata -> img（src 取本地 basename）
    html_text = re.sub(
        r"<v:imagedata[^>]*src=[\"']([^\"']*)[\"'][^>]*/?>",
        lambda m: f'<img src="{os.path.basename(m.group(1))}"/>',
        html_text,
    )
    # (c) 删除条件注释标记本身
    html_text = re.sub(r"<!--\[if[^>]*>", "", html_text)
    html_text = re.sub(r"<!\[endif\]-->", "", html_text)
    html_text = re.sub(r"<!\[if[^>]*>", "", html_text)
    html_text = re.sub(r"<!\[endif\]>", "", html_text)
    # (d) 删除 v:/o:/w:/st1:/st2: 命名空间标签 —— 必须 DOTALL，VML 跨行
    html_text = re.sub(r"</?(?:v|o|w|st1|st2):[^>]*>", "", html_text, flags=re.DOTALL)
    # (e) 删除 img 上的 v:shapes 等非法属性
    html_text = re.sub(
        r"<img[^>]*>",
        lambda m: re.sub(r"\s+v:shapes=[\"'][^\"']*[\"']", "", m.group(0)),
        html_text,
    )
    # (f) 清掉 Word 遗留的 span lang/style 属性与 mso 类
    html_text = re.sub(r"<span[^>]*>", "<span>", html_text)
    html_text = re.sub(r'<p class="MsoNormal"[^>]*>', "<p>", html_text)
    return html_text

def clean_page(html_text):
    """清理单页 -> (章节标题, [(小节标题, 锚点id)], 正文HTML片段)。"""
    html_text = preprocess(html_text)
    soup = BeautifulSoup(html_text, "html.parser")
    body = soup.body or soup

    # 1. 面包屑导航：第一个 <hr> 之前全部删除
    first_hr = body.find("hr")
    if first_hr:
        for el in list(body.contents):
            if el is first_hr:
                break
            el.decompose()
        first_hr.decompose()

    # 2. 章内目录表格（含 <a href="#..."> 的 table）
    for table in body.find_all("table"):
        if table.find("a", href=re.compile(r"^#")):
            table.decompose()

    # 3. 尾部翻页导航（上一篇/回目录/下一篇）
    for p in body.find_all("p"):
        txt = p.get_text()
        if ("上一篇" in txt or "回目录" in txt or "下一篇" in txt) and "style" in p.attrs:
            p.decompose()
    for hr in body.find_all("hr"):
        rest_txt = "".join(str(s) for s in hr.find_all_next(string=True))
        if "上一篇" in rest_txt or "回目录" in rest_txt or not rest_txt.strip():
            hr.decompose()

    # 4. 章节标题 p.title1（删除元素，后面以 <h1> 输出）
    title_el = body.find("p", class_="title1")
    chapter_title = title_el.get_text(strip=True) if title_el else ""
    if title_el:
        title_el.decompose()

    # 5. 脚注引用: <a name='_ftnrefN' href='#_ftnN'><sup>[N]</sup></a> -> <a href="#ftnN" id="ftnrefN"><sup>[N]</sup></a>
    for a in body.find_all("a", href=False):
        if not a.get_text(strip=True):
            a.decompose()
    for a in body.find_all("a", href=True):
        href = a["href"]
        m = re.match(r"^#_ftn(\d+)$", href)
        if m:
            n = m.group(1)
            sup = a.find("sup")
            if sup is not None:
                sup.clear()
                sup.append(soup.new_string(f"[{n}]"))
            a.attrs = {"href": f"#ftn{n}", "id": f"ftnref{n}"}
            if sup is None:
                a.string = f"[{n}]"
        elif href.startswith("#"):
            a["href"] = "#" + href[1:]

    # 6. 脚注定义: <a name='_ftnN' href='#_ftnrefN'>... -> <a id="ftnN">[N]</a>
    for a in body.find_all("a", href=True):
        m = re.match(r"^#_ftnref(\d+)$", a["href"])
        if m:
            a.attrs = {"id": f"ftn{m.group(1)}"}
            a.string = f"[{m.group(1)}]"

    # 7. h4 -> h2 + id="secN"
    sections = []
    for i, h4 in enumerate(body.find_all("h4")):
        sec_id = f"sec{i+1}"
        h4.name = "h2"
        h4.attrs = {"id": sec_id}
        sections.append((h4.get_text(strip=True), sec_id))

    # 7b. 全局修复所有 img src -> images/<basename>（必须先做，防 <p><center><img> 结构漏改）
    for img in body.find_all("img"):
        src = img.get("src", "")
        img["src"] = f"images/{os.path.basename(src)}"
        img["style"] = "display:block;margin:0.6em auto;"

    # 8. 流式段落化：裸文本+<br> -> <p>；透明容器递归；内联标签保留为节点（勿 str() 化，会转义）
    from bs4 import NavigableString
    TRANSPARENT = ("span", "div", "font", "center")
    INLINE = ("a", "sup", "i", "em", "b", "strong", "u", "cite", "sub", "code", "q", "small", "big")

    def process_container(container):
        blocks = []
        para_nodes = []
        def flush():
            nonlocal para_nodes
            while para_nodes and isinstance(para_nodes[0], NavigableString) and not para_nodes[0].strip():
                para_nodes.pop(0)
            while para_nodes and isinstance(para_nodes[-1], NavigableString) and not para_nodes[-1].strip():
                para_nodes.pop()
            if para_nodes:
                blocks.append(para_nodes)
                para_nodes = []
        for child in list(container.children):
            if isinstance(child, NavigableString):
                if child.strip():
                    para_nodes.append(child)
            elif child.name == "br":
                flush()
            elif child.name in TRANSPARENT:
                sub = process_container(child)
                for b in sub:
                    if isinstance(b, list):
                        flush()          # 透明容器内已是独立段落，必须先 flush
                        para_nodes.extend(b)
                    else:
                        flush()
                        blocks.append(b)
                flush()
            elif child.name in INLINE:
                para_nodes.append(child)
            else:
                flush()
                blocks.append(child)
        flush()
        return blocks

    blocks = process_container(body)
    for el in list(body.contents):
        el.extract()
    for b in blocks:
        if isinstance(b, list):
            p = soup.new_tag("p")
            for node in b:               # append 节点，勿用 p.string = html 字符串
                p.append(node)
            body.append(p)
        else:
            body.append(b)

    # 9. 脚注区：第一个含 <a id="ftnN"> 的段落起，所有后续兄弟包进 .footnotes div
    fn_first = body.find("a", id=re.compile(r"^ftn\d+$"))
    if fn_first:
        fn_start = fn_first.find_parent("p")
        if fn_start:
            fn_div = soup.new_tag("div")
            fn_div["class"] = "footnotes"
            to_move = []
            node = fn_start
            while node is not None:      # 先收集再 extract
                to_move.append(node)
                node = node.find_next_sibling()
            for el in to_move:
                fn_div.append(el.extract())
            body.append(fn_div)

    # 10. 清理残留
    for p in body.find_all("p"):
        if not p.get_text(strip=True) and not p.find("a"):
            p.decompose()
    fn_div = body.find("div", class_="footnotes")
    if fn_div is not None:
        hr = fn_div.find_previous_sibling("hr")
        if hr is not None:
            fn_div.insert(0, hr.extract())
    for hr in body.find_all("hr"):
        hr.decompose()

    inner = "".join(str(c) for c in body.contents)
    return chapter_title, sections, inner

def build():
    book = epub.EpubBook()
    book.set_identifier(BOOK_ID)
    book.set_title(BOOK_TITLE)
    book.set_language("zh-CN")
    book.add_author(BOOK_AUTHOR)
    book.add_metadata("DC", "description", BOOK_DESC)
    book.add_metadata("DC", "publisher", BOOK_PUBLISHER)
    book.add_metadata("DC", "date", BOOK_DATE)

    cover_path = os.path.join(os.path.dirname(OUT_EPUB), "cover.jpg")
    if os.path.exists(cover_path):
        book.set_cover("cover.jpg", open(cover_path, "rb").read())

    # 图片资源
    img_files = [f for f in os.listdir(PAGES_DIR) if f.lower().endswith((".png", ".gif", ".jpg", ".jpeg"))]
    for f in sorted(img_files):
        ext = os.path.splitext(f)[1].lower().lstrip(".")
        mime = {"png": "image/png", "gif": "image/gif", "jpg": "image/jpeg", "jpeg": "image/jpeg"}[ext]
        item = epub.EpubItem(uid=f"img-{f}", file_name=f"images/{f}",
                             media_type=mime, content=open(os.path.join(PAGES_DIR, f), "rb").read())
        book.add_item(item)
    print(f"  图片资源: {len(img_files)} 个")

    # 标题页
    title_page = epub.EpubHtml(title="书名页", file_name="title.xhtml", lang="zh-CN")
    tp = ['<html xmlns="http://www.w3.org/1999/xhtml"><head><title>书名页</title>',
          '<link rel="stylesheet" type="text/css" href="style.css"/></head><body><div class="titlepage">']
    for text, cls in BOOK_TITLEPAGE_LINES:
        tp.append(f'<p class="{cls}">{text}</p>')
    tp.append('</div></body></html>')
    title_page.content = "\n".join(tp)
    book.add_item(title_page)

    # 章节
    parsed = []
    chapters_items = []
    for filename, fallback_title in CHAPTERS:
        html_text = decode_page(filename)
        chapter_title, sections, inner = clean_page(html_text)
        title = chapter_title or fallback_title
        file_name = f"chap_{filename}.xhtml"
        # 注意: 不要加 <?xml ...?> 声明 —— ebooklib/lxml 会报错（见 SKILL.md Pitfalls）
        content = f"""<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head><body>
<h1>{title}</h1>
{inner}
</body></html>"""
        item = epub.EpubHtml(title=title, file_name=file_name, lang="zh-CN")
        item.content = content
        book.add_item(item)
        chapters_items.append(item)
        parsed.append((file_name, title, sections))

    # 静态目录页（章 + 节两级）
    toc_html = ['<html xmlns="http://www.w3.org/1999/xhtml"><head><title>目录</title>',
                '<link rel="stylesheet" type="text/css" href="style.css"/></head><body><h1>目录</h1>']
    for file_name, title, sections in parsed:
        toc_html.append(f'<p class="noindent" style="margin-top:0.8em"><a href="{file_name}"><b>{title}</b></a></p>')
        for sec_title, sec_id in sections:
            toc_html.append(f'<p class="noindent" style="margin-left:2em"><a href="{file_name}#{sec_id}">{sec_title}</a></p>')
    toc_html.append('</body></html>')
    toc_page = epub.EpubHtml(title="目录", file_name="toc.xhtml", lang="zh-CN")
    toc_page.content = "\n".join(toc_html)
    book.add_item(toc_page)

    # CSS
    style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=CSS)
    book.add_item(style)

    # 结构化 TOC（导航）：书名页 + 章(含节子项)
    struct_toc = [epub.Link("title.xhtml", "书名页", "title")]
    for file_name, title, sections in parsed:
        sub_links = [epub.Link(f"{file_name}#{sid}", st, f"{file_name}-{sid}") for st, sid in sections]
        if sub_links:
            struct_toc.append((epub.Section(title, href=file_name), tuple(sub_links)))
        else:
            struct_toc.append(epub.Link(file_name, title, file_name))
    book.toc = struct_toc

    # Spine：书名页 -> 目录 -> 各章
    book.spine = ["nav"] + [title_page, toc_page] + chapters_items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(OUT_EPUB, book, {})
    print("EPUB written:", OUT_EPUB, os.path.getsize(OUT_EPUB), "bytes")

if __name__ == "__main__":
    build()
