#!/usr/bin/env python3
"""Diagnose per-section footnote marks vs note entries in layout.json-derived pages.json.

Use case: 逐节讲解+注释 books (per-section circled-number footnotes ①②③, renumbered
per section). Counts BOTH ^{X} superscript marks AND bare circled chars (OCR lost the
superscript wrapper). Prints sections where mark count != note count.

Usage: python3 align_marks_notes.py <pages.json>
Requires pages.json in the extract.py output shape:
  [{file, pi, orig, body: [{type, y, text}], footnotes: [text...]}]
"""
import json, re, sys

CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱'
SEC_RE = re.compile(r'^第\s*\d+\s*节$|^第\s*\d+、\d+\s*节$')
FN_RE = re.compile(r'^([①-⑱])\s*\S')
HELPER_RE = re.compile(r'^(黑格尔《小逻辑》译注|黑格尔《小逻辑》绎注|第[一二三]篇|逻辑学概念的初步规定|导言$|存在论$|本质论$|概念论$)')

def marks_in_text(t):
    """Ordered mark tokens: ('sup', X) for ^{X}, ('bare', 圈) for bare circled chars."""
    out = []
    for m in re.finditer(r'\^\{([^}]*)\}|([①-⑱])', t):
        if m.group(1) is not None:
            out.append(('sup', m.group(1)))
        else:
            out.append(('bare', m.group(2)))
    return out

def main(path):
    with open(path) as fh:
        pages = json.load(fh)

    stats = []
    cur_sec = None
    body_marks = []
    notes = []
    in_notes = False

    for pg in pages:
        for b in pg['body']:
            t = b['text']
            if t == '注释：':
                in_notes = True
                continue
            if SEC_RE.match(t):
                # flush previous section
                if cur_sec is not None:
                    stats.append((pg['file'], cur_sec, list(body_marks), list(notes)))
                cur_sec = t
                body_marks = []
                notes = []
                in_notes = False
                continue
            if in_notes:
                m = FN_RE.match(t)
                if m:
                    notes.append((CIRC.index(m.group(1)) + 1, t[:26]))
                elif notes:
                    notes[-1] = (notes[-1][0], notes[-1][1])  # continuation line
                continue
            if HELPER_RE.match(t):
                continue
            body_marks.extend(marks_in_text(t))
        # page-footnotes (discarded) also belong to current section
        for fn in pg['footnotes']:
            if cur_sec is not None:
                m = FN_RE.match(fn)
                if m:
                    notes.append((CIRC.index(m.group(1)) + 1, fn[:26]))
                else:
                    notes.append((0, fn[:26]))
    if cur_sec is not None:
        stats.append((pages[-1]['file'], cur_sec, list(body_marks), list(notes)))

    total_gap = 0
    mismatches = 0
    for f, sec, marks, notes in stats:
        mcnt, ncnt = len(marks), len(notes)
        if mcnt != ncnt and ncnt > 0:
            mismatches += 1
            total_gap += max(0, ncnt - mcnt)
            ml = ','.join(f"{k}:{v}" for k, v in marks[:16])
            if len(marks) > 16:
                ml += '...'
            print(f"[{f}] {sec:<22}{mcnt:>4}{ncnt:>4}  {ml}")
    print(f"\nsections={len(stats)} mismatched={mismatches} total_gap={total_gap}")

if __name__ == '__main__':
    main(sys.argv[1])
