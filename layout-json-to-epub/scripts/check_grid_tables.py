#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 book.md 里的 pandoc grid table 是否合法（在 pandoc 之前跑，比解包 EPUB 快）。

用法：python3 check_grid_tables.py book.md

能抓到三类真实翻车（曼昆 11 版实测）：
1. 列宽不足 → 行内 `|` 数多于分隔线 `+` 数（中文按 1 列算宽就会这样，
   pandoc 会把整行拆成残片，而不是报错）
2. 同行各列 `|` 位置与分隔线不对齐（`+` 不在同一列）
3. 两张表紧邻且表头重复 = 跨页续表没合并
退出码：0 全绿；1 有问题（逐条打印）。
"""
import re
import sys
import unicodedata

SEP = re.compile(r'^\+[-+]+\+$')
ROW = re.compile(r'^\|.*\|$')


def dw(s):
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def main(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    bad = 0
    i = 0
    tables = []
    while i < len(lines):
        if not SEP.match(lines[i].strip()):
            i += 1
            continue
        start = i
        cols = [m.start() for m in re.finditer(r'\+', lines[i])]
        i += 1
        while i < len(lines) and (ROW.match(lines[i].strip()) or SEP.match(lines[i].strip())):
            ln = lines[i].rstrip()
            if ROW.match(ln.strip()):
                bars = [m.start() for m in re.finditer(r'\|', ln)]
                if bars != cols:
                    bad += 1
                    print('行宽不对齐 @line %d' % (i + 1))
                    print('   分隔线 %s' % cols)
                    print('   本行   %s' % bars)
                    print('   %s' % ln[:160])
            i += 1
        tables.append((start, i))
    # 跨页续表：两表之间只有空行 + 表头相同
    for (s1, e1), (s2, e2) in zip(tables, tables[1:]):
        if any(x.strip() for x in lines[e1:s2]):
            continue
        h1 = lines[s1 + 1]
        h2 = lines[s2 + 1]
        if h1 == h2:
            bad += 1
            print('跨页续表未合并 @line %d / %d' % (s1 + 1, s2 + 1))
            print('   %s' % h1[:120])
    print('表格 %d 个，问题 %d 处' % (len(tables), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'book.md'))
