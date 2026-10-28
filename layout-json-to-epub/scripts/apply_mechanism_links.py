#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 references/mechanisms/*.md 应用「相关篇」互链与「双归属」标记（幂等）。

用法：
    python3 apply_mechanism_links.py [技能目录]
    缺省技能目录 = 本脚本所在技能（scripts/ 的上一级）

设计：
- 互链表是 `scripts/mechanism_links.json`（REL + DUAL），**不是 md 文件**。
  mechanisms/*.md 可能被重新生成，手写进去的互链会丢；改互链只改 JSON 再重跑本脚本。
- 幂等：每次先剥掉已有的 `## 相关篇` 段和 `- 双归属 →` 行，再按 JSON 重新注入。
  所以可以反复跑，结果稳定。

互链的两个层次：
  1. `## 相关篇`（篇头）：这一篇和哪些邻篇相交、为什么 —— 35 条
  2. `- 双归属 → **Mx**（原因）`（条目下）：某条实测结论跨两个机制，
     正文只在主归属篇写一份，这里只放指针 —— 21 条
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MECH_DIR = os.path.join(os.path.dirname(HERE), 'references', 'mechanisms')
LINKS = os.path.join(HERE, 'mechanism_links.json')

REL_SECTION = re.compile(r'^## 相关篇\n(?:.*\n)*?(?=^## |\Z)', re.M)
DUAL_LINE = re.compile(r'^\s+- 双归属 → .*\n', re.M)


def rel_block(items):
    if not items:
        return ''
    out = ['## 相关篇', '',
           '> 一条结论常跨两个机制：**正文只在主归属那篇写一份**，这里只放指针。', '']
    for other, why in items:
        out.append('- **%s** —— %s' % (other, why))
    out.append('')
    return '\n'.join(out) + '\n'


def apply_dual(text, duals, fname):
    """在命中条目下方插一行标记；不改动原条目文字"""
    if not duals:
        return text
    lines = text.split('\n')
    out = []
    for ln in lines:
        out.append(ln)
        if not ln.startswith('- '):
            continue
        body = ln[2:]
        for pat, other, why in duals:
            if body.startswith(pat.lstrip('-')):
                out.append('  - 双归属 → **%s**（%s）' % (other, why))
                break
    return '\n'.join(out)


def main(skill_dir=None):
    if skill_dir is None:
        skill_dir = os.path.dirname(HERE)
    mech_dir = os.path.join(skill_dir, 'references', 'mechanisms')
    links = json.load(open(LINKS, encoding='utf-8'))
    rel = {k: [tuple(x) for x in v] for k, v in links['REL'].items()}
    dual_by_file = {}
    for fname, pat, other, why in links['DUAL']:
        dual_by_file.setdefault(fname, []).append((pat, other, why))

    # 篇号 → 文件名（从 SKILL.md 的索引表取，或按 REL 的键推）
    idx = {}
    for mech in rel:
        idx[mech] = None
    total_rel = total_dual = 0
    for fname in sorted(os.listdir(mech_dir)):
        if not fname.endswith('.md'):
            continue
        path = os.path.join(mech_dir, fname)
        text = open(path, encoding='utf-8').read()

        # 1. 剥旧
        text = REL_SECTION.sub('', text)
        text = DUAL_LINE.sub('', text)

        # 2. 找本篇的 mech 键（按文件名反查 META 里的 fname）
        mech = next((k for k in rel if FNAME.get(k) == fname), None)
        # 3. 注入
        block = rel_block(rel.get(mech, [])) if mech else ''
        if block:
            # 插在首个 `## ` 之前（即篇头元信息之后）
            m = re.search(r'^## ', text, re.M)
            pos = m.start() if m else len(text)
            text = text[:pos] + block + text[pos:]
            total_rel += len(rel.get(mech, []))
        duals = dual_by_file.get(fname, [])
        if duals:
            text = apply_dual(text, duals, fname)
            total_dual += len(duals)

        text = re.sub(r'\n{3,}', '\n\n', text)
        open(path, 'w', encoding='utf-8').write(text)

    print('相关篇指针 %d 条，双归属标记 %d 条' % (total_rel, total_dual))


# mech 键 → 文件名（与 SKILL.md 机制篇索引一致）
FNAME = {
    'M1-inputs': 'inputs.md',
    'M2-page-break': 'page-break-merge.md',
    'M3-notes': 'notes.md',
    'M4-figures': 'figures.md',
    'M5-tables-math': 'tables-math.md',
    'M6-quotes': 'quotes.md',
    'M7-structure': 'structure-noise.md',
    'M8-assembly': 'assembly.md',
    'M9-checks': 'checks.md',
    'M10-external': 'external-ref.md',
}

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
