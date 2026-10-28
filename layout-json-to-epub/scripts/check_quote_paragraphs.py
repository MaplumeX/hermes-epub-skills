# -*- coding: utf-8 -*-
"""列出 book.md 里「段末带出处」的段落，供人工判定哪些是整段引文（→ blockquote）。

背景：用户要求「独立成段、段末带出处的整段引文」用引用格式，但**作者本人的分析段**
（段末也带出处）和**段末引语**（正文里“…”恰在段尾）不能转。单靠正则会把这两类
一起误伤（某书实测 77 个候选里只有 57 个该转，另 20 个是段末引语、100 个是分析段），
所以本脚本只负责把候选**导出成可读清单**，判定必须人读原文。

用法：
    python3 check_quote_paragraphs.py book.md            # 列出「未转引用」的候选
    python3 check_quote_paragraphs.py book.md --quoted   # 列出「已转引用」的段落（复核用）

判定后把整段引文的**段首 15–20 字指纹**写进 build 的 QUOTE_STARTS 常量，
去空白去标记后 startswith 比对（指纹可审计、判错改一行）。
"""
import re
import sys

# 段末出处：全角括号包裹的「第N页」/「第N—M页」，允许尾随句号
CIT = re.compile(r'（[^（）]{0,90}?第\s*[\d、—\-]+\s*页[^（）]{0,25}）[。．.]?$')
# 非正文块的行首
SKIP_PREFIX = ('#', '---', '![', '- ', '**图', '**表', '|', '+', '*', '>', '[^')


def main(path, show_quoted=False):
    md = open(path, encoding='utf-8').read()
    blocks = [b.strip() for b in re.split(r'\n\n+', md)]
    heads = [(m.start(), m.group(1)) for m in re.finditer(r'\n# ([^\n]+)', md)]

    n = 0
    for i, b in enumerate(blocks):
        if not b:
            continue
        quoted = b.startswith('> ')
        body = b[2:] if quoted else b
        if body.startswith(SKIP_PREFIX):
            continue
        if not CIT.search(body):
            continue
        if quoted != show_quoted:
            continue

        n += 1
        pos = md.find(b[:30])
        chs = [h for p, h in heads if p < pos]
        ch = chs[-1] if chs else '(front matter)'
        prev = blocks[i - 1][-30:].replace('\n', ' ') if i else ''
        plain = re.sub(r'<[^>]+>', '', body)
        has_q = '“' in body
        print('【%d】%s | 段内引号=%s | 前段…%s' % (n, ch[:26], '有' if has_q else '无', prev))
        print('    %s' % plain[:160])
        print()

    print('合计 %d 段（%s）' % (n, '已转引用，复核用' if show_quoted else '未转引用，待人工判定'))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    main(args[0] if args else 'book.md', '--quoted' in sys.argv)
