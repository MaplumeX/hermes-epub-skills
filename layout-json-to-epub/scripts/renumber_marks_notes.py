#!/usr/bin/env python3
"""按出现顺序重编号正文标记/注释条目，修"缺 N 补 1"型 OCR 错读。

背景：count 对齐（align.py mismatch=0）不等于编号正确——正文标记序列
可能是 1,2,3,1,5 或 8,3,10（OCR 把缺号重读成已出现的数）。本脚本把每个
区域（节/章/附录每页）的正文标记与注释条目各自按出现顺序重编号为 1..N。

用法：
  python3 renumber_marks_notes.py            # book.md -> book_renum.md
  cp book_renum.md book.md                   # 覆盖后继续 mdlinks 等下游

规则：
- 正文标记与注释条目用【独立】计数器（两者按位置 1:1 对应）
- 新节（**第N节**）、新章（# 标题）、附录换页时重置计数器
- 附录正文标记保留页码前缀：[[MARK:pg-N]] -> [[MARK:pg-k]]
- SKIP_SEC：语义配对已证的顺序颠倒节（如第146节 5,6,4）不重排，
  否则破坏语义锚点——重排前先人工确认哪些节是"有意乱序"
"""
import re

SRC = 'book.md'
DST = 'book_renum.md'
SKIP_SEC = {146}   # 语义验证过的顺序颠倒节，按需调整

CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵'

def num2circ(n):
    return CIRC[n-1] if 1 <= n <= len(CIRC) else str(n)

def main():
    with open(SRC) as fh:
        lines = fh.read().split('\n')

    out = []
    cur_sec = None
    in_notes = False
    skip = False
    body_cnt = 0
    note_cnt = 0
    area_type = None      # 'sec' / 'chap' / 'app'
    app_pg = None

    for ln in lines:
        s = ln.strip()

        if s.startswith('# 附录'):
            cur_sec, in_notes, area_type = None, False, 'app'
            body_cnt = note_cnt = 0
            app_pg = None
            out.append(ln); continue
        if s.startswith('# '):
            cur_sec, in_notes, area_type = None, False, 'chap'
            body_cnt = note_cnt = 0
            out.append(ln); continue
        m = re.match(r'^\*\*第(\d+)节\*\*$', s)
        if m:
            cur_sec = int(m.group(1))
            in_notes = False
            area_type = 'sec'
            body_cnt = note_cnt = 0
            skip = cur_sec in SKIP_SEC
            out.append(ln); continue
        if s.startswith('注释：'):
            in_notes = True
            out.append(ln); continue

        # 附录注释条目：[pg] ① ...
        m = re.match(r'^\[(\d+)\]\s*([①-⑳㉑-㉟])', s)
        if area_type == 'app' and m:
            pg = m.group(1)
            if pg != app_pg:
                app_pg = pg
                note_cnt = 0
            note_cnt += 1
            out.append(ln.replace(m.group(2), num2circ(note_cnt), 1))
            continue

        # 节/章注释条目：① ...
        if in_notes and re.match(r'^[①-⑳㉑-㉟]', s):
            if skip:
                out.append(ln)
            else:
                note_cnt += 1
                out.append(ln.replace(s[0], num2circ(note_cnt), 1))
            continue

        # 正文标记
        if '[[MARK:' in ln and not skip:
            if area_type == 'app':
                # 附录：[[MARK:pg-N]] -> [[MARK:pg-k]]，按页重置 body_cnt
                parts = ln.split('[[MARK:')
                new_parts = [parts[0]]
                for p in parts[1:]:
                    pm = re.match(r'(\d+)-(\d+)\]\]', p)
                    if pm:
                        pg = pm.group(1)
                        if pg != app_pg:
                            app_pg = pg
                            body_cnt = 0
                        body_cnt += 1
                        new_parts.append('[[MARK:' + f'{pg}-{body_cnt}]]' + p[pm.end():])
                    else:
                        new_parts.append('[[' + p)
                out.append(''.join(new_parts))
            else:
                def repl(m2):
                    nonlocal body_cnt
                    body_cnt += 1
                    return f'[[MARK:{body_cnt}]]'
                out.append(re.sub(r'\[\[MARK:\d+\]\]', repl, ln))
            continue

        out.append(ln)

    with open(DST, 'w') as fh:
        fh.write('\n'.join(out))
    print(f"wrote {DST}")

if __name__ == '__main__':
    main()
