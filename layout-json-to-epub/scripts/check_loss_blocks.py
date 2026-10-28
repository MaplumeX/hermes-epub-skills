#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保真度自检：源 layout.json 的每个 span 是否都进了 book.md。

用法：
    python3 check_loss_blocks.py book.md A=docA_layout.json B=docB_layout.json ...

为什么不能直接比字符串：
- 源文本多为半角标点（, ; : ? ! ( ) .），book.md 已转全角 —— 不做标点映射会
  满屏假丢失（实测 1565 条 -> 22 条）。
- 脚注引用 [^pN-M]、圈码 ①-⑳、$ \\ { } & | _ ^ * # 与括号都要剥掉再比。
- 表格书的 padding/分隔线会让字符数比值虚高，所以主判据是「逐块前缀命中」，
  字符数比值只做粗筛（应 ≈1.00，<0.97 才是丢块，>1.01 查重复渲染）。

报出来的条目逐条判断，常见正常项：OCR 噪声块（Ground Truth / OCR result）、
重复输出的公式碎片、被删掉的原书目录页、被拆成列表项的索引/译名表行。
"""
import json
import re
import sys

CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
PUN = {',': '，', ';': '；', ':': '：', '?': '？', '!': '！',
       '(': '（', ')': '）', '.': '。'}
STRIP = re.compile(r'[\[\]（）()$\\{}&|_^*#〔〕“”‘’]')


def norm(s):
    s = re.sub(r'\[\^p\d+-\d+\]', '', s)
    s = re.sub('[' + CIRC + ']', '', s)
    s = STRIP.sub('', s)
    s = ''.join(PUN.get(c, c) for c in s)
    return re.sub(r'\s', '', s)


def blocks_of(path):
    """产出正文 span 与页脚注释 span（可选加 discarded header/footer）。"""
    data = json.load(open(path))
    for page in data.get('pdf_info', []):
        for b in page.get('preproc_blocks', []):
            for l in b.get('lines', []):
                for sp in l.get('spans', []):
                    if sp.get('content'):
                        yield sp['content']
        for b in page.get('discarded_blocks', []):
            if b.get('type') == 'page_footnote':
                for l in b.get('lines', []):
                    for sp in l.get('spans', []):
                        if sp.get('content'):
                            yield sp['content']


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    md = open(sys.argv[1]).read()
    mdnz = norm(md)
    print('book.md 非空白字符', len(mdnz))
    total_src = 0
    for arg in sys.argv[2:]:
        tag, _, path = arg.partition('=')
        srcs = list(blocks_of(path))
        total_src += sum(len(re.sub(r'\s', '', s)) for s in srcs)
        miss = []
        for s in srcs:
            n = norm(s)
            if len(n) < 15:
                continue
            if n[:40] not in mdnz:
                miss.append(s[:70])
        print('[%s] span %d，未命中 %d' % (tag, len(srcs), len(miss)))
        for m in miss[:30]:
            print('    ', repr(m))
    if total_src:
        print('源非空白字符', total_src, '比值', round(len(mdnz) / total_src, 4))
    return 0


if __name__ == '__main__':
    sys.exit(main())
