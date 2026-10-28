#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pandoc --epub-chapter-level 拆章后，把 href="#id" 的锚点改成跨文件相对路径。
用法: python3 fix_epub_links.py in.epub out.epub
只改 href="#id" 形式；已带路径的 href="file#id" 不动。nav.xhtml 的 TOC 链接本来就相对 EPUB/ 根，不算错。
"""
import zipfile, os, re, posixpath, sys, tempfile, shutil

src, dst = sys.argv[1], sys.argv[2]
work = tempfile.mkdtemp(prefix='epubfix-')
with zipfile.ZipFile(src) as z:
    z.extractall(work)

ids = {}
for root, _, files in os.walk(os.path.join(work, 'EPUB')):
    for f in files:
        if f.endswith(('.xhtml', '.ncx', '.opf')):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, work).replace(os.sep, '/')
            txt = open(p, encoding='utf-8').read()
            for m in re.finditer(r'\sid="([^"]+)"', txt):
                ids.setdefault(m.group(1), rel)

count = [0]
for root, _, files in os.walk(os.path.join(work, 'EPUB')):
    for f in files:
        if not f.endswith(('.xhtml', '.ncx')):
            continue
        p = os.path.join(root, f)
        rel = os.path.relpath(p, work).replace(os.sep, '/')
        curdir = posixpath.dirname(rel)
        txt = open(p, encoding='utf-8').read()

        def repl(m):
            tgt = ids.get(m.group(1))
            if not tgt or tgt == rel:
                return m.group(0)
            count[0] += 1
            return 'href="%s#%s"' % (posixpath.relpath(tgt, curdir), m.group(1))
        new = re.sub(r'href="#([^"]+)"', repl, txt)
        if new != txt:
            open(p, 'w', encoding='utf-8').write(new)

if os.path.exists(dst):
    os.remove(dst)
with zipfile.ZipFile(dst, 'w') as z:
    z.write(os.path.join(work, 'mimetype'), 'mimetype', compress_type=zipfile.ZIP_STORED)
    for root, _, files in os.walk(work):
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, work).replace(os.sep, '/')
            if rel != 'mimetype':
                z.write(p, rel, compress_type=zipfile.ZIP_DEFLATED)
shutil.rmtree(work)
print('跨文件锚点修正: %d 处' % count[0])
