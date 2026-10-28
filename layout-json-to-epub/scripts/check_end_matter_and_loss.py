#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""章末区（内容提要/关键概念/复习题/问题与应用/快速测验）结构校验 + discarded 块丢失扫描。

两个独立的检查，任一失败退出码 1：

  A. 结构校验（只要 book.md）
     按 `#### 内容提要` 等小节切块，逐行归类 N(题号) / O(选项) / X(其它)，
     报「快速测验题号不是 1..6」「A/D 选项计数≠6」「编号不连续」「游离文本」。
     典型命中：选项挤成一行（x 串成一片）、题号粘上行尾、题干跨栏被切两段。

  B. 丢失扫描（book.md + pages.json + 各 layout.json）
     逐页取 discarded_blocks 里的 header/footer，去空白后若不在 book.md 里
     且不是版式噪声（书名/章名/篇名/页码/续表/Preface/网址）→ 报丢失。
     典型命中：OCR 把页底正文判成 footer，build 的白名单启发式把它丢了。

用法：
  python3 check_end_matter_and_loss.py book.md
  python3 check_end_matter_and_loss.py book.md --loss pages.json A=docA_layout.json M=docM_layout.json
"""
import json
import re
import sys

SECTIONS = ('内容提要', '关键概念', '复习题', '问题与应用', '快速测验', '快速测验答案')
QNUM = re.compile(r'^(\d{1,2})\\?\s*[.、]')
OPT = re.compile(r'^([A-D])\\?\s*[.、]')


def split_sections(lines):
    """返回 [(行号, 小节名, 正文行列表)]"""
    out, i = [], 0
    while i < len(lines):
        m = re.match(r'^#{2,4} (.+)$', lines[i].strip())
        if m and m.group(1).strip() in SECTIONS:
            j, body = i + 1, []
            while j < len(lines) and not re.match(r'^#{2,4} ', lines[j]):
                body.append(lines[j])
                j += 1
            out.append((i + 1, m.group(1).strip(), body))
            i = j
        else:
            i += 1
    return out


def classify(body):
    items = []
    for b in body:
        for piece in b.strip().replace('<br/>', '\n').split('\n'):
            piece = piece.strip()
            if not piece:
                continue
            m = QNUM.match(piece)
            if m:
                items.append(('N' + m.group(1), piece))
                continue
            m = OPT.match(piece)
            if m:
                items.append(('O' + m.group(1), piece))
                continue
            items.append(('X', piece))
    return items


def check_structure(md):
    bad = 0
    for ln, name, body in split_sections(md.split('\n')):
        it = classify(body)
        nums = [int(t[1:]) for t, _ in it if t.startswith('N')]
        opts = [t[1] for t, _ in it if t.startswith('O')]
        other = [v for t, v in it if t == 'X']
        seq = ''.join('Q' if t.startswith('N') else 'o' if t.startswith('O') else 'x' for t, _ in it)
        prob = []
        if name == '快速测验':
            if nums != list(range(1, 7)):
                prob.append('题号 %s' % nums)
            if opts.count('A') != 6 or opts.count('D') != 6:
                prob.append('A=%d D=%d' % (opts.count('A'), opts.count('D')))
        else:
            if nums and nums != list(range(1, len(nums) + 1)):
                prob.append('编号不连续 %s' % nums)
        if other:
            prob.append('游离%d' % len(other))
        if prob:
            bad += 1
            print('line %5d %-6s items %3d %s  <<< %s'
                  % (ln, name, len(it), seq[:70], '; '.join(prob)))
    print('结构异常小节: %d' % bad)
    return bad


NOISE = [
    r'^.{0,40}（第[一二三四五六七八九十]+版）$',
    r'^\d{1,3}[.\s]*.{0,40}（第[一二三四五六七八九十]+版）$',
    r'^\d{1,3}[.、]?$',
    r'^续表$',
    r'^(Preface|Contents|CONTENTS)$',
    r'^第\s*\d{1,2}\s*章\s*.{0,30}$',
    r'^第\s*[一二三四五六]\s*篇\s*.{0,30}$',
    r'^结束语\s*.{0,30}$',
    r'^\d{1,3}\s+第\s*\d{1,2}\s*章',
    r'macmillanlearning',
]
NOISE = [re.compile(p, re.I) for p in NOISE]


def plain(block):
    return '\n'.join(''.join(s.get('content', '') for s in (l.get('spans') or []))
                     for l in (block.get('lines') or []))


def check_loss(md_path, pages_path, layout_specs):
    pages = json.load(open(pages_path))['pages']
    kept = {(p['file'], p['pi']) for p in pages}
    md = re.sub(r'\s', '', open(md_path, encoding='utf-8').read())
    lost = []
    for tag, path in layout_specs:
        d = json.load(open(path))
        for i, pg in enumerate(d.get('pdf_info', [])):
            if (tag, i) not in kept:
                continue
            for b in pg.get('discarded_blocks', []):
                if b.get('type') not in ('header', 'footer'):
                    continue
                t = plain(b).strip()
                core = re.sub(r'\s', '', t)
                if len(core) < 12 or any(p.match(core) or p.search(core) for p in NOISE):
                    continue
                if core in md:
                    continue
                lost.append((tag, i, b.get('type'), b.get('bbox'), t))
    print('discarded 里疑似丢失的正文块: %d（字符 %d）'
          % (len(lost), sum(len(re.sub(r'\s', '', x[4])) for x in lost)))
    for tag, i, ty, bbox, t in lost[:40]:
        print('  %s %3d %-6s %s %r' % (tag, i, ty, bbox, t[:90]))
    return len(lost)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    md_path = args[0]
    md = open(md_path, encoding='utf-8').read()
    bad = check_structure(md)
    lost = 0
    if '--loss' in args:
        k = args.index('--loss')
        pages_path = args[k + 1]
        specs = [a.split('=', 1) for a in args[k + 2:] if '=' in a]
        lost = check_loss(md_path, pages_path, specs)
    return 1 if (bad or lost) else 0


if __name__ == '__main__':
    sys.exit(main())
