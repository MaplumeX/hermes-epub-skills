#!/usr/bin/env python3
"""Pre-process pages.json: fix cross-page/cross-file paragraph breaks and
embedded footer noise lines. Run BEFORE build.py.

1. Embedded footer noise: for blocks with y>635, remove lines matching
   HEADER_FOOTER_RE (e.g. "存在论" inside a body block on P1 p166).
2. Cross-page/cross-file merge: if the last body block of a page ends with a
   non-terminal punctuation and the first body block of the next page is a
   pure continuation (single-line, non-structural), merge them.

Output overwrites pages.json (backup kept as pages_raw.json).

Why pages.json level, not book.md post-process:
- book.md cannot distinguish page-boundary breaks from legitimate in-page
  paragraph splits -> would over-merge.
- single-pass book.md merge is not chained: after merging line A into the
  previous line, the merged line may STILL end with non-terminal punctuation
  and its continuation gets skipped (e.g. "…纯粹的反思和规定的" + "反思的统一").
"""
import json, re, shutil

SRC = '/root/hegel_yizhu/pages.json'   # adjust per project
BAK = '/root/hegel_yizhu/pages_raw.json'

HEADER_FOOTER_RE = re.compile(
    r'^(第一版序言|第二版序言|第三版序言|导言|逻辑学概念的初步规定|'
    r'逻辑学概念的进一步规定和部门划分|第[一二三]篇|存在论|本质论|概念论)(\d*)$')
TERMINAL = re.compile(r'[。！？….!?]["」』”’)\]]*$')
CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵'
SEC_RE = re.compile(r'^第\s*(\d+)\s*节$')
SUB2_RE = re.compile(r'^[A-Z]\.\s')
SUB3_RE = re.compile(r'^\([a-z]\)\s')
SUB4_RE = re.compile(r'^\(\d+\)\s')
ROMAN_RE = re.compile(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[\.．]?\s')
CH1 = {'第三卷说明', '序言', '简称表', '第一版序言', '第二版序言', '第三版序言',
       '导言', '逻辑学概念的初步规定', '逻辑学概念的进一步规定和部门划分',
       '第一篇 存在论', '第二篇 本质论', '第三篇 概念论',
       '附录 黑格尔论"反思"(Reflexion)'}

def is_structural(t):
    """Structural elements that must NOT be merged into a previous paragraph."""
    s = t.strip()
    if not s:
        return True
    if s in CH1:
        return True
    if SEC_RE.match(s):
        return True
    if SUB2_RE.match(s) or SUB3_RE.match(s) or SUB4_RE.match(s) or ROMAN_RE.match(s):
        return True
    if re.match(r'^[' + CIRC + ']', s):
        return True
    if re.match(r'^\[\d+\]\s*[' + CIRC + ']', s):
        return True
    if s.startswith('注释'):
        return True
    if s in ('※ ※ ※', '直接知识或直观知识'):
        return True
    if re.match(r'^[一二三四五六七八九十]+\s', s) and len(s) < 40:
        return True
    if re.match(r'^\(Die Lehre vom', s):
        return True
    if HEADER_FOOTER_RE.match(s):
        return True
    return False

def is_pure_continuation(t):
    """Next-page first block qualifies as continuation: single-line, non-structural."""
    s = t.strip()
    if not s:
        return False
    if '\n' in s:
        return False
    if is_structural(s):
        return False
    return True

def main():
    shutil.copy(SRC, BAK)
    with open(SRC) as fh:
        pages = json.load(fh)

    # ---- pass 1: remove embedded footer noise lines (y>635) ----
    removed = 0
    for pg in pages:
        for b in pg['body']:
            if b.get('y', 0) <= 635:
                continue
            t = b['text']
            if '\n' not in t:
                continue
            lines = t.split('\n')
            kept = [ln for ln in lines if not HEADER_FOOTER_RE.match(ln.strip())]
            if len(kept) != len(lines):
                b['text'] = '\n'.join(kept).strip()
                removed += 1
    print(f"pass1: removed embedded footer lines in {removed} blocks")

    # ---- pass 2: cross-page / cross-file merge ----
    merged = 0
    for idx in range(len(pages) - 1):
        cur = pages[idx]
        nxt = pages[idx + 1]
        # last non-structural block of current page
        cur_body = cur['body']
        last_idx = None
        for i in range(len(cur_body) - 1, -1, -1):
            if is_structural(cur_body[i]['text'].strip()):
                continue
            last_idx = i
            break
        if last_idx is None:
            continue
        last_b = cur_body[last_idx]
        last_t = last_b['text'].strip()
        # strip marks for terminal check
        core = re.sub(r'\[\[MARK:[^\]]+\]\]', '', last_t)
        core = re.sub(r'\^\{[^}]+\}|[' + CIRC + ']', '', core).strip()
        if not core or TERMINAL.search(core):
            continue
        # first non-structural block of next page
        nxt_body = nxt['body']
        first_idx = None
        for i, b in enumerate(nxt_body):
            if is_structural(b['text'].strip()):
                continue
            first_idx = i
            break
        if first_idx is None:
            continue
        first_b = nxt_body[first_idx]
        first_t = first_b['text'].strip()
        if not is_pure_continuation(first_t):
            continue
        # merge
        sep = ' ' if (last_t[-1].isascii() and last_t[-1].isalnum()
                      and first_t[0].isascii() and first_t[0].isalnum()) else ''
        first_b['text'] = last_t + sep + first_t
        first_b['y'] = last_b['y']
        # remove the last block of current page (now merged into next page's first)
        del cur_body[last_idx]
        merged += 1

    print(f"pass2: merged {merged} cross-page breaks")
    with open(SRC, 'w') as fh:
        json.dump(pages, fh, ensure_ascii=False, indent=1)
    print(f"wrote {SRC} (backup {BAK})")

if __name__ == '__main__':
    main()
