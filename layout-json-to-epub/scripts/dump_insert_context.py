#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接读成品 EPUB，把每个「插入组」（<hr> 包围的图/表组）连同前后各 3 段原文
导出成可读报告，供人（agent）逐条判断插入位置对不对。

为什么不用纯启发式：位置/归属是语义判断。本类任务里脚本打分会把图搬到错误段落
（实测：按「首次提及」自动重排 279 组，用户下一轮就说「你对插入部分的内容判断
不是很准确」）。正确姿势 = 脚本导出上下文 + 自己读 + 只对读出来的错法动刀。

用法：
    python3 dump_insert_context.py out.epub placement_report.txt

输出两部分：
  1) 报告：每个插入组「前 3 段 / 组内各块 / 后 3 段」
  2) stdout：四类可疑信号统计
       A 紧跟标题之后（组前最近元素是 h1–h4）
       B 组前段落无句末标点（正文可能被切断；**但教科书正文本就跨表格，多数是正常的**）
       C 组前没有任何正文（章首/编首页）
       D 组后首段以接续式字开头（明显是半句续文 → 插入组位置可疑）
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = '{http://www.w3.org/1999/xhtml}'
TERM = re.compile(r'[。！？….!?]["”’』」）)\]]*$')
# 接续式段首：出现这些字开头，说明该段本该接在前一段后面
CONT = re.compile(r'^[的了着过们而就也还又则是在与和及或等其之中上下后前时别格化性者所以为把被从由对向到成出入起来去开作得地]')
INNER_TAGS = (NS + 'p', NS + 'h1', NS + 'h2', NS + 'h3', NS + 'h4',
              NS + 'table', NS + 'hr', NS + 'blockquote', NS + 'ul')


def txt(el, lim=110):
    s = re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()
    return s if len(s) <= lim else s[:lim] + '…'


def main():
    epub = sys.argv[1] if len(sys.argv) > 1 else 'out.epub'
    out = sys.argv[2] if len(sys.argv) > 2 else 'placement_report.txt'
    z = zipfile.ZipFile(epub)

    lines, gid = [], 0
    sig = {'A': [], 'B': [], 'C': [], 'D': []}

    for name in sorted(n for n in z.namelist() if n.endswith('.xhtml')):
        try:
            root = ET.fromstring(z.read(name))
        except ET.ParseError:
            continue
        body = root.find(NS + 'body')
        if body is None:
            continue
        seq = [el for el in body.iter() if el.tag in INNER_TAGS]
        hrs = [i for i, el in enumerate(seq) if el.tag == NS + 'hr']

        for a, b in zip(hrs[0::2], hrs[1::2]):
            inner = seq[a + 1:b]
            has_ins = any(el.tag == NS + 'table' or el.find('.//' + NS + 'img') is not None
                          for el in inner)
            if not has_ins:
                continue
            gid += 1

            parts = []
            for el in inner:
                if el.tag == NS + 'table':
                    rows = el.findall('.//' + NS + 'tr')
                    parts.append('[表格 %d行] %s' % (len(rows), txt(rows[0]) if rows else ''))
                elif el.find('.//' + NS + 'img') is not None:
                    parts.append('[图片]')
                else:
                    parts.append(txt(el, 90))

            prevs = []
            for el in reversed(seq[:a]):
                if el.tag in INNER_TAGS and el.tag != NS + 'hr':
                    t = txt(el)
                    if t:
                        prevs.append(('#' if el.tag.startswith(NS + 'h') else ' ') + t)
                    if len(prevs) >= 3:
                        break
            prevs.reverse()

            nexts = []
            for el in seq[b + 1:]:
                if el.tag in INNER_TAGS and el.tag != NS + 'hr':
                    t = txt(el)
                    if t:
                        nexts.append(('#' if el.tag.startswith(NS + 'h') else ' ') + t)
                    if len(nexts) >= 3:
                        break

            short = name.split('/')[-1]
            cap = next((p for p in parts if re.match(r'^[图表]', p)), '')
            rec = 'G%-4d %-16s %s' % (gid, short, cap[:40])

            if prevs and prevs[-1].startswith('#'):
                sig['A'].append(rec + '  前=' + prevs[-1][1:26])
            if not prevs:
                sig['C'].append(rec)
            elif not prevs[-1].startswith('#') and not TERM.search(prevs[-1]):
                sig['B'].append(rec + '  …' + prevs[-1][-24:])
            if nexts and not nexts[0].startswith('#') and CONT.match(nexts[0].lstrip(' ')):
                sig['D'].append(rec + '  后=' + nexts[0][1:30])

            lines.append('')
            lines.append('===== G%d   %s' % (gid, short))
            for x in prevs:
                lines.append('   前| ' + x)
            lines.append('   ---- 插入组 ----')
            for x in parts:
                lines.append('   组| ' + x)
            lines.append('   ---- 组后 ----')
            for x in nexts:
                lines.append('   后| ' + x)

    open(out, 'w', encoding='utf-8').write('\n'.join(lines))

    print('插入组 %d 个 → %s（%d 行）' % (gid, out, len(lines)))
    for k, label in (('A', '紧跟标题之后'), ('B', '组前段落未结束'),
                     ('C', '组前无正文'), ('D', '组后是接续式开头')):
        print('\n%s %s %d 处' % (k, label, len(sig[k])))
        for r in sig[k][:40]:
            print('   ' + r)
    print('\n提示：B 类多数是教科书正文跨表格的正常排版，别一律强拼；'
          'A/D 两类优先人工核对。')


if __name__ == '__main__':
    main()
