#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""book.md 图题排版归一化（layout.json 教科书管线通用后处理）

三个 pass，顺序固定：
  1. drop_axis_noise()          删掉被 OCR 读成正文的图内坐标轴标签（白名单，按书定制）
  2. fix_split_figure_text()    图前「图X-Y显示了…」（无句末标点）与图后续文拼回一段，放到图题后
  3. normalize_figures()        图题/面板标签统一加粗，并一律移到该组图之后

用法：
    python3 normalize_figure_captions.py book.md           # 原地改（先存 book.md.bak）
    python3 normalize_figure_captions.py book.md --check   # 只报告不写
    python3 normalize_figure_captions.py book.md --axis axis.txt   # 每行一条轴标签噪声

放在 build.py 之后、pandoc 之前跑；也可把三个函数 import 进 build.py 的 md 后处理链。
"""
import os
import re
import sys

# ---------------------------------------------------------------- 1) 轴标签噪声
# 图内的坐标轴标签常被 OCR 读成独立段落（图里本来就有，正文不该重复）
AXIS_NOISE = set()


def drop_axis_noise(md, noise=None):
    noise = AXIS_NOISE if noise is None else noise
    if not noise:
        return md
    blocks = md.split('\n\n')
    keep = [b for b in blocks if b.strip() not in noise]
    return '\n\n'.join(keep)


# ------------------------------------------------- 2) 被页边界切开的「图X-Y…」正文
TRUNC_FIG = re.compile(r'^图\s*(\d{1,2}[-–—]\d{1,2})')
CONT_START = re.compile(r'^[的了是和与而但并]\S')
TERM_END = re.compile(r'[。！？…”』」）)\]】：；.!?]["”’』」）)\]]*$')


def fix_split_figure_text(md):
    """OCR 把介绍某张图的正文段落切断：前半截（以「图X-Y…」开头、没有句末标点）被塞进
    上一张图的 caption 里，后半截留在图后。把两截拼回一段，放到该图图题/图注之后。"""
    blocks = md.split('\n\n')
    for bi, b in enumerate(blocks):
        st = b.strip()
        m = TRUNC_FIG.match(st)
        if not m or TERM_END.search(st) or len(st) < 20:
            continue
        key = m.group(1)
        ci = next((k for k in range(bi + 1, len(blocks))
                   if blocks[k].strip().startswith('**图%s' % key)
                   or blocks[k].strip().startswith('**图 %s' % key)), None)
        if ci is None:
            continue
        cj = next((k for k in range(ci + 1, min(ci + 6, len(blocks)))
                   if CONT_START.match(blocks[k].strip())), None)
        if cj is None:
            continue
        blocks[cj] = st + blocks[cj].strip()
        blocks[bi] = ''
        return fix_split_figure_text('\n\n'.join(x for x in blocks if x != ''))
    return md


# ---------------------------------------------------------- 3) 图题位置与格式
IMG_B = re.compile(r'^!\[\]\(images/[^)]+\)$')
CAP_B = re.compile(r'^\*{0,2}(图\s*\d{1,2}[-–—]\d{1,2}\s+[^*。？！]{1,50}?)\*{0,2}$')
PANEL_B = re.compile(r'^\*{0,2}(\(\s*[a-fA-F]\s*\)\s*[^*。？！]{1,30}?)\*{0,2}$')


def _fig_cls(b):
    t = b.strip()
    if IMG_B.match(t):
        return 'img'
    if CAP_B.match(t):
        return 'cap'
    if PANEL_B.match(t):
        return 'panel'
    return 'other'


def normalize_figures(md):
    """图题排版统一：① 主图题与面板标签一律加粗；② 图题若排在图前，移到该组图之后。
    只动「图X-Y 标题」「(a) 标题」这种独立成块的短行，不碰正文里提到图号的句子。"""
    blocks = md.split('\n\n')
    out = []
    i = 0
    while i < len(blocks):
        if _fig_cls(blocks[i]) not in ('img', 'cap', 'panel'):
            out.append(blocks[i])
            i += 1
            continue
        j = i
        run = []
        while j < len(blocks) and _fig_cls(blocks[j]) in ('img', 'cap', 'panel'):
            run.append(blocks[j])
            j += 1
        imgs = [b for b in run if _fig_cls(b) == 'img']
        caps = ['**%s**' % CAP_B.match(b.strip()).group(1).strip()
                for b in run if _fig_cls(b) == 'cap']
        panels = ['**%s**' % PANEL_B.match(b.strip()).group(1).strip()
                  for b in run if _fig_cls(b) == 'panel']
        if not imgs:
            out.extend(caps)
            out.extend(panels)
            i = j
            continue
        if len(imgs) == 1:
            out.append(imgs[0])
            out.extend(panels)
            out.extend(caps)
        else:
            if len(panels) == len(imgs) and len(panels) > 1:
                for k, im in enumerate(imgs):
                    out.append(im)
                    out.append(panels[k])
            else:
                out.extend(imgs)
                out.extend(panels)
            out.extend(caps)
        i = j
    return '\n\n'.join(out)


# ------------------------------------------------------------------------ 验收

def report(md):
    blocks = md.split('\n\n')
    before_cap = before_panel = unbold = 0
    for i, b in enumerate(blocks):
        st = b.strip()
        if not (CAP_B.match(st) or PANEL_B.match(st)):
            continue
        if not st.startswith('**'):
            unbold += 1
        j = i + 1
        while j < len(blocks) and not blocks[j].strip():
            j += 1
        nxt = blocks[j].strip() if j < len(blocks) else ''
        k = i - 1
        while k >= 0 and not blocks[k].strip():
            k -= 1
        prev = blocks[k].strip() if k >= 0 else ''
        if IMG_B.match(nxt) and not IMG_B.match(prev):
            if CAP_B.match(st):
                before_cap += 1
            else:
                before_panel += 1
    print('图题在图前: %d | 面板标签在图前: %d | 未加粗: %d' % (before_cap, before_panel, unbold))
    return before_cap + before_panel + unbold


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    check = '--check' in argv
    axis = set()
    if '--axis' in argv:
        ap = argv[argv.index('--axis') + 1]
        axis = {l.strip() for l in open(ap, encoding='utf-8') if l.strip()}
    md = open(path, encoding='utf-8').read()
    before = report(md)
    if check:
        return 0 if before == 0 else 1
    md = drop_axis_noise(md, axis)
    md = fix_split_figure_text(md)
    md = normalize_figures(md)
    open(path + '.bak', 'w', encoding='utf-8').write(open(path, encoding='utf-8').read())
    open(path, 'w', encoding='utf-8').write(md)
    after = report(md)
    print('修复前 %d 项 → 修复后 %d 项（备份 %s.bak）' % (before, after, path))
    return 0 if after == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
