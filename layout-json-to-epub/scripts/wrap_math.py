#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把散落在中文里的 LaTeX 片段包成 $...$（layout-json → markdown 用）。

用法：
    from wrap_math import wrap_math, wrap_math_safe
    md = wrap_math_safe(text)          # 已有 {{FN:1}} / {{MATH:..}} 占位符时用这个

    python3 wrap_math.py < book.md     # stdin -> stdout，可直接试

三条硬规则（都踩过）：
1. 花括号必须配平。\\frac{消费增长率}{生产资料增长率} 里花括号内是中文，
   按「数学字符集」右扩会停在第一个 }，得到 $\\frac{消费增长率}${生产资料增长率}
   → pandoc 报 Could not convert TeX math ... unexpected eof。
2. 右邻是 ^ 或 { 时继续吞（s_{av}^{2}、P_{基年} \\times Q 这种）。
3. 占位符必须先换成私有区 token 再包，否则会被卷进公式。
"""
import re

MATH_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                 "_^{}()+-*/=<>.,;:!'\\ &|[]")
PH_OPEN = '\ue003'
PH_CLOSE = '\ue004'
# 占位符两种：{{MATH:<tex>\ue006 与 {{FN:1}} / {{SUP:x}}
PH_PAT = r'(?:\{\{MATH:[^\ue006]*\ue006|\{\{[A-Z]+:[^}]*\}\})'


def protect(text):
    tokens = []

    def rep(m):
        tokens.append(m.group(0))
        return PH_OPEN + str(len(tokens) - 1) + PH_CLOSE

    return re.sub(PH_PAT, rep, text), tokens


def restore(text, tokens):
    return re.sub(PH_OPEN + r'(\d+)' + PH_CLOSE, lambda m: tokens[int(m.group(1))], text)


def wrap_math(s):
    """就地包裹；不含占位符保护的版本。"""
    pat = re.compile(r'\\[a-zA-Z]+|[_^]\s*\{')
    spans = []
    for m in pat.finditer(s):
        a = m.start()
        while a > 0 and s[a - 1] in MATH_CHARS:      # 向左扩（必须允许 { }）
            a -= 1
        b = m.end()
        while b < len(s) and s[b] in MATH_CHARS:
            b += 1
        lim = min(len(s), b + 120)
        while b < lim:                                # 规则 1+2：配平与续接
            if s[a:b].count('{') > s[a:b].count('}'):
                b += 1
                continue
            if s[b] in '^{':
                b += 1
                continue
            break
        while a < b and s[a] in ' \t,.;:':
            a += 1
        while b > a and s[b - 1] in ' \t,.;:':
            b -= 1
        if b <= a:
            continue
        if spans and a < spans[-1][1]:               # 与上一段重叠 -> 合并
            if b > spans[-1][1]:
                spans[-1] = (spans[-1][0], b)
            continue
        spans.append((a, b))

    out, last = [], 0
    for a, b in spans:
        if a < last:
            continue
        out.append(s[last:a])
        out.append('$' + s[a:b] + '$')
        last = b
    out.append(s[last:])
    return ''.join(out)


def wrap_math_safe(text):
    text, tokens = protect(text)
    return restore(wrap_math(text), tokens)


if __name__ == '__main__':
    import sys
    sys.stdout.write(wrap_math_safe(sys.stdin.read()))
