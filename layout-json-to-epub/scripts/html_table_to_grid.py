#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""layout.json 的 table 块（span 里的 raw HTML）→ pandoc grid table。

用法：
    python3 html_table_to_grid.py table.html        # 文件
    cat table.html | python3 html_table_to_grid.py   # stdin
    from html_table_to_grid import html_table_to_grid, grid_to_md, merge_split_tables

要点：
- 展开 rowspan / colspan（layout 的表头合并格很多，不展开列会错位）
- 若首列是全表重复的表题（rowspan 覆盖整表），整列删除，题注另行加粗输出
- 输出 pandoc grid table（不是 pipe table）：**列宽必须按显示宽度算**（CJK 占 2 列），
  用 len() 会让中文溢出到相邻列、pandoc 把整行拆成残片；grid table 在 pandoc 里最稳，
  且支持多行单元格
- 单元格里的 `<eq>x</eq>` → `$x$`；裸 `<`（`Y<C+I+G`）必须转义，否则被当标签吃掉
- 跨页被切成两张表（表头重复）→ `merge_split_tables(book_md)` 在 build 末尾调一次
- 表格单元格里的 `[^id]` 脚注不会被 pandoc 解析（raw HTML 也不解析）→ 表格注要用
  HTML 锚点 `<a href="#tn..."><sup>&#42;</sup></a>`，见 SKILL.md「陷阱」一节
"""
import re
import sys
from html.parser import HTMLParser

CAP_RE = re.compile(r'^(图|表)\s?\d+\s?-\s?\d+')

# 单元格里合法的 HTML 标签；不在名单里的 `<` 一律当普通字符转义
KNOWN_TAG = re.compile(
    r'<(?!/?(?:table|tbody|thead|tfoot|tr|td|th|caption|br|p|span|div|i|b|em|'
    r'strong|sup|sub|img|eq)\b)', re.I)


class _TParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cur, self.cell, self.buf = [], None, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'tr':
            self.cur = []
        elif tag in ('td', 'th'):
            self.cell = {'rowspan': int(a.get('rowspan', 1) or 1),
                         'colspan': int(a.get('colspan', 1) or 1), 'text': ''}
            self.buf = []
        elif tag == 'br':
            self.buf.append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.cell['text'] = re.sub(r'\s+', ' ', ''.join(self.buf)).strip()
            if self.cur is not None:
                self.cur.append(self.cell)
            self.cell, self.buf = None, []
        elif tag == 'tr' and self.cur is not None:
            self.rows.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cell is not None:
            self.buf.append(data)


def html_table_to_grid(html, drop_caption_col=True):
    """返回二维 list[str]（已展开合并格）；解析不出返回 None"""
    if not html or '<table' not in html.lower():
        return None
    # ① 单元格里的 <eq>公式</eq> 要转成 $...$，否则 HTMLParser 直接丢掉标签只留文字
    html = re.sub(r'<eq>(.*?)</eq>', lambda m: '$%s$' % m.group(1).strip(),
                  html, flags=re.S)
    # ② 单元格里的裸 `<`（如 `Y<C+I+G`）会被当标签开头吃掉整段，先转义。
    #    只放过白名单标签，其余 `<` 一律 &lt;
    html = KNOWN_TAG.sub('&lt;', html)
    p = _TParser()
    try:
        p.feed(html)
    except Exception:
        return None
    rows = [r for r in p.rows if r]
    if not rows:
        return None

    grid, pending = [], {}
    for r in rows:
        cells, ci = [], 0
        it = iter(r)
        while True:
            while (len(grid), ci) in pending:
                cells.append(pending.pop((len(grid), ci)))
                ci += 1
            try:
                c = next(it)
            except StopIteration:
                break
            cells.append(c['text'])
            for dr in range(c['rowspan']):
                for dc in range(c['colspan']):
                    if dr or dc:
                        pending[(len(grid) + dr, ci + dc)] = c['text']
            ci += c['colspan']
        while (len(grid), ci) in pending:
            cells.append(pending.pop((len(grid), ci)))
            ci += 1
        grid.append(cells)

    ncol = max(len(r) for r in grid)
    for r in grid:
        r.extend([''] * (ncol - len(r)))

    # 首列全表重复的题注（rowspan 覆盖整表）→ 删列
    if drop_caption_col and grid and grid[0] and CAP_RE.match(grid[0][0] or ''):
        first = grid[0][0]
        if all(r[0] == first for r in grid):
            for r in grid:
                r.pop(0)
            ncol -= 1

    grid = [r for r in grid if any(c.strip() for c in r)]
    if not grid or ncol < 1:
        return None
    return grid


def dw(s):
    """显示宽度：CJK/全角字符占 2 列。grid table 的列宽必须按显示宽度算——
    用 len() 会让中文单元格溢出到相邻列，pandoc 把整行拆错，输出
    `<td>| 实</td><td>际GDP | 模型</td>` 这种残片（曼昆 11 版「关键概念」实测）。"""
    import unicodedata
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
    return w


def grid_to_md(grid):
    """二维 list → pandoc grid table 文本（列宽按显示宽度，中文对齐）"""
    ncol = max(len(r) for r in grid)
    w = [3] * ncol
    for r in grid:
        for i, c in enumerate(r):
            w[i] = max(w[i], dw(c) + 2)
    sep = '+' + '+'.join('-' * w[i] for i in range(ncol)) + '+'
    out = [sep]
    for r in grid:
        cells = []
        for i in range(ncol):
            c = r[i] if i < len(r) else ''
            cells.append(' ' + c + ' ' * (w[i] - 1 - dw(c)))
        out.append('|' + '|'.join(cells) + '|')
        out.append(sep)
    return '\n'.join(out)


def merge_split_tables(md):
    """跨页续表合并：同一张表被页边界切成两个 grid table、表头重复 → 合成一个。

    只合并「两表之间除空行外别无他物 + 表头去空格后完全相同」的相邻表。
    **不能只删掉第二个表头两行**——两张表各自 padding 宽度不同，删完就是非法 grid
    table（pandoc 静默降级成一段文本）。必须用 grid_to_md 按统一列宽重新渲染。
    """
    TB = re.compile(r'(?m)^\+[-+]+\+\n(?:\|.*\|\n\+[-+]+\+\n?)+')

    def rows_of(txt):
        return [[c.strip() for c in l.strip().strip('|').split('|')]
                for l in txt.split('\n') if l.startswith('|')]

    blocks = list(TB.finditer(md))
    merged = []
    for a, b in zip(blocks, blocks[1:]):
        if md[a.end():b.start()].strip() != '':
            continue
        ra, rb = rows_of(a.group(0)), rows_of(b.group(0))
        if ra and rb and ra[0] == rb[0]:
            merged.append((a.start(), a.end(), ra + rb[1:]))
    if not merged:
        return md
    res, pos = [], 0
    for s, e, rows in merged:
        res.append(md[pos:s])
        res.append(grid_to_md(rows))
        pos = e
    res.append(md[pos:])
    return ''.join(res)


def main():
    src = open(sys.argv[1], encoding='utf-8').read() if len(sys.argv) > 1 else sys.stdin.read()
    grid = html_table_to_grid(src)
    if not grid:
        print('*〔表格：未能解析〕*')
        return 1
    print(grid_to_md(grid))
    return 0


if __name__ == '__main__':
    sys.exit(main())
