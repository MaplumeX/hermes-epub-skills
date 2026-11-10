#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_text_fidelity.py — 源网页 vs 成品 EPUB 的正文/脚注/链接保真校验。

用法：
    python verify_text_fidelity.py --epub 书.epub --pages pages \\
        --map 011=chap_011.xhtml --map 012=chap_012.xhtml ...

对每个映射对：
  1) 从源页面抽正文（去掉面包屑即第一个 <hr> 之前、p.title1、注释区标记与 _ftn/_ftnref 锚点），
     从 EPUB 章节抽正文（去掉自加的 <h1>、“注释”题头、脚注锚点），两边都去标签/实体/空白；
  2) 做 **25 字窗口双向比对**：仅源有 / 仅 EPUB 有的窗口数应为 0，否则打印上下文——
     这才是“正文一字不漏、一字不多”的证据；单看字数相等可能互相抵消；
  3) 全书范围统计脚注：正文引用 id=ftnrefN、注释定义 id=ftnN 是否一一对应，内部链接是否都能解析。

注意：新增的章节标题/“注释”题头/脚注编号文字必须在抽正文时剥掉，否则会报假差异。
"""
import argparse
import html as htmllib
import re
import zipfile
from collections import Counter


def norm(s):
    s = re.sub(r'<[^>]+>', '\n', s)
    s = htmllib.unescape(s)
    s = s.replace('\u3000', '').replace('\xa0', '')
    return re.sub(r'\s+', '', s)


def src_text(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    body = s[s.find('<body'):]
    i = body.find('<hr')                      # 面包屑到第一个 <hr> 为止
    if i >= 0:
        body = body[body.find('>', i) + 1:]
    body = re.sub(r'<p class=.title1.>.*?</p>', '', body, count=1, flags=re.S)
    body = body.replace('<b>注释：</b>', '')
    body = re.sub(r"<a[^>]*name=['\"]_ftn(?:ref)?\d+['\"][^>]*>.*?</a>", '', body, flags=re.S)
    return norm(body)


def epub_text(zf, fname):
    s = zf.read('EPUB/' + fname).decode('utf-8')
    body = s[s.find('<body>'):]
    body = re.sub(r'<h1>.*?</h1>', '', body, count=1, flags=re.S)
    body = re.sub(r'<p class="fnhead">.*?</p>', '', body, flags=re.S)
    body = re.sub(r'<a (?:id="ftnref\d+"|href="#ftn\d+")[^>]*>.*?</a>', '', body, flags=re.S)
    body = re.sub(r'<a id="ftn\d+" href="#ftnref\d+">\[\d+\]</a>', '', body)
    return norm(body)


def windows(t, n=25):
    return {t[i:i + n] for i in range(0, max(len(t) - n + 1, 1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epub', required=True)
    ap.add_argument('--pages', required=True, help='源页面目录（<名>.htm，已是 UTF-8）')
    ap.add_argument('--map', action='append', default=[], help='页面名=EPUB内文件名')
    ap.add_argument('--window', type=int, default=25)
    args = ap.parse_args()

    zf = zipfile.ZipFile(args.epub)
    ok = True
    print('== 文本完整性（%d 字窗口双向比对）' % args.window)
    for pair in args.map:
        name, fname = pair.split('=', 1)
        a = src_text(f'{args.pages}/{name}.htm')
        b = epub_text(zf, fname)
        wa, wb = windows(a, args.window), windows(b, args.window)
        only_src, only_epub = wa - wb, wb - wa
        print(f'  {name}: 源 {len(a)} 字 / EPUB {len(b)} 字；'
              f'仅源 {len(only_src)} 窗口，仅 EPUB {len(only_epub)} 窗口')
        if only_src or only_epub:
            ok = False
            for w in sorted(only_src)[:5]:
                i = a.find(w)
                print(f'    [源] …{a[max(0, i - 10):i + 30]}…')
            for w in sorted(only_epub)[:5]:
                i = b.find(w)
                print(f'    [EPUB] …{b[max(0, i - 10):i + 30]}…')

    print('== 脚注与内部链接')
    refs, defs, ids, hrefs = [], [], set(), []
    for f in zf.namelist():
        if not f.endswith('.xhtml'):
            continue
        s = zf.read(f).decode('utf-8')
        ids |= set(re.findall(r'id="([^"]+)"', s))
        hrefs += re.findall(r'href="#([^"]+)"', s)
        refs += re.findall(r'id="ftnref(\d+)"', s)
        defs += re.findall(r'id="ftn(\d+)"', s)
    miss_def = sorted(set(refs) - set(defs), key=int)
    miss_ref = sorted(set(defs) - set(refs), key=int)
    dup = ([k for k, v in Counter(refs).items() if v > 1] +
           ['ftn' + k for k, v in Counter(defs).items() if v > 1])
    bad = sorted({h for h in hrefs if h not in ids})
    print(f'  引用 {len(refs)} 条，定义 {len(defs)} 条；缺定义 {miss_def or "无"}，'
          f'缺回链 {miss_ref or "无"}，重复 id {dup or "无"}')
    print(f'  内部链接 {len(hrefs)} 条，无法解析 {len(bad)} 条 {bad[:10] or ""}')
    if miss_def or miss_ref or dup or bad:
        ok = False
    print('\n结论:', 'PASS' if ok else 'FAIL')


if __name__ == '__main__':
    main()
