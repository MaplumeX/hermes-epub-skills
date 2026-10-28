#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从原扫描 PDF 读回被 OCR 整处丢掉的上标编号，过三道闸后写回 book.md。

适用：layout.json → book.md 已建好，但尾注/脚注的正文上标在 OCR 阶段被整处删除，
      布局数据里既无 span 也无残留数字（丢弃块/ref_text/独立数字块查过为 0）。
      此时唯一可靠补救 = 让多模态模型看扫描页图，读出「上标数字 + 它前面的字」。

三段式（可断点续跑）：
  1) locate  SCAN_PDF=上册.pdf python3 read_marks_from_scan.py locate <book.md> <pages.json> <outdir>
       → 算各章缺号 → 反查承载缺号的扫描页 → 250dpi 裁剪渲染 → outdir/pages_todo.json
  2) read    /usr/local/lib/hermes-agent/venv/bin/python read_marks_from_scan.py read <outdir>
       → 逐页调 Hermes 辅助视觉模型，写 outdir/marks_read.json（每页立即落盘，可中断重跑）
       注：这一段的解释器必须是 Hermes venv（系统 python3 没有 openai 模块）；
           整段建议 terminal(background=true) 跑，84 页约 30-40 分钟。
  3) apply   python3 read_marks_from_scan.py apply <book.md> <pages.json> <notes.json> <outdir>
       → 三道闸校验后插入锚点 + 附注条目补 ↩，覆盖 book.md（先备份 book.md.bak）

约定：book.md 正文与「附注/注释」区分界为第一个行首 `# 附注` 或 `# 注释`；
      notes.json = {章号(int/str): {注号: 文本}}；pages.json 每页 {pi, pageno, items[{kind,text}]}；
      锚点格式 <a id="enref-c{ch}-{N}" href="#en-c{ch}-{N}"><sup>N</sup></a>
      对应附注条目 <a id="en-c{ch}-{N}"></a>N. 文本 <a href="#enref-c{ch}-{N}">↩</a>
