#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""epub_repack.py — 把改过的解包目录重新打成合规 EPUB。

用法:
    python3 epub_repack.py <src_dir> <out.epub> [--prefix OEBPS]

关键约束(不遵守 = 文件损坏成普通 zip):
  · mimetype 必须是 ZIP 的**第一个条目**,且 **不压缩**(ZIP_STORED)
  · 其余条目 ZIP_DEFLATED,顺序无所谓但排序后最稳定

注意:重压缩会把体积降下来(实测 15.2MB → 11.7MB,多为原包里
已压缩的图片被重新压缩)。**交付时要主动说明**,否则用户会以为内容被删了。
"""
import os
import sys
import zipfile


def repack(src, out):
    pairs = []
    for root, _dirs, names in os.walk(src):
        for n in names:
            p = os.path.join(root, n)
            rel = os.path.relpath(p, src).replace(os.sep, '/')
            pairs.append((rel, p))
    pairs.sort()

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        # 1) mimetype 首位 + 不压缩
        zi = zipfile.ZipInfo('mimetype')
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, 'application/epub+zip')
        # 2) 其余条目
        for rel, p in pairs:
            if rel == 'mimetype':
                continue
            zi = zipfile.ZipInfo(rel)
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(p, 'rb') as fh:
                z.writestr(zi, fh.read())

    # 3) 自检
    with zipfile.ZipFile(out) as z:
        infos = z.infolist()
        assert infos[0].filename == 'mimetype', 'mimetype 不在首位'
        assert infos[0].compress_type == zipfile.ZIP_STORED, 'mimetype 被压缩了'
        assert z.read('mimetype') == b'application/epub+zip', 'mimetype 内容不对'
        bad = z.testzip()
        assert bad is None, 'ZIP 损坏: %s' % bad
    print('wrote %s (%d entries, %.1f MB)'
          % (out, len(pairs) + 1, os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    repack(sys.argv[1], sys.argv[2])
