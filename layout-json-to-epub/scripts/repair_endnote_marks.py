#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把被 OCR 误识成普通数字的尾注上标补回为锚点（幂等，可反复跑）。
前提: book.md 里正文标记已是 <a id="enref-c{ch}-{K}" href="#en-c{ch}-{K}"><sup>K</sup></a>，
      书末有 '# 附注' 区，notes.json = {"章号": {"条号": "注文"}}。
用法: python3 repair_endnote_marks.py book.md notes.json
校验（四条全过才插）: ① 章内序号单调且落在前后已知标记区间内 ② 同一取值只取第一个
                      ③ 数字后不得接 年/月/日/世纪/人/个/次/多/余/万… ④ 该章附注确实存在该编号
关键: 数字后允许空格（OCR 常在上标后留空格，写紧接中文会漏掉一半以上）。
"""
import json, re, sys

BOOK, NOTES = sys.argv[1], sys.argv[2]
BAD_AFTER = re.compile(r'^(年|月|日|世纪|年代|时|点|人|名|个|次|多|余|万|亿|千|百|分之|等|以上|天|周|小时|分钟|英里|美元|条|座|艘|支|位|种|户|州|页|卷|章|节|周年)')
CAND = re.compile(r'([。！？”’）\]》])(\s*)(\d{1,3})(?=\s*[\u4e00-\u9fffA-Za-z“《（(])')
CH = re.compile(r'^## 第([一二三四五六七八九十]+)章', re.M)
CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
      '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15, '十六': 16, '十七': 17}


def main():
    md = open(BOOK).read()
    notes = {int(k): {int(n): t for n, t in v.items()} for k, v in json.load(open(NOTES)).items()}
    i = md.find('\n# 附注')
    body, apx = (md[:i], md[i:]) if i > 0 else (md, '')
    chunks = [(CN[m.group(1)], m.start()) for m in CH.finditer(body)]
    added, offset = [], 0
    for k, (ch, pos) in enumerate(chunks):
        end = chunks[k + 1][1] if k + 1 < len(chunks) else len(body)
        seg = body[pos + offset:end + offset]
        known = [(m.start(), int(m.group(1))) for m in re.finditer(r'id="enref-c%d-(\d+)"' % ch, seg)]
        ks = [n for _, n in known]
        missing = [x for x in sorted(notes[ch]) if x not in ks]
        if not missing:
            continue
        flat = re.sub(r'<table.*?</table>', lambda m: ' ' * len(m.group(0)), seg, flags=re.S)
        accepted, last = [], 0
        for m in CAND.finditer(flat):
            val = int(m.group(3))
            if val not in missing or BAD_AFTER.match(flat[m.end():].lstrip()[:3]):
                continue
            s = m.start() + len(m.group(1)) + len(m.group(2))
            lo = max([v for p, v in known if p < s], default=0)
            hi = min([v for p, v in known if p > s], default=10 ** 6)
            if lo < val < hi and val > last:
                accepted.append((s, m.end(), val))
                last = val
        for s, e, val in sorted(accepted, reverse=True):
            seg = (seg[:s] + '<a id="enref-c%d-%d" href="#en-c%d-%d"><sup>%d</sup></a>' % (ch, val, ch, val, val) + seg[e:])
            added.append((ch, val))
        if accepted:
            body = body[:pos + offset] + seg + body[end + offset:]
            offset += len(seg) - (end - pos)
            for c, val in added:
                if c != ch:
                    continue
                pat = '<a id="en-c%d-%d"></a>' % (c, val)
                if pat in apx:
                    j = apx.find(pat)
                    eol = apx.find('\n', j)
                    if 'href="#enref-' not in apx[j:eol]:
                        apx = apx[:eol] + ' <a href="#enref-c%d-%d">↩</a>' % (c, val) + apx[eol:]
    open(BOOK, 'w').write(body + apx)
    print('修补尾注标记 %d 处' % len(added))
    for c, val in added:
        print('  第%d章 +%d' % (c, val))


if __name__ == '__main__':
    main()
