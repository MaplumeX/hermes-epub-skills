#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""epub_toc_audit.py — 体检 EPUB 的导航目录是否与正文标题一致(重建目录前/后都该跑一次)。

用法:
    python3 epub_toc_audit.py book.epub [--levels 3]
    python3 epub_toc_audit.py ./src          # 也可以直接喂解包后的目录

只依赖标准库。检查项:
  1. mimetype 是否在 ZIP 首位且未压缩(喂目录时该检查跳过)
  2. ncx 每条 <content src> / nav.xhtml 每个 <a href> 目标(文件+id)是否存在
  3. 正文 h1..hN 是否都有 id、是否都进入了导航
  4. 书内"目录"页(含 contents-chapter* 的页面)里的链接是否都是活链
  5. 同文件重复 id、ncx playOrder 是否连续、dtb:depth 是否与实际嵌套一致

退出码 0 = 全部通过;1 = 有问题(问题清单打到 stdout)。
"""
import os
import re
import sys
import posixpath
import zipfile

HEAD_RE = re.compile(r'<(h[1-6])\b([^>]*)>(.*?)</\1>', re.S)
CONTENT_SRC_RE = re.compile(r'<content\s+src="([^"]+)"')
A_HREF_RE = re.compile(r'<a\b[^>]*\bhref="([^"]*)"')
ID_RE = re.compile(r'\bid="([^"]+)"')

problems = []
notes = []


def load(target):
    """-> (files{relpath: bytes}, zip_mimetype_ok or None)"""
    if os.path.isdir(target):
        files = {}
        for root, _dirs, names in os.walk(target):
            for n in names:
                p = os.path.join(root, n)
                rel = os.path.relpath(p, target).replace(os.sep, '/')
                with open(p, 'rb') as fh:
                    files[rel] = fh.read()
        return files, None

    with zipfile.ZipFile(target) as z:
        files = dict((n, z.read(n)) for n in z.namelist() if not n.endswith('/'))
        infos = z.infolist()
        ok = None
        if infos:
            first = infos[0]
            ok = (first.filename == 'mimetype' and
                  first.compress_type == zipfile.ZIP_STORED and
                  files.get('mimetype') == b'application/epub+zip')
        return files, ok


def text(files, path):
    b = files.get(path)
    if b is None:
        return None
    return b.decode('utf-8', 'replace')


def find_opf(files):
    c = text(files, 'META-INF/container.xml')
    if c:
        m = re.search(r'full-path="([^"]+)"', c)
        if m and m.group(1) in files:
            return m.group(1)
    for n in files:
        if n.endswith('.opf'):
            return n
    return None


def resolve(base, href):
    if '://' in href or href.startswith('mailto:'):
        return None, None
    file, _, frag = href.partition('#')
    if file:
        path = posixpath.normpath(posixpath.join(base, file)) if base else file
    else:
        path = base
    return path, (frag or None)


def norm(base, href):
    """href -> 'resolved/path.xhtml#frag',与正文侧拼出的 key 同构(否则会假报未入导航)"""
    path, frag = resolve(base, href)
    if path is None:
        return None
    return '%s#%s' % (path, frag) if frag else path


def check_links(files, base, label, targets):
    """targets: iterable of href strings that live in `base`"""
    dead = 0
    n = 0
    for href in targets:
        href = href.replace('&amp;', '&')
        path, frag = resolve(base, href)
        if path is None:
            continue
        n += 1
        body = text(files, path)
        if body is None:
            problems.append('%s 目标文件不存在: %s' % (label, href))
            dead += 1
        elif frag and not re.search(r'\bid="%s"' % re.escape(frag), body):
            problems.append('%s 锚点不存在: %s' % (label, href))
            dead += 1
    notes.append('%s: %d 条链接, %d 条失效' % (label, n, dead))
    return n, dead


def main():
    args = [a for a in sys.argv[1:]]
    levels = 3
    if '--levels' in args:
        i = args.index('--levels')
        levels = int(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 2
    target = args[0]

    files, mimetype_ok = load(target)
    if mimetype_ok is False:
        problems.append('mimetype 不在 ZIP 首位或已被压缩(EPUB 会损坏)')
    if mimetype_ok is True:
        notes.append('mimetype: OK(首位 + 未压缩)')

    opf = find_opf(files)
    if not opf:
        print('找不到 content.opf,不是有效 EPUB')
        return 2
    base = posixpath.dirname(opf)
    opf_body = text(files, opf)

    manifest = dict((mid, href) for href, mid in
                    re.findall(r'<item\b[^>]*\bhref="([^"]+)"[^>]*\bid="([^"]+)"', opf_body))
    manifest2 = dict((mid, href) for href, mid in
                     re.findall(r'<item\b[^>]*\bid="([^"]+)"[^>]*\bhref="([^"]+)"', opf_body))
    manifest.update(manifest2)
    spine_ids = re.findall(r'<itemref\b[^>]*\bidref="([^"]+)"', opf_body)
    spine = [posixpath.normpath(posixpath.join(base, manifest[i]))
             for i in spine_ids if i in manifest]
    notes.append('spine: %d 个文件' % len(spine))

    # ---------- nav sources ----------
    ncx = None
    for href, mid in re.findall(r'<item\b[^>]*\bhref="([^"]+)"[^>]*\bid="([^"]+)"', opf_body):
        if href.endswith('.ncx'):
            ncx = posixpath.normpath(posixpath.join(base, href))
    nav_files = []
    for href in re.findall(r'<item\b[^>]*\bhref="([^"]+)"[^>]*>', opf_body):
        if 'nav' in href.lower() and href.endswith(('.xhtml', '.html')):
            nav_files.append(posixpath.normpath(posixpath.join(base, href)))

    nav_srcs = set()
    if ncx and text(files, ncx) is not None:
        body = text(files, ncx)
        srcs = CONTENT_SRC_RE.findall(body)
        check_links(files, base, 'ncx', srcs)
        nav_srcs |= set(x for x in (norm(base, s) for s in srcs) if x)
        po = [int(x) for x in re.findall(r'playOrder="(\d+)"', body)]
        if po and po != list(range(1, len(po) + 1)):
            problems.append('ncx playOrder 不连续或不唯一(%d 条)' % len(po))
        depth = 0
        real = 0
        for line in body.split('\n'):
            if '<navPoint' in line:
                depth += 1
                real = max(real, depth)
            if '</navPoint>' in line:
                depth -= 1
        d = re.search(r'dtb:depth"\s+content="(\d+)"', body)
        if d and int(d.group(1)) != real:
            problems.append('dtb:depth=%s 与实际嵌套 %d 不符' % (d.group(1), real))
        u = re.search(r'dtb:uid"\s+content="([^"]+)"', body)
        o = re.search(r'<dc:identifier[^>]*>([^<]+)<', opf_body)
        if u and o and u.group(1) != o.group(1).strip():
            problems.append('NCX-001 risk: dtb:uid(%s) != opf identifier(%s)'
                            % (u.group(1), o.group(1).strip()))
        notes.append('ncx: %d 条 navPoint, 实际嵌套 %d 层' % (len(po), real))
    else:
        notes.append('ncx: 无(EPUB3 或未声明)')

    for nf in nav_files:
        body = text(files, nf)
        if body is None:
            continue
        hrefs = A_HREF_RE.findall(body)
        check_links(files, base, 'nav(%s)' % posixpath.basename(nf), hrefs)
        nav_srcs |= set(x for x in (norm(base, h) for h in hrefs) if x)

    # ---------- body headings vs nav ----------
    total = with_id = no_id = in_nav = 0
    missing = []
    for path in spine:
        if not path.endswith(('.html', '.xhtml', '.htm')):
            continue
        body = text(files, path)
        if body is None:
            continue
        ids = ID_RE.findall(body)
        for dup in sorted(set(i for i in ids if ids.count(i) > 1)):
            problems.append('%s 文件内重复 id: %s' % (posixpath.basename(path), dup))
        for m in HEAD_RE.finditer(body):
            level = int(m.group(1)[1])
            if level > levels:
                continue
            total += 1
            idm = re.search(r'\bid="([^"]+)"', m.group(2))
            if idm:
                with_id += 1
            else:
                no_id += 1
            src = '%s#%s' % (path, idm.group(1) if idm else '')
            if idm and (src in nav_srcs or path in nav_srcs):
                in_nav += 1
            else:
                missing.append(src)
    if no_id:
        problems.append('%d 个 h1..h%d 标题缺少 id(无法作为跳转目标)' % (no_id, levels))
    if missing:
        preview = ', '.join(missing[:8])
        problems.append('%d 个标题未进入导航,例如: %s%s'
                        % (len(missing), preview, ' …' if len(missing) > 8 else ''))
    notes.append('正文 h1..h%d: %d 条(有 id %d,无 id %d,已入导航 %d)'
                 % (levels, total, with_id, no_id, in_nav))

    # ---------- in-book 目录 pages ----------
    toc_pages = [p for p in spine if p.endswith(('.html', '.xhtml'))
                 and 'contents-chapter' in (text(files, p) or '')]
    for p in toc_pages:
        check_links(files, base, '书内目录页 %s' % posixpath.basename(p),
                    A_HREF_RE.findall(text(files, p)))

    print('— 体检报告 —')
    for n in notes:
        print('  ·', n)
    if problems:
        print('— 问题 %d 项 —' % len(problems))
        for p in problems[:60]:
            print('  ✗', p)
        if len(problems) > 60:
            print('  … 另有 %d 项' % (len(problems) - 60))
        return 1
    print('— 全部通过 —')
    return 0


if __name__ == '__main__':
    sys.exit(main())
