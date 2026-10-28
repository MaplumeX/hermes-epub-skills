#!/usr/bin/env python3
"""Batch report for mismatched sections: body mark sequence + note entry starts.

For 逐节讲解+圈码注释 books (张世英《黑格尔〈小逻辑〉绎注》型):
- Reads pages.json (extract.py output)
- For each section in the mismatch list: prints body mark sequence (with context)
  and note entry starts
- 正文标记序列 vs 注释编号序列对照，错位处即 OCR 错读处
  (e.g. 第48节 `^{③}` 重复出现 → 第二个应为 ④；第50节序列 1,3,4,6,7,8,3 明显错位)

Usage: python3 batch_report.py
Adjust MISMATCH list from align.py output (sections where marks != notes).
"""
import json, re

with open('/root/hegel_yizhu/pages.json') as fh:
    pages = json.load(fh)

CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵'

# sections: (name, num, file, pi, bi)
sections = []
for pg in pages:
    for bi, b in enumerate(pg['body']):
        t = b['text'].strip()
        if re.match(r'^第\s*\d+(\s*[、,，]\s*\d+)*\s*节', t) and len(t) < 30:
            m = re.search(r'(\d+)', t)
            sections.append((t, int(m.group(1)), pg['file'], pg['pi'], bi))

def collect(sidx):
    """Collect body marks + note entry starts for section sidx.
    IMPORTANT: use (file, pi) tuple comparison — P1/P2/P3 pi are per-file
    indices, comparing pi alone mixes sections across files."""
    sf, spi, sbi = sections[sidx][2], sections[sidx][3], sections[sidx][4]
    if sidx+1 < len(sections):
        ef, epi, ebi = sections[sidx+1][2], sections[sidx+1][3], sections[sidx+1][4]
    else:
        ef, epi, ebi = 'ZZZ', 9999, 9999
    body_marks = []  # (mark_text, context)
    note_starts = []
    in_notes = False
    for pg in pages:
        f, pi = pg['file'], pg['pi']
        if (f, pi) < (sf, spi):
            continue
        if (f, pi) > (ef, epi):
            break
        for bi, b in enumerate(pg['body']):
            if (f, pi) == (sf, spi) and bi < sbi: continue
            if (f, pi) == (ef, epi) and bi >= ebi: break
            t = b['text'].strip()
            if not t: continue
            if t.startswith('注释'):
                in_notes = True
                continue
            if in_notes:
                # 只认圈码开头为新条目；数字开头是续行（如 "33、34、35页…"）
                if re.match(r'^[' + CIRC + ']', t) or re.match(r'^中[\s、．.]', t):
                    note_starts.append(t[:40])
                else:
                    if note_starts:
                        note_starts[-1] += '…'
            else:
                for m in re.finditer(r'\^\{([^}]+)\}|[' + CIRC + ']', t):
                    ctx = t[max(0, m.start()-15):m.start()+10].replace('\n', ' ')
                    body_marks.append((m.group(0), ctx))
        for fn in pg['footnotes']:
            note_starts.append(fn[:40])
    return body_marks, note_starts

# 从 align.py 输出复制不匹配节名
MISMATCH = ['第9节', '第12节', '第13节', '第24节', '第42节', '第48节', '第50节', '第81节',
            '第92节', '第112节', '第117节', '第120节', '第121节', '第136节', '第137节',
            '第142节', '第145节', '第146节', '第147节', '第155节', '第164节', '第169节',
            '第173节', '第175节', '第179节', '第181节', '第206节', '第207节', '第208节',
            '第209节', '第213节', '第214节', '第215节', '第216节', '第218节', '第229节',
            '第232节', '第241节']

for name in MISMATCH:
    for sidx, (sname, num, sf, pi, bi) in enumerate(sections):
        if sname == name:
            marks, notes = collect(sidx)
            print(f"\n===== {name} ({sf} p{pi}) =====")
            print(f"  body marks ({len(marks)}):")
            for m, ctx in marks:
                print(f"    {m}  ...{ctx}...")
            print(f"  note starts ({len(notes)}):")
            for n in notes:
                print(f"    {n}")
            break
