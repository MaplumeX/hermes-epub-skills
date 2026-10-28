#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""book.md 里的每个 grid table 单独喂 pandoc 做硬校验。

比 check_grid_tables.py 更贴近成品：只看 pandoc 实际渲染结果。

用法: python3 check_tables_pandoc.py book.md
退出码非 0 就回去修 build（grid_md / html_table_to_grid）。

三道判据：
  1. 能渲染出 <table>      —— 否则被 pandoc 静默降级成文本
  2. 每行 <td> 数一致      —— ragged 行说明列宽/分隔线错位
  3. 剥标签后无 '|' 残留   —— 说明单元格溢出到相邻列
"""
import re
import subprocess
import sys


TABLE_RE = re.compile(r'(?:^\+[-+]+\+\n(?:\|.*\|\n|\+[-+]+\+\n)+)', re.M)


def check(md_path):
    md = open(md_path, encoding='utf-8').read()
    tables = TABLE_RE.findall(md)
    bad = []
    for i, tbl in enumerate(tables, 1):
        r = subprocess.run(
            ['pandoc', '-f', 'markdown', '-t', 'html'],
            input=tbl, capture_output=True, text=True)
        html = r.stdout
        if '<table' not in html:
            bad.append((i, 'not rendered as table', tbl.splitlines()[0][:60]))
            continue
        rows = re.findall(r'<tr.*?</tr>', html, re.S)
        counts = [len(re.findall(r'<t[dh]', row)) for row in rows]
        if len(set(counts)) > 1:
            bad.append((i, 'ragged rows', counts))
        plain = re.sub(r'<[^>]+>', '', html)
        if '|' in plain:
            bad.append((i, 'pipe leaked into cell text', plain.strip()[:80]))
        if '<pre>' in html or '<code>' in html:
            bad.append((i, 'degraded to pre/code', ''))
    print('tables: %d, problems: %d' % (len(tables), len(bad)))
    for item in bad:
        print('  ', item)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else 'book.md'))
