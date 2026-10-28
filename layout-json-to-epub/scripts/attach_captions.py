#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 OCR 拆散的图题/表题挂回最近的 fig/table 块。

背景：layout.json 里 chart/image 块的题注本该在 `chart_caption`/`image_caption`
子块里，但 OCR 常把它整段跑出去变成独立的 `title`/`text` 块；图号与标题还可能
再拆成两块（`图1A-4` + `坡度不等于斜率`）。

题注判定（严格，宁缺勿错）：
  - type == 'title' 且以「图N-M」「表N-M」开头  → 一定是题注
  - type == 'text' 且以图号开头、len<80、无句号、**图号后不接引用动词** → 题注

引用动词黑名单不是可选项：`图 6-1 也可以表明劳动的边际收益递减规律。假定土地……`
这类被 OCR 截成 70 字无句号的**正文**块，只靠「短+无句号」会被误挂成图题，
正文就此消失（实测踩过）。

宿主：同页最近的无题注 fig/table 块；同页没有则看下一页前 6 块。

用法：python3 attach_captions.py pages.json [--dry-run]
      （原地改 pages.json；跑在 build.py 之前，且应从 pages_raw.json 重建后再跑）
"""
import json
import re
import sys

CAP = re.compile(r'^([图表])\s*(\d+)([A-Za-z]?)[-—](\d+)\s*(.*)$')
# 图号后紧接这些词 → 是正文里的交叉引用，不是题注
REF = re.compile(r'^(描述|表明|显示|说明|是|将|表示|所|中|到|和|与|及|（|\(|给出|'
                 r'描绘|呈现|列出|用|可以|还|也|概括|总结)')
TOK = re.compile(r'[\ue000-\ue003]')


def cl(t):
    """去掉 extract 阶段的私有区 token"""
    return TOK.sub('', t).strip()


def capno(t):
    m = CAP.match(t)
    return None if not m else (m.group(1), int(m.group(2)), m.group(3), int(m.group(4)))


def is_caption(b):
    if b.get('type') not in ('title', 'text'):
        return False
    t = cl(b.get('text', ''))
    m = CAP.match(t)
    if not m:
        return False
    if b['type'] == 'title':
        return True
    if len(t) >= 80 or '。' in t:
        return False
    return not REF.match(m.group(5).strip())


def has_cap(b):
    return bool(b.get('cap'))


def nearest(blocks, idx, kind, span=4):
    for d in range(0, span + 1):
        cand = [idx - 1, idx + 1] if d == 0 else [idx - 1 - d, idx + 1 + d]
        for j in cand:
            if 0 <= j < len(blocks) and blocks[j]['type'] == kind and not has_cap(blocks[j]):
                return j
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'pages.json'
    dry = '--dry-run' in sys.argv
    pages = json.load(open(path, encoding='utf-8'))

    attached, orphan = 0, []
    for pi, p in enumerate(pages):
        blocks = p['blocks']
        i = 0
        while i < len(blocks):
            b = blocks[i]
            if not is_caption(b):
                i += 1
                continue
            txt = cl(b['text'])
            no = capno(txt)
            # 图号与标题被拆成两块 → 拼接
            if i + 1 < len(blocks) and blocks[i + 1]['type'] in ('title', 'text'):
                nxt = cl(blocks[i + 1]['text'])
                if (nxt and not capno(nxt) and len(nxt) < 40
                        and not re.search(r'[。！？]', nxt)
                        and not nxt.startswith('资料来源')):
                    txt = txt + ' ' + nxt
                    blocks.pop(i + 1)
            kind = 'fig' if no[0] == '图' else 'table'
            ti = nearest(blocks, i, kind)
            if ti is not None:
                blocks[ti].setdefault('cap', []).insert(0, txt)
                blocks.pop(i)
                attached += 1
                continue
            # 跨页：下一页前 6 块里第一个无题注的同类块
            if pi + 1 < len(pages):
                for nb in pages[pi + 1]['blocks'][:6]:
                    if nb['type'] == kind and not has_cap(nb):
                        nb.setdefault('cap', []).insert(0, txt)
                        blocks.pop(i)
                        attached += 1
                        break
                else:
                    orphan.append((pi, txt[:40]))
                    i += 1
                continue
            orphan.append((pi, txt[:40]))
            i += 1

    print('挂回 %d 条，无宿主 %d 条' % (attached, len(orphan)))
    for o in orphan:
        print('  ', o)
    if not dry:
        json.dump(pages, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
