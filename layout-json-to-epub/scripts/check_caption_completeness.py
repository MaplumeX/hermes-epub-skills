#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图/表题注完整性检查：正文引用过的编号 − 已有题注的编号 = 缺题注。

为什么不用「1..max 里的缺口」：教科书里大量插图本来就没有题注，
用缺口法会误报几十个假缺口。用「正文提到过这个图号、但没有任何块以它开头」才准。

题注可能落在 fig/table 的 cap **或** fnote 里（OCR 常把 chart_caption 塞进
chart_footnote），两边都要算，否则会把已修好的题注又报成缺失。

用法：
    python3 check_caption_completeness.py pages.json            # 图+表
    python3 check_caption_completeness.py pages.json fig        # 只查图
    python3 check_caption_completeness.py pages.json table      # 只查表

退出码非 0 = 有缺口，输出可直接贴给用户当交付说明。
"""
import json
import re
import sys
import collections

CAP = re.compile(r'^([图表])\s*(\d+)([A-Za-z]?)[-—](\d+)')
ANY = re.compile(r'([图表])\s*(\d+)([A-Za-z]?)[-—](\d+)')
PUA = re.compile(r'[\ue000-\ue003]')


def cl(t):
    return PUA.sub('', t or '').strip()


def check(pages, kinds=('图', '表')):
    have = collections.defaultdict(set)     # (kind, ch, suffix) -> {num}
    refs = collections.defaultdict(set)
    where = {}

    for p in pages:
        for b in p['blocks']:
            bt = b['type']
            if bt == 'fig':
                kind = '图'
            elif bt == 'table':
                kind = '表'
            else:
                kind = None
            if kind and kind in kinds:
                for src in ('cap', 'fnote'):
                    for c in b.get(src, []):
                        m = CAP.match(cl(c))
                        if m and m.group(1) == kind:
                            k = (kind, int(m.group(2)), m.group(3))
                            have[k].add(int(m.group(4)))
            if kind is None or kind in kinds:
                for m in ANY.finditer(cl(b.get('text', ''))):
                    k = (m.group(1), int(m.group(2)), m.group(3))
                    if k[0] in kinds:
                        refs[k].add(int(m.group(4)))

    missing = []
    for k, ns in refs.items():
        for n in sorted(ns):
            if n not in have.get(k, set()):
                missing.append((k, n))
    return have, refs, sorted(missing)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'pages.json'
    kinds = tuple(sys.argv[2:]) or ('图', '表')
    pages = json.load(open(path, encoding='utf-8'))
    have, refs, missing = check(pages, kinds)

    for kind in kinds:
        nref = sum(len(v) for k, v in refs.items() if k[0] == kind)
        nhave = sum(len(v) for k, v in have.items() if k[0] == kind)
        mis = [x for x in missing if x[0][0] == kind]
        print('%s：正文引用 %d 个编号，有题注 %d 个，缺 %d 个'
              % (kind, nref, nhave, len(mis)))
        for (k, n) in mis:
            print('   %s%d%s-%d' % (k[0], k[1], k[2], n))
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
