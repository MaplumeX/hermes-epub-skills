#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_epub.py <out.epub> [workdir]

EPUB 成品通用校验（本技能各案例共用，替代每个案例手写一份 validate.py）：
  1. zip 完整性 + 解包
  2. XML 合法性（xhtml / opf / ncx / nav，逐个 ElementTree.fromstring）
  3. 内部链接解析（相对当前文件目录；nav 的 text/xxx.xhtml#id 以 EPUB/ 为基准 fallback）
  4. 同文件内锚点是否解析 + 文件内重复 id
  5. 脚注双向：epub:type="noteref" 与 footnote-back/backlink 计数
  6. MathML / 表格 统计
  7. 封面（properties="cover-image" + spine 首位）、nav 目录条目数、正文总字符

注意：pandoc 对每个拆分文件重新生成 fnrefN/fnN，**跨文件重复 id 是正常的**，只报同文件内重复。
"""
import os, re, sys, shutil, zipfile, posixpath, collections
import xml.etree.ElementTree as ET


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    epub = sys.argv[1]
    work = sys.argv[2] if len(sys.argv) > 2 else '/tmp/_epub_validate'
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    with zipfile.ZipFile(epub) as z:
        bad = z.testzip()
        print('zip testzip:', 'OK' if bad is None else f'BAD {bad}')
        z.extractall(work)
    files = [os.path.relpath(os.path.join(r, f), work)
             for r, _, fs in os.walk(work) for f in fs]
    print('条目数:', len(files))

    # 2) XML 合法性
    errs = 0
    for f in files:
        if f.endswith(('.xhtml', '.opf', '.ncx', '.xml')):
            try:
                ET.fromstring(open(os.path.join(work, f), 'rb').read())
            except ET.ParseError as e:
                errs += 1
                print(f'  XML 错误 {f}: {e}')
    print('XML 校验:', 'OK' if errs == 0 else f'{errs} 个文件有问题')

    # id 表（全局 + 逐文件）
    ids, ids_in = {}, {}
    for f in files:
        if f.endswith('.xhtml'):
            s = open(os.path.join(work, f), encoding='utf-8').read()
            found = re.findall(r'\sid="([^"]+)"', s)
            ids_in[f] = collections.Counter(found)
            for i in found:
                ids.setdefault(i, []).append(f)

    # 3) 链接解析
    bad_links, nlink = [], 0
    for f in files:
        if not f.endswith('.xhtml'):
            continue
        s = open(os.path.join(work, f), encoding='utf-8').read()
        d = posixpath.dirname(f)
        for m in re.finditer(r'href="([^"]+)"', s):
            href = m.group(1)
            if href.startswith(('http', 'mailto')):
                continue
            nlink += 1
            if href.startswith('#'):
                tgt, tid = f, href[1:]
            else:
                a, _, tid = href.partition('#')
                tgt = posixpath.normpath(posixpath.join(d, a))
            if tgt not in files:
                bad_links.append((f, href, 'file'))
                continue
            if tid and tid not in ids:
                bad_links.append((f, href, 'id'))
    print('内部链接:', nlink, '无效:', len(bad_links), bad_links[:5])

    # 4) 文件内重复 id / 同文件锚点
    dup, unscoped = [], []
    for f, c in ids_in.items():
        d = [k for k, v in c.items() if v > 1]
        if d:
            dup.append((f, d[:5]))
        s = open(os.path.join(work, f), encoding='utf-8').read()
        for m in re.finditer(r'href="#([^"]+)"', s):
            if m.group(1) not in c:
                unscoped.append((f, m.group(1)))
    print('文件内重复 id:', len(dup), dup[:3], ' 同文件锚点未解析:', len(unscoped), unscoped[:3])

    # 5) 脚注双向
    refs = back = 0
    for f in files:
        if f.endswith('.xhtml'):
            s = open(os.path.join(work, f), encoding='utf-8').read()
            refs += len(re.findall(r'epub:type="noteref"', s))
            back += len(re.findall(r'class="footnote-back"', s))
            back += len(re.findall(r'epub:type="backlink"', s))
    print('脚注 noteref:', refs, ' backlink:', back,
          'OK' if refs == back else '⚠ 数量不等')

    # 6) MathML / 表格 / 7) 封面 nav
    math = tbl = tot = 0
    for f in files:
        if f.endswith('.xhtml'):
            s = open(os.path.join(work, f), encoding='utf-8').read()
            math += s.count('<math')
            tbl += s.count('<table')
            tot += len(re.sub(r'<[^>]+>', '', s))
    print('MathML:', math, ' 表格:', tbl, ' 正文总字符:', tot)
    opf = [f for f in files if f.endswith('.opf')][0]
    s = open(os.path.join(work, opf), encoding='utf-8').read()
    print('cover-image:', 'cover-image' in s,
          ' spine 首位:', re.search(r'<spine[^>]*>(.{0,80})', s, re.S).group(1).strip().split('\n')[0])
    navp = next((f for f in files if f.endswith('nav.xhtml')), None)
    if navp:
        nav = open(os.path.join(work, navp), encoding='utf-8').read()
        print('TOC 条目:', len(re.findall(r'<a href="[^"]+">', nav)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
