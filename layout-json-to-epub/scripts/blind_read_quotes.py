# -*- coding: utf-8 -*-
"""引文判读的「盲读版」生成与清单合并（配合「一个 subagent 读一章」并行判读）

用法：
  python3 blind_read_quotes.py split book.md read/
  python3 blind_read_quotes.py merge answers.json read/

盲读版的三条硬规则（缺一条就判不准，实测踩过）：
  1. 必须去掉全部 `> ` 引文标记。带着「哪些已经是引文」的暗示去读，模型只会核对
     已有标记、不会去找漏判——实测含标记版 8 章只报 0 处漏判 + 1 处误判，全是照抄
     旧结论；剥标记重派后同一批章补出 20 余段。
  2. 段落顺序编号 [001]…[NNN]，subagent 只回段号，回来靠段号映射回原文。
  3. 剔除脚注定义区（`[^id]:`）、图片、表格、分隔线——它们不是判读单元。

merge 端的指纹归一必须与 build.py 的 norm_head() 完全一致，否则清单静默 0 命中。
"""
import os
import re
import sys

SKIP_HEAD = ('---', '![', '**图', '**表', '|', '+', '[^')


def safe_name(t, n=30):
    t = re.sub(r'[^\w\u4e00-\u9fff]+', '_', t).strip('_')
    return t[:n] or 'chapter'


def split(book_md, outdir):
    md = open(book_md, encoding='utf-8').read()
    os.makedirs(outdir, exist_ok=True)
    # 按 `# ` 一级标题切章
    chunks = re.split(r'(?m)^# ', md)
    made = []
    for i, c in enumerate(chunks[1:], 1):
        title = c.split('\n', 1)[0].strip()
        body = c.split('\n', 1)[1] if '\n' in c else ''
        # 章末译注/注释区不是正文判读对象
        for marker in ('\n## 译注', '\n## 注释'):
            k = body.find(marker)
            if k > 0:
                body = body[:k]
        # 去掉引文标记 —— 盲读的核心
        body = re.sub(r'(?m)^> ?', '', body)
        blocks = [b.strip() for b in re.split(r'\n\n+', body) if b.strip()]
        lines, n = [], 0
        for b in blocks:
            if b.startswith('#'):
                lines.append('\n### ' + b.lstrip('# ').strip())
                continue
            if b.startswith(SKIP_HEAD):
                continue
            n += 1
            lines.append('[%03d] %s' % (n, b))
        fn = os.path.join(outdir, '%02d_%s.md' % (i, safe_name(title)))
        open(fn, 'w', encoding='utf-8').write('\n'.join(lines))
        chars = len(re.sub(r'\s', '', '\n'.join(lines)))
        made.append((fn, n, chars))
        print('%-46s 段落 %-4d 字符 %d' % (os.path.basename(fn)[:44], n, chars))
    return made


def norm_head(s, n=24):
    """与 build.py 的 norm_head 同一套归一化——两边不一致清单就静默 0 命中"""
    t = re.sub(r'\{\{MARK:[^}]*\}\}', '', s)
    t = re.sub('\\{\\{MATH:(.*?)\ue000', r'\1', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\[\^[^\]]+\]', '', t)
    for a, b in (('\u201c', '"'), ('\u201d', '"'), ('\u300c', '"'), ('\u300d', '"'),
                 ('\u2018', "'"), ('\u2019', "'")):
        t = t.replace(a, b)
    t = re.sub(r'[\\${}^_*]', '', t)
    t = re.sub(r'\s+', '', t)
    return t.lstrip('"\'')


def merge(answers_json, readdir, out=None):
    """answers.json 形如 {"05": [1, 23, 34], "06": [...], ...}，键是 read 文件序号"""
    import json
    answers = json.load(open(answers_json, encoding='utf-8'))
    heads, missing = [], []
    for fn in sorted(os.listdir(readdir)):
        if not fn.endswith('.md'):
            continue
        want = set(answers.get(fn[:2], []))
        if not want:
            continue
        s = open(os.path.join(readdir, fn), encoding='utf-8').read()
        idx = {int(m.group(1)): m.group(2).strip()
               for m in re.finditer(r'^\[(\d{3})\] (.+?)(?=^\[|\Z)', s, re.M | re.S)}
        for n in sorted(want):
            if n not in idx:
                missing.append((fn, n))
                continue
            h = norm_head(idx[n])[:24]
            if len(h) < 12:
                missing.append((fn, n, 'too short'))
                continue
            heads.append(h)
    lines = ['# 共 %d 条' % len(heads), 'QUOTE_PARAS = [']
    lines += ["    '%s'," % h.replace("'", "\\'") for h in heads]
    lines.append(']')
    txt = '\n'.join(lines)
    if out:
        open(out, 'w', encoding='utf-8').write(txt + '\n')
        print('写入 %s（%d 条）' % (out, len(heads)))
    else:
        print(txt)
    if missing:
        print('# 未找到：%r' % (missing,), file=sys.stderr)
    return heads, missing


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] not in ('split', 'merge'):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == 'split':
        split(sys.argv[2], sys.argv[3])
    else:
        merge(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
