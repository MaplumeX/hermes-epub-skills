#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 book.md 里「图片 ↔ 图题」的配对是否正确。

为什么不用「图后紧跟不是图题」这种逐图片判据：
多面板图组本来就是「图 → 另一张图 → … → 图题」，按图片数会得出一堆假异常（实测 224 张图里 28 个假异常，真异常 0）。
正确口径：把连续的 img/panel 块算作**一个图组**，取组后第一个 `**图X-Y …**` 作为该组图题，然后查：
  1. 图题顺序单调递增（按 (章, 图号)）
  2. 每章图号 1..N 无缺口
  3. 无图题的图组清单（人工看是不是图标题烘在图内）
  4. 图题重复 / 同图号多标题 / 图题未加粗 / 在图前的图题 / 整段正文被当图题加粗

用法：
    python3 check_figure_pairing.py book.md
    python3 check_figure_pairing.py book.md --epub-dir x/EPUB/text   # 额外查 EPUB 里 img 后第一块

退出码：0 = 全部通过；1 = 有问题（明细打在 stdout）。
"""
import argparse
import glob
import html
import os
import re
import sys
from collections import Counter, defaultdict

IMG = re.compile(r'^!\[\]\(images/([^)]+)\)$')
CAP = re.compile(r'^\*\*(图\s*(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+(.*?))\*\*$')
CAP_ANY = re.compile(r'^\*{0,2}(图\s*(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+(.*?))\*{0,2}$')
PANEL = re.compile(r'^\*\*[（(]\s*[a-fA-F]\s*[）)]')


def groups(blocks):
    """把连续 img/panel 块归为一个图组，返回 [(图数, 图题tuple|None, [hash...])]"""
    out, i = [], 0
    while i < len(blocks):
        if not IMG.match(blocks[i].strip()):
            i += 1
            continue
        j, hashes = i, []
        while j < len(blocks) and (IMG.match(blocks[j].strip()) or PANEL.match(blocks[j].strip())):
            m = IMG.match(blocks[j].strip())
            if m:
                hashes.append(m.group(1))
            j += 1
        cap = None
        if j < len(blocks):
            cm = CAP.match(blocks[j].strip())
            if cm:
                cap = (int(cm.group(2)), int(cm.group(3)), cm.group(4).strip())
        out.append((len(hashes), cap, hashes))
        i = j + 1
    return out


def check_md(path):
    md = open(path, encoding='utf-8').read()
    blocks = md.split('\n\n')
    gs = groups(blocks)
    problems = []

    # 1) 顺序单调
    prev = (0, 0)
    for n, cap, hs in gs:
        if not cap:
            continue
        cur = (cap[0], cap[1])
        if cur <= prev:
            problems.append('图题顺序异常：图%d-%d 出现在 图%d-%d 之后' % (cur + prev))
        prev = cur

    # 2) 每章图号连续
    by_ch = defaultdict(list)
    for n, cap, hs in gs:
        if cap:
            by_ch[cap[0]].append(cap[1])
    for ch in sorted(by_ch):
        nums = by_ch[ch]
        absent = [k for k in range(1, max(nums) + 1) if k not in nums]
        if absent:
            problems.append('第%d章 缺图号 %s' % (ch, absent))

    # 3) 无图题的图组
    nocap = [(n, hs) for n, cap, hs in gs if not cap]

    # 4) 图题文本层面
    all_caps = [CAP.match(b.strip()) for b in blocks]
    all_caps = [m.group(1) for m in all_caps if m]
    dup = [k for k, v in Counter(all_caps).items() if v > 1]
    if dup:
        problems.append('图题重复：%s' % dup[:5])
    loose = []
    for b in blocks:
        s = b.strip()
        m = CAP_ANY.match(s)
        if m and not CAP.match(s):
            loose.append(s[:40])
    if loose:
        problems.append('图题未统一加粗 %d 处：%s' % (len(loose), loose[:5]))
    for i, b in enumerate(blocks):
        s = b.strip()
        if CAP_ANY.match(s) and i + 1 < len(blocks) and IMG.match(blocks[i + 1].strip()):
            problems.append('图题排在图前：%s' % s[:40])
    for b in blocks:
        s = b.strip()
        if s.startswith('**') and s.endswith('**') and '。' in s[2:-2] and len(s) > 60:
            problems.append('整段正文被当图题加粗：%s' % s[:40])

    return gs, problems, nocap


def check_epub(textdir):
    """EPUB 里逐个 <p><img></p> 看其后第一块是不是图题/面板标签。
    多图组里「图后面紧跟另一张图」是正常的，所以只统计「后面是正文文字」的情况。"""
    bad = []
    for f in sorted(glob.glob(os.path.join(textdir, '*.xhtml'))):
        s = open(f, encoding='utf-8').read()
        for m in re.finditer(r'<p>(<img[^>]+/?>)</p>', s):
            tail = s[m.end():m.end() + 600]
            mm = re.match(r'\s*<p>(.*?)</p>', tail, re.S)
            t = html.unescape(re.sub(r'<[^>]+>', '', mm.group(1))).strip() if mm else ''
            if not t:
                continue
            if re.match(r'^图\s*\d{1,2}[-–—]\d{1,2}', t) or re.match(r'^[（(]\s*[a-fA-F]\s*[）)]', t):
                continue
            if '<img' in tail[:80]:
                continue
            bad.append((os.path.basename(f), t[:50]))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('book_md')
    ap.add_argument('--epub-dir', default=None, help='解包后的 EPUB/text 目录')
    args = ap.parse_args()

    gs, problems, nocap = check_md(args.book_md)
    print('图组 %d；有图题 %d；无图题 %d'
          % (len(gs), sum(1 for _, c, _ in gs if c), len(nocap)))
    print('图题总数 %d' % sum(1 for _, c, _ in gs if c))

    if nocap:
        print('\n无图题的图组（人工看：多面板图的标题常烘在图内，不要自己编）:')
        for n, hs in nocap:
            print('   %d 图 %s' % (n, ','.join(h[:8] for h in hs)))

    if args.epub_dir:
        bad = check_epub(args.epub_dir)
        print('\nEPUB 中「图后第一块是正文文字」的 %d 处:' % len(bad))
        for f, t in bad[:15]:
            print('   %s | %s' % (f, t))
        if bad:
            problems.append('EPUB 图后跟正文 %d 处' % len(bad))

    if problems:
        print('\n问题 %d 条:' % len(problems))
        for p in problems:
            print('   -', p)
        return 1
    print('\n全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
