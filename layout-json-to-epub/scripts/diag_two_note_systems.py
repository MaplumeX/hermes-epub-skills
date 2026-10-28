#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双注释体系诊断：章级「数字上标 vs 译注条目」+ 页级「圈码 vs 页脚注条目」。

适用：中译本学术专著，页脚圈码注（每页从①重编）与章末「译注」数字注（每章从 1 重编）并存。

用法：
    python3 diag_two_note_systems.py pages.json

pages.json 的块格式约定（与 layout-json-to-epub 技能各案例的 extract.py 一致）：
    {'t': 'title'|'sec'|'text'|'ref_text'|'fn'|'fig'|'tab'|'eq',
     's': '...', 'page': 'A42', 'y': 48, 'x0': 26}
标记已归一化为 {{MARK:圈码}} / {{MARK:N}}。

输出：
  1) 章级表：marks 序列 / notes 条数 / gaps（跳号区间）
  2) 页级不匹配清单：body=正文圈码序列  fn=页脚注条目圈码序列
退出码：两套体系都不匹配时非 0，便于 CI 拦截。
"""
import json
import re
import sys
from collections import OrderedDict

CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
MARK_RE = re.compile(r'\{\{MARK:([^}]+)\}\}')
CH_RE = re.compile(r'^第\s*(\d+)\s*章')

# 章末「译注」区之外的 `#` 级章节名，按书改这一处即可
FLAT_CHAPTERS = {'译者说明', '导言', '后记', '参考书目', '人名索引', '主题索引'}
YZ = '译注'


def chapter_key(title):
    t = re.sub(r'\s+', '', title)
    m = CH_RE.match(t)
    if m:
        return '第%s章' % m.group(1)
    if t in FLAT_CHAPTERS:
        return t
    if t.startswith('2006年唯首出版社'):
        return '2006导言'
    return None


def parse_notes(texts):
    """译注条目分条：严格连续判据（序号前不一定有标点）。"""
    txt = ''.join(texts).replace('\n', '')
    txt = MARK_RE.sub('', txt)
    used, last, gaps = [], 0, []
    for m in re.finditer(r'(\d{1,3})[.、]', txt):
        n = int(m.group(1))
        prev = txt[m.start() - 1] if m.start() else ''
        if n == last + 1:
            used.append((m.start(), m.end(), n))
            last = n
        elif last + 1 < n <= last + 6 and prev in '。！？；：）】”’…':
            gaps.append((last + 1, n - 1))
            used.append((m.start(), m.end(), n))
            last = n
    return [n for _, _, n in used], gaps


def main(path):
    pages = json.load(open(path))
    chaps = OrderedDict()
    cur, mode = None, 'body'
    page_rows = []

    def C(name):
        if name not in chaps:
            chaps[name] = {'marks': [], 'yz': []}
        return chaps[name]

    for p in pages:
        page = p.get('page') or '%s%s' % (p.get('f', ''), p.get('pi', ''))
        body_circ, fn_circ = [], []
        for b in p.get('blocks', []):
            t, s = b.get('t'), b.get('s') or ''
            if t in ('title', 'sec'):
                tn = re.sub(r'\s+', '', s)
                if tn == YZ:
                    mode = 'yz'
                    continue
                ck = chapter_key(s)
                if ck:
                    cur, mode = ck, 'body'
                    C(ck)
                continue
            if cur is None:
                continue
            if mode == 'yz':
                if t == 'fn' and re.match(r'^\s*\{\{MARK:[①-⑳]\}\}', s):
                    fn_circ.append(MARK_RE.match(s).group(1))
                else:
                    chaps[cur]['yz'].append(s)
                continue
            if t == 'fn':
                m = re.match(r'^\s*\{\{MARK:([①-⑳])\}\}', s)
                if m:
                    fn_circ.append(m.group(1))
                continue
            if t in ('text', 'ref_text'):
                for m in MARK_RE.finditer(s):
                    v = m.group(1)
                    if v in CIRC:
                        body_circ.append(v)
                    elif re.fullmatch(r'\d{1,3}', v):
                        chaps[cur]['marks'].append(int(v))
        if body_circ or fn_circ:
            page_rows.append((page, body_circ, fn_circ))

    print('=== 章级：正文数字标记 vs 译注条目')
    bad = 0
    tm = tn = 0
    for ck, st in chaps.items():
        notes, gaps = parse_notes(st['yz'])
        marks = st['marks']
        tm += len(marks)
        tn += len(notes)
        seq_ok = marks == list(range(1, len(marks) + 1))
        cnt_ok = len(marks) == len(notes)
        if not (seq_ok and cnt_ok):
            bad += 1
        print('%-12s marks=%-3d notes=%-3d gaps=%-8s seq=%s' % (
            ck, len(marks), len(notes), str(gaps), ','.join(map(str, marks))[:80]))
    print('TOTAL marks %d  notes %d  mismatch chapters %d' % (tm, tn, bad))

    print('\n=== 页级：正文圈码 vs 页脚注条目（仅不匹配）')
    pbad = 0
    for page, bc, fc in page_rows:
        if bc != fc:
            pbad += 1
            print(' %-6s body=%s fn=%s' % (page, ''.join(bc), ''.join(fc)))
    print('mismatch pages %d / %d' % (pbad, len(page_rows)))

    return 1 if (bad or pbad) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'pages.json'))