"""
import json, os, re, subprocess, sys

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
      '十': 10, '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15, '十六': 16, '十七': 17,
      '十八': 18, '十九': 19, '二十': 20, '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24,
      '二十五': 25, '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30}
DPI = int(os.environ.get('MARK_DPI', '250'))
SC = DPI / 72.0
# 正文页面裁剪（单位 pt，去掉页眉页脚）：CROP_X CROP_Y CROP_W CROP_H
CX = float(os.environ.get('CROP_X', '55')); CY = float(os.environ.get('CROP_Y', '42'))
CW = float(os.environ.get('CROP_W', '487')); CH = float(os.environ.get('CROP_H', '760'))
PROMPT = ('这是一页中文书籍的扫描图。正文里句末标点（。！？”）后面常常紧跟一个【小号上标数字】，'
          '那是尾注/注释编号（例如：……的贡献。”18 里的 18）。\n'
          '请逐条列出本页出现的所有上标数字，每条格式为：\n'
          '上标数字 | 它前面紧邻的 6~12 个汉字（原样照抄，不要改写，不要加标点）\n'
          '看不清的写「看不清」。没有上标的地方不要列。不要解释，不要总结，只输出列表。')


def norm(s):
    """中英文数字白名单。不要用 \\uXXXX 字符类——经工具调用/heredoc 传递会多一层反斜杠而静默剥掉全部中文。"""
    return ''.join(c for c in (s or '') if c.isalnum())


def load_book(path):
    md = open(path, encoding='utf-8').read()
    m = re.search(r'(?m)^#\s*(附注|注释|尾注)\s*$', md)
    return md, (md[:m.start()], md[m.start():]) if m else (md, md, '')


def chapter_spans(body):
    spans, cur, st = [], None, None
    for m in re.finditer(r'(?m)^##\s*第([一二三四五六七八九十]+)章', body):
        if cur is not None:
            spans.append((cur, st, m.start()))
        cur = CN.get(m.group(1)); st = m.end()
    if cur is not None:
        spans.append((cur, st, len(body)))
    return spans


def cmd_locate(book, pages_path, outdir):
    md, body, _ = load_book(book)
    pages = json.load(open(pages_path, encoding='utf-8'))['pages']
    pmap = {p['pi']: p for p in pages}
    notes_path = os.environ.get('NOTES_JSON', os.path.join(os.path.dirname(book), 'notes.json'))
    notes = json.load(open(notes_path, encoding='utf-8'))
    pdf = os.environ['SCAN_PDF']
    os.makedirs(outdir, exist_ok=True)

    # 页 → 章（用 title 块切章）；无页码或页码 ≥ 附注起始页的排除
    cur, page_ch, chap_pages = None, {}, {}
    CH_T = re.compile(r'第([一二三四五六七八九十]+)章')
    for p in pages:
        for it in p['items']:
            if it.get('kind') == 'title':
                m = CH_T.search(it['text'].replace(' ', ''))
                if m and m.group(1) in CN:
                    cur = CN[m.group(1)]; break
        page_ch[p['pi']] = cur
        if cur:
            chap_pages.setdefault(cur, []).append(p['pi'])

    # 每章：拼接串 + 页边界（必须用累计字符数！用 len(buf) 会静默全错）
    chapter_text = {}
    for ch, plist in chap_pages.items():
        buf, bounds, total = [], [], 0
        for pi in plist:
            txt = norm(''.join(it.get('text', '') for it in pmap[pi]['items']))
            bounds.append((total, total + len(txt), pi, pmap[pi]['pageno']))
            total += len(txt); buf.append(txt)
        chapter_text[ch] = (''.join(buf), bounds)

    def locate(ch, key):
        text, bounds = chapter_text.get(ch, ('', []))
        k = norm(key)
        if len(k) < 6:
            return None
        wins = [k[i:i + 12] for i in range(0, max(1, len(k) - 11), 6)]
        for w in [w for w in wins if len(w) >= 8]:
            pos = text.find(w)
            if pos >= 0:
                for a, b, pi, pageno in bounds:
                    if a <= pos < b:
                        return pi
        return None

    jobs, missing_stat = {}, {}
    for ch, a, b in chapter_spans(body):
        if ch not in chapter_text:
            continue
        seg = body[a:b]
        linked = set(int(x) for x in re.findall(r'id="enref-c%d-(\d+)"' % ch, seg))
        miss = sorted(set(int(k) for k in notes[str(ch)]) - linked)
        missing_stat[ch] = miss
        marks = sorted((m.start(), int(m.group(1)))
                       for m in re.finditer(r'id="enref-c%d-(\d+)"' % ch, seg))
        for n in miss:
            prev = [x for x in marks if x[1] < n]      # 前后已链接标记夹逼
            nxt = [x for x in marks if x[1] > n]
            lo = prev[-1][0] if prev else 0
            if prev:
                j = seg.find('</a>', lo); lo = j + 4 if j >= 0 else lo
            hi = nxt[0][0] if nxt else len(seg)
            sp = re.sub(r'<[^>]+>', '', seg[lo:hi])
            p1, p2 = locate(ch, sp[:80]), locate(ch, sp[-60:])
            if p1 is not None and p2 is not None:
                jobs[(ch, n)] = (min(p1, p2), max(p1, p2))

    page_jobs = {}
    for (ch, n), (a2, b2) in jobs.items():
        for pi in range(a2, b2 + 1):
            page_jobs.setdefault(pi, set()).add('%d.%d' % (ch, n))

    todo = []
    for pi in sorted(page_jobs):
        pageno = pmap[pi]['pageno']
        if not pageno or not str(pageno).isdigit():
            continue
        pdfpage = pi + 1
        prefix = os.path.join(outdir, 'p%03d' % pdfpage)
        hits = [x for x in os.listdir(outdir) if x.startswith('p%03d-' % pdfpage) and x.endswith('.png')]
        if not hits:
            subprocess.run(['pdftoppm', '-f', str(pdfpage), '-l', str(pdfpage), '-r', str(DPI),
                            '-x', str(int(CX * SC)), '-y', str(int(CY * SC)),
                            '-W', str(int(CW * SC)), '-H', str(int(CH * SC)),
                            '-png', pdf, prefix], check=True)
            hits = [x for x in os.listdir(outdir) if x.startswith('p%03d-' % pdfpage) and x.endswith('.png')]
        if hits:
            todo.append({'pdfpage': pdfpage, 'pageno': pageno, 'pi': pi,
                         'marks': sorted(page_jobs[pi], key=lambda s: (int(s.split('.')[0]), int(s.split('.')[1]))),
                         'img': os.path.join(outdir, hits[0])})
    json.dump(todo, open(os.path.join(outdir, 'pages_todo.json'), 'w'), ensure_ascii=False, indent=1)
    print('缺号 %d 个，定位到 %d 个，待读页 %d 页'
          % (sum(len(v) for v in missing_stat.values()), len(jobs), len(todo)))


def cmd_read(outdir):
    sys.path.insert(0, '/usr/local/lib/hermes-agent')
    import agent.auxiliary_client as A          # noqa: E402（必须在 venv 解释器下运行）
    todo = json.load(open(os.path.join(outdir, 'pages_todo.json'), encoding='utf-8'))
    nbfile = os.path.join(outdir, 'marks_read.json')
    done = json.load(open(nbfile, encoding='utf-8')) if os.path.exists(nbfile) else {}
    prov, client, model = A.resolve_vision_provider_client()
    print('视觉模型: %s / %s' % (prov, model), flush=True)
    import base64, time
    for i, t in enumerate(todo):
        key = 'p%d' % t['pdfpage']
        if done.get(key, {}).get('resp'):
            continue
        b64 = base64.b64encode(open(t['img'], 'rb').read()).decode()
        msg = [{'role': 'user', 'content': [
            {'type': 'text', 'text': PROMPT},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b64}}]}]
        try:
            # 推理型视觉模型：temperature 低 + max_tokens 放宽，否则 content 为空、答案只在 reasoning_content
            r = client.chat.completions.create(model=model, messages=msg,
                                               temperature=0.1, max_tokens=4000)
            m0 = r.choices[0].message
            resp = m0.content or getattr(m0, 'reasoning_content', None) or ''
        except Exception as e:
            resp = 'ERROR: %s %s' % (type(e).__name__, str(e)[:200])
        done[key] = {'pdfpage': t['pdfpage'], 'pageno': t['pageno'], 'pi': t['pi'],
                     'marks': t['marks'], 'resp': resp, 'model': model}
        json.dump(done, open(nbfile, 'w'), ensure_ascii=False, indent=1)
        print('[%d/%d] 页%s → %s' % (i + 1, len(todo), t['pageno'],
                                     (resp or '')[:160].replace('\n', ' / ')), flush=True)
        time.sleep(0.5)
    print('完成 %d 页' % len(done), flush=True)


def cmd_apply(book, pages_path, notes_path, outdir):
    md, body, apx = load_book(book)
    pages = json.load(open(pages_path, encoding='utf-8'))['pages']
    pmap = {p['pi']: p for p in pages}
    notes = json.load(open(notes_path, encoding='utf-8'))
    reads = json.load(open(os.path.join(outdir, 'marks_read.json'), encoding='utf-8'))

    cur, page_ch = None, {}
    CH_T = re.compile(r'第([一二三四五六七八九十]+)章')
    for p in pages:
        for it in p['items']:
            if it.get('kind') == 'title':
                m = CH_T.search(it['text'].replace(' ', ''))
                if m and m.group(1) in CN:
                    cur = CN[m.group(1)]; break
        page_ch[p['pi']] = cur

    info = {}
    for ch, a, b in chapter_spans(body):
        seg = body[a:b]
        marks = sorted((m.start(), int(m.group(1)))
                       for m in re.finditer(r'id="enref-c%d-(\d+)"' % ch, seg))
        info[ch] = {'a': a, 'b': b, 'marks': marks,
                    'missing': sorted(set(int(k) for k in notes[str(ch)]) - set(n for _, n in marks))}

    # 规范化索引：全字符 + 仅汉字两种，用于回退匹配
    bnorm, bidx, bcj, bcjidx = [], [], [], []
    for i2, c2 in enumerate(body):
        if c2.isalnum():
            bnorm.append(c2); bidx.append(i2)
        if '\u4e00' <= c2 <= '\u9fff':
            bcj.append(c2); bcjidx.append(i2)
    bnorm, bcj = ''.join(bnorm), ''.join(bcj)

    LINE = re.compile(r'^\s*(\d{1,3})\s*[|｜]\s*(.+?)\s*$', re.M)
    ins, seen, reject = [], {}, []
    for key, e in reads.items():
        if not e.get('resp') or e['resp'].startswith('ERROR'):
            continue
        ch = page_ch.get(e['pi'])
        if ch not in info:
            continue
        page_txt = norm(''.join(it.get('text', '') for it in pmap[e['pi']]['items']))
        for num_s, ctx in LINE.findall(e['resp']):
            num, ctx = int(num_s), norm(ctx)
            is_ctrl = num not in info[ch]['missing']
            if is_ctrl and num not in set(n for _, n in info[ch]['marks']):
                reject.append((ch, num, '号不在本章注释表内')); continue
            if (ch, num) in seen:
                continue
            probe, hang = ctx[-8:], False
            if probe and len([m for m in re.finditer(re.escape(probe), page_txt)]) != 1:
                cj = ''.join(c3 for c3 in probe if '\u4e00' <= c3 <= '\u9fff')
                pcj = ''.join(c3 for c3 in page_txt if '\u4e00' <= c3 <= '\u9fff')
                if len(cj) < 6 or len([m for m in re.finditer(re.escape(cj), pcj)]) != 1:
                    reject.append((ch, num, '前文在本页不唯一')); continue
                probe, hang = cj, True
            if is_ctrl:
                seen[(ch, num)] = True      # 控制读数只用于评估准确率，不插入
                continue
            hay, imap = (bcj, bcjidx) if hang else (bnorm, bidx)
            pos = hay.find(probe)
            if pos < 0 or len([m for m in re.finditer(re.escape(probe), hay)]) != 1:
                reject.append((ch, num, '前文在正文中未找到或不唯一')); continue
            j = imap[pos + len(probe) - 1] + 1
            while j < len(body) and body[j] in '。””！？!?…"\'」』）)':
                j += 1
            ms = [(m.start() + info[ch]['a'], int(m.group(1)))
                  for m in re.finditer(r'id="enref-c%d-(\d+)"' % ch, body[info[ch]['a']:info[ch]['b']])]
            if not [p2 for p2, n2 in ms if n2 < num and p2 <= j] or \
               not [p2 for p2, n2 in ms if n2 > num and p2 >= j]:
                reject.append((ch, num, '插入位置不在相邻已链接标记之间')); continue
            seen[(ch, num)] = True
            ins.append((j, ch, num))

    for j, ch, num in sorted(ins, reverse=True):
        body = body[:j] + '<a id="enref-c%d-%d" href="#en-c%d-%d"><sup>%d</sup></a>' % (ch, num, ch, num, num) + body[j:]
    fixed = 0
    for j, ch, num in ins:
        pat = re.compile(r'(<a id="en-c%d-%d"></a>[^\n]*?)$' % (ch, num), re.M)
        if pat.search(apx) and 'enref-c%d-%d' % (ch, num) not in pat.search(apx).group(1):
            apx = pat.sub(lambda mm: mm.group(1) + ' <a href="#enref-c%d-%d">↩</a>' % (ch, num), apx, count=1)
            fixed += 1
    open(book + '.bak', 'w').write(md)
    open(book, 'w').write(body.rstrip() + '\n\n' + apx)
    print('插入 %d 条，附注补 ↩ %d 条，拒绝 %d 条' % (len(ins), fixed, len(reject)))
    for r in reject:
        print('  拒绝: 第%s章 注%s — %s' % r)
    print('下一步：重跑 pandoc + fix_epub_links.py + validate_epub.py，并核对逐章链接数')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'locate':
        cmd_locate(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'read':
        cmd_read(sys.argv[2])
    elif cmd == 'apply':
        cmd_apply(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        print(__doc__)
