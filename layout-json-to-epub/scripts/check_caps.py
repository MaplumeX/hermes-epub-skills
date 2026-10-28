#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图题/表题缺口权威检查：正文引用过的编号 − 已有题注的编号 = 真缺口。

用法：python3 check_caps.py pages.json [fig|table]
退出码：有缺口返回 1（方便串进构建链）。

要点：
- 不用「1..max 缺号」判：章末无编号装饰小图、编分隔页整图、跨章同号会造大量假缺口
- 正反两向都查：refs-caps（缺题注）、caps-refs（题注张冠李戴）
- **题注可能落在 fnote 里**（题注被 OCR 归进 chart_footnote / 表格 fnote，本例图30-10），
  所以「已有题注」必须 cap + fnote 两边都数；只数 cap 会误报缺号
- refs 也要扫 aside 块（表题常被判成 aside_text）
"""
import json
import re
import sys
import collections

P = sys.argv[1] if len(sys.argv) > 1 else 'pages.json'
KIND = sys.argv[2] if len(sys.argv) > 2 else 'fig'
CHAR = '图' if KIND == 'fig' else '表'
BLOCK = 'fig' if KIND == 'fig' else 'table'
pages = json.load(open(P))


def cl(t):
    return re.sub(r'[\ue000-\ue003]', '', t)


# 字母在数字后面：图1A-4 / 图5A-1
CAPRE = re.compile(CHAR + r'\s*(\d+)([A-Za-z]?)[-—](\d+)')
REFRE = re.compile(CHAR + r'\s*(\d+)([A-Za-z]?)[-—](\d+)')

caps = collections.defaultdict(set)
misplaced = []
for i, p in enumerate(pages):
    for b in p['blocks']:
        if b['type'] != BLOCK:
            continue
        for src in ('cap', 'fnote'):
            for c in b.get(src, []):
                m = CAPRE.match(cl(c).strip())
                if m:
                    caps[(int(m.group(1)), m.group(2))].add(int(m.group(3)))
                    if src == 'fnote':
                        misplaced.append((i, cl(c)[:70]))

refs = collections.defaultdict(set)
for p in pages:
    for b in p['blocks']:
        for m in REFRE.finditer(cl(b.get('text', ''))):
            refs[(int(m.group(1)), m.group(2))].add(int(m.group(3)))

missing = [(k, n) for k, ns in sorted(refs.items()) for n in sorted(ns)
           if n not in caps.get(k, set())]
extra = [(k, n) for k, ns in caps.items() for n in ns
         if n not in refs.get(k, set())]

print('正文引用%s号 %d 个，已有题注 %d 个'
      % (CHAR, sum(len(v) for v in refs.values()), sum(len(v) for v in caps.values())))
print('缺题注 %d 个：' % len(missing))
for (ch, suf), n in missing:
    print('  %s%d%s-%d' % (CHAR, ch, suf, n))
print('题注存在但正文未引用 %d 个（可能是误挂）：' % len(extra))
for (ch, suf), n in extra[:30]:
    print('  %s%d%s-%d' % (CHAR, ch, suf, n))
print('题注落在 fnote 里 %d 条（应挪到 cap）：' % len(misplaced))
for i, t in misplaced[:30]:
    print('  idx%-4d %s' % (i, t))

json.dump([[list(k), n] for k, n in missing], open('gaps_%s.json' % KIND, 'w'),
          ensure_ascii=False)
print('→ gaps_%s.json（喂给逐条人工审查脚本）' % KIND)
sys.exit(1 if missing else 0)
