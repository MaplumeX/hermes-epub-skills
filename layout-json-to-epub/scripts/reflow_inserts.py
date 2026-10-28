#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""book.md 后期排版：插图/表格的插入位置与分隔线。

用户要求（原话）：「对于那些插入的内容要移到合适的位置，不要切断正文，同时上下加入分隔线」。

做的事：
  ① 每个「插图/表格组」（fig/table + 题注 + 图释 + 资料来源）上下各加一行 `---`
     （pandoc 渲染成 `<hr />`）；
  ② 若某段正文被插入组从中间切断（T1 无句末标点 → 组 → T2 续文），把组挪到
     该段正文结束之后，T1 与真正的续文重新接成一整段；
  ③ 相邻的同图号重复题注去重（优先保留不以「。」结尾的那条——带句号的其实是
     图释首句被误当题注）。

判断「哪一段才是真正的续文」（按可靠性降序）：
  1. T1 以 ，；：、 结尾 → 紧随插入组之后的那段就是续文；
  2. T1 停在半个词上 → 「末字+首字」二字组在全书出现的次数打分，取最高且 >= MIN_SCORE；
  3. 打分前用 DISC 黑名单排除以「新段落起首字」开头的候选，否则「这里我们…」
     会被当成续文把两段粘成一句。

用法：
    python3 reflow_inserts.py book.md [book_final.md]
    选项：--no-rule 只重排不加分隔线；--tail-marker '# 专业术语表' 指定不参与重排的尾部区起点

退出时打印「接回 N 处」与分隔线对数，供交付说明引用。
"""
import re
import sys

MIN_SCORE = 5
# 不能当作「上一句续文」的段首字（新段落常见的起首词）
DISC = r'^[这那但然因所此同另其第在从对由随当如例值应需我你他她它近目本]'
TERM = re.compile(r'[。！？….!?]["”’』」）)\]]*$')          # 句末
CLAUSE = re.compile(r'[，；：、,;:]["”’』」）)\]]*$')        # 分句未完（逗号/分号/冒号）
RULE = '---'


def kind(s):
    """块类型：fig / table / cap / note / struct / list / text"""
    s = s.strip()
    if not s:
        return 'empty'
    if s.startswith('![]('):
        return 'fig'
    if s.startswith('+---') or s.startswith('|'):
        return 'table'
    if s.startswith('**图') or s.startswith('**表'):
        return 'cap'
    if s.startswith('*') and s.endswith('*') and len(s) < 500:
        return 'note'
    if s.startswith('#') or s.startswith('$$') or s == RULE:
        return 'struct'
    if s.startswith('- ') or s.startswith('>'):
        return 'list'
    return 'text'


def bigram(corpus, a, b):
    """T1 末字 + T2 首字 在全书出现的次数"""
    ta = re.sub(r'[\s。，、；：！？…—“"”’』」）)\]]+$', '', a)[-1:]
    hb = re.sub(r'^[\s“”‘’「『（(《\*]+', '', b)[:1]
    if not ta or not hb:
        return 0
    return corpus.count(ta + hb)


def strip_fn(s):
    return re.sub(r'\[\^[^\]]+\]', '', s)


def dedupe_adjacent_caps(blocks):
    """相邻同图号题注去重：优先保留不以「。」结尾的那条"""
    out = []
    for blk in blocks:
        st = blk.strip()
        k = len(out) - 1
        while k >= 0 and not out[k].strip():      # 找上一个非空块
            k -= 1
        if k >= 0:
            pv = out[k].strip()
            m1 = re.match(r'^\*\*([图表]\s*\d+[A-Za-z]?[-—]\d+)', pv)
            m2 = re.match(r'^\*\*([图表]\s*\d+[A-Za-z]?[-—]\d+)', st)
            if m1 and m2 and m1.group(1).replace(' ', '') == m2.group(1).replace(' ', ''):
                pe = pv.rstrip('*').endswith('。')
                se = st.rstrip('*').endswith('。')
                if pe != se:
                    keep = st if pe else pv     # 带句号的是图释首句，丢掉
                else:
                    keep = st if len(st) > len(pv) else pv
                out[k] = keep
                continue
        out.append(blk)
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'book.md'
    dst = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'book_final.md'
    add_rule = '--no-rule' not in sys.argv
    tail_marker = '# 专业术语表'
    for a in sys.argv[1:]:
        if a.startswith('--tail-marker='):
            tail_marker = a.split('=', 1)[1]

    md = open(src, encoding='utf-8').read()
    pos = md.find(tail_marker)          # 术语表/索引是词条列表，不参与重排
    head, tail = (md[:pos], md[pos:]) if pos > 0 else (md, '')
    corpus = re.sub(r'\s+', '', re.sub(r'!\[[^\]]*\]\([^)]*\)', '', head))

    blocks = head.split('\n\n')
    ks = [kind(b) for b in blocks]

    out, joined, i = [], 0, 0
    while i < len(blocks):
        k = ks[i]
        if k in ('fig', 'cap', 'note', 'table'):
            j = i
            while j < len(blocks) and ks[j] in ('fig', 'cap', 'note', 'table'):
                j += 1
            grp, gk = blocks[i:j], ks[i:j]
            if 'fig' not in gk and 'table' not in gk:
                out.extend([blocks[i], ''])     # 只有题注/图注，交给后面的块处理
                i += 1
                continue

            prev = out[-2] if len(out) >= 2 else ''   # out[-1] 恒为空行
            pick = None
            if kind(prev) == 'text' and not TERM.search(strip_fn(prev)):
                c, cands = j, []
                while c < len(blocks) and len(cands) < 3:
                    if ks[c] == 'text':
                        cands.append(c)
                    elif ks[c] in ('struct', 'list'):
                        break
                    c += 1
                if cands:
                    if CLAUSE.search(strip_fn(prev)):
                        pick = cands[0]
                    else:
                        scored = [(bigram(corpus, prev, blocks[x].strip()), x)
                                  for x in cands
                                  if not re.match(DISC, blocks[x].strip())]
                        if scored:
                            best = max(scored)
                            if best[0] >= MIN_SCORE:
                                pick = best[1]
            if pick is not None:
                between = [blocks[x] for x in range(j, pick) if ks[x] == 'text']
                del out[-2:]
                out.extend([prev.rstrip() + blocks[pick].strip(), ''])
                if add_rule:
                    out.extend([RULE, ''])
                for g in grp:
                    out.extend([g, ''])
                if add_rule:
                    out.extend([RULE, ''])
                for x in between:
                    out.extend([x, ''])
                joined += 1
                i = pick + 1
                continue

            if add_rule:
                out.extend([RULE, ''])
            for g in grp:
                out.extend([g, ''])
            if add_rule:
                out.extend([RULE, ''])
            i = j
            continue

        out.extend([blocks[i], ''])
        i += 1

    out = dedupe_adjacent_caps(out)
    res = '\n'.join(out)
    if tail:
        res = res.rstrip('\n') + '\n\n' + tail
    open(dst, 'w', encoding='utf-8').write(res)

    n_rule = res.count('\n' + RULE + '\n') // 2 if add_rule else 0
    print('接回被切断的正文 %d 处；分隔线 %d 对；输出 %s' % (joined, n_rule, dst))


if __name__ == '__main__':
    main()
