#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多面板图重建：把被 OCR 拆成多个 fig 块的「一张图」合回一个单元。

跑在 build.py 之前，直接改 pages.json（每次从 pages_raw.json 重跑整条链）。

用法:
    python3 rebuild_panels.py pages.json src/ [file1 file2 ...]

src/ 下放原始 layout.json（文件名不带 .json），按页连续切分的顺序；
不给 file 列表时自动 glob 该目录下所有 *.json。

四步（每步的踩坑注释都是实测代价，改之前先读）:
  1 去重   同页某图块 >=80% 面积落在另一更大图块内 -> 重复裁切，丢弃并合并题注
  2 归属   题注(图N-M)与图块贪心配对：竖向距离最小 + 要求横向重叠；
           无横向重叠时只接受「题注纵向在图内且紧贴左右边缘」的侧边题注
  3 标签   只用原始 layout 里真实存在的 (a)/(b)/(c)，缺就留空，绝不臆造
  4 排序   按 y 重叠 >50% 聚成行，行内按 x 左->右，行间自上而下

输出 fig 单元 = {'type':'fig','panels':[{img,label,w,h}],'cap':[...],'fnote':[...]}
build.py 侧需支持 panels（无 panels 时走老的 img 路径）:
    for pn in b['panels']:
        if pn.get('label'): add('*' + pn['label'] + '*'); add()
        if pn['img']: add('![](images/%s)' % pn['img']); add()
    然后照旧输出 cap / fnote。
"""
import glob
import json
import os
import re
import sys

CAPNO = re.compile(r'^图\s*\d+[A-Za-z]?[-—]\d+')   # [A-Za-z]? 必须在 \d+ 之后，否则 图1A-4 类全漏
PANEL = re.compile(r'^[（(]\s*([a-zA-Z])\s*[)）]')


def bt(b):
    return ''.join(s.get('content', '')
                   for l in b.get('lines', []) for s in l.get('spans', [])).strip()


def cl(t):
    return re.sub(r'[\ue000-\ue003]', '', t or '').strip()


def area(b):
    return b['w'] * b['h']


def contained(inner, outer):
    """inner 有多大比例的面积落在 outer 内"""
    ox = min(inner['x0'] + inner['w'], outer['x0'] + outer['w']) - max(inner['x0'], outer['x0'])
    oy = min(inner['y'] + inner['h'], outer['y'] + outer['h']) - max(inner['y'], outer['y'])
    if ox <= 0 or oy <= 0:
        return 0.0
    return (ox * oy) / max(1.0, area(inner))


def main(pages_path, src_dir, files):
    if not files:
        files = [os.path.splitext(os.path.basename(p))[0]
                 for p in sorted(glob.glob(os.path.join(src_dir, '*.json')))]
    RAW = {f: json.load(open(os.path.join(src_dir, f + '.json')))['pdf_info'] for f in files}
    pages = json.load(open(pages_path))

    report, dedup, changed = [], 0, 0
    for gi, p in enumerate(pages):
        figs = [b for b in p['blocks']
                if b['type'] == 'fig' and not (b['w'] < 40 and b['h'] < 40)]
        if len(figs) < 2:
            continue

        # ---- 1. 去重：重复裁切块（整图 + 它的左半/右半裁切）----
        keep = []
        for f in sorted(figs, key=area, reverse=True):
            dup = False
            for k in keep:
                if contained(f, k) >= 0.8 and area(k) >= area(f):
                    k['cap'] = k.get('cap', []) + [c for c in f.get('cap', []) if c not in k.get('cap', [])]
                    k['fnote'] = k.get('fnote', []) + [c for c in f.get('fnote', []) if c not in k.get('fnote', [])]
                    dup = True
                    break
            if not dup:
                keep.append(f)
        if len(keep) < len(figs):
            dedup += len(figs) - len(keep)
        dropped = {id(b) for b in figs if b not in keep}
        figs = keep

        raw = RAW[p['file']][p['pi']]
        rawfigs = []
        for b in raw.get('preproc_blocks', []):
            if b['type'] in ('chart', 'image'):
                subs = [{'type': sb['type'], 'text': bt(sb),
                         'y': sb['bbox'][1], 'x0': sb['bbox'][0], 'x1': sb['bbox'][2]}
                        for sb in b.get('blocks', [])]
                rawfigs.append({'bbox': b['bbox'], 'subs': subs})

        def match_raw(fig):
            best, bd = None, 1e9
            for r in rawfigs:
                d = abs(r['bbox'][1] - fig['y']) + abs(r['bbox'][0] - fig['x0'])
                if d < bd:
                    best, bd = r, d
            return best

        # 面板标签从本页**所有**原始图块收集（被去重丢弃的裁切块上的标签也要）
        caps, plabels = [], []
        for r in rawfigs:
            for sb in r['subs']:
                if sb['type'] not in ('chart_caption', 'image_caption',
                                      'chart_footnote', 'image_footnote'):
                    continue
                t = cl(sb['text'])
                if t and PANEL.match(t):
                    plabels.append({'y': sb['y'], 'x0': sb['x0'], 'x1': sb['x1'], 'label': t})

        for f in figs:
            r = match_raw(f)
            if not r:
                continue
            for sb in r['subs']:
                if sb['type'] not in ('chart_caption', 'image_caption',
                                      'chart_footnote', 'image_footnote'):
                    continue
                t = cl(sb['text'])
                if t and CAPNO.match(t):
                    caps.append({'y': sb['y'], 'text': t, 'x0': sb['x0'], 'x1': sb['x1'], 'fig': f})

        # 2a. 前面步骤(fix_captions 等)塞进 fig['cap'] 的题注也要算进来。
        #     不加这一步，重建会用原始 layout 覆盖掉已修好的题注（症状：图号缺口反弹）。
        have = {CAPNO.match(c['text']).group(0) for c in caps if CAPNO.match(c['text'])}
        for f in figs:
            for c in f.get('cap', []):
                t = cl(c)
                m = CAPNO.match(t)
                if m and m.group(0) not in have:
                    have.add(m.group(0))
                    caps.append({'y': f['y'] + f['h'], 'text': t,
                                 'x0': f['x0'], 'x1': f['x0'] + f['w'], 'fig': f})
        if not caps:
            continue

        # ---- 2. 题注归属（贪心，按竖向距离）----
        pairs = []
        for ci, c in enumerate(caps):
            for fi, f in enumerate(figs):
                d = min(abs(f['y'] + f['h'] - c['y']), abs(c['y'] - f['y']))
                ox = min(f['x0'] + f['w'], c['x1']) - max(f['x0'], c['x0'])
                # 侧边题注：纵向**严格在图内**且横向紧贴图的左右边缘。
                # 写成 f['y']-5 <= c['y'] <= f['y']+f['h']+5 会让下方题注也算侧边，
                # 并排两图（题注 y 只差十几像素）的题注会互换。
                inside = (f['y'] <= c['y'] <= f['y'] + f['h'] - 10) and (
                    c['x0'] >= f['x0'] + f['w'] - 6 or c['x1'] <= f['x0'] + 6)
                if ox <= 0 and not inside:
                    continue
                pairs.append((d, ci, fi))
        pairs.sort()
        cap2fig, used = {}, set()
        for d, ci, fi in pairs:
            if ci in cap2fig or fi in used or d > 140:
                continue
            cap2fig[ci] = fi
            used.add(fi)

        groups = [{'caps': [caps[ci]], 'figs': [figs[fi]]} for ci, fi in sorted(cap2fig.items())]

        # 落选题注（最佳图块已被占用）挂到最近的组，不丢
        for ci, c in enumerate(caps):
            if ci in cap2fig or not groups:
                continue
            g = min(groups, key=lambda g: min(
                abs(m['y'] + m['h'] - c['y']) + abs((m['x0'] + m['w'] / 2) - (c['x0'] + c['x1']) / 2)
                for m in g['figs']))
            g['caps'].append(c)

        # 无题注图块并入竖向最近的组
        for f in figs:
            if any(f in g['figs'] for g in groups) or not groups:
                continue
            g = min(groups, key=lambda g: min(abs(m['y'] - f['y']) for m in g['figs']))
            g['figs'].append(f)

        # ---- 3. 面板标签：横向覆盖到、纵向在图上方/下方 45px 内，且唯一命中 ----
        ymin = min(f['y'] for f in figs)
        seen_pl = set()
        for pl in plabels:
            if pl['y'] < 0:            # 跨页归位占位（标签在上一页末、图在本页）
                pl['y'] = ymin - 5
            key = (pl['label'], round(pl['y'] / 6), round(pl['x0'] / 6))
            if key in seen_pl:
                continue
            seen_pl.add(key)
            cand = [f for g in groups for f in g['figs']
                    if f['x0'] - 20 <= (pl['x0'] + pl['x1']) / 2 <= f['x0'] + f['w'] + 20
                    and f['y'] - 45 <= pl['y'] <= f['y'] + 45]
            if len(cand) != 1 or cand[0].get('plabel'):
                continue
            cand[0]['plabel'] = pl['label']
            if pl.get('blk') is not None:
                pl['blk']['text'] = ''   # 正文里的标签块用完即清空

        # 同图号两个单元：短的是题注，长的（含句号）其实是图释 -> 合并降级
        by_no = {}
        for g in groups:
            for c in g['caps']:
                m = CAPNO.match(c['text'])
                if m:
                    by_no.setdefault(m.group(0).replace(' ', ''), []).append(g)
                    break
        for no, gs in by_no.items():
            if len(gs) < 2:
                continue
            gs.sort(key=lambda g: len(g['caps'][0]['text']))
            keep_g = gs[0]
            for other in gs[1:]:
                keep_g['figs'].extend(other['figs'])
                keep_g.setdefault('extra_note', []).extend(c['text'] for c in other['caps'])
                groups.remove(other)

        # ---- 4. 排序 + 输出单元 ----
        units = []
        for g in groups:
            rows = []
            for b in sorted(g['figs'], key=lambda b: b['y']):
                for r in rows:
                    top = min(x['y'] for x in r)
                    bot = max(x['y'] + x['h'] for x in r)
                    ov = min(b['y'] + b['h'], bot) - max(b['y'], top)
                    if ov > 0.5 * min(b['h'], bot - top):
                        r.append(b)
                        break
                else:
                    rows.append([b])
            rows.sort(key=lambda r: min(x['y'] for x in r))
            ps = [b for r in rows for b in sorted(r, key=lambda b: b['x0'])]
            panels = [{'img': b['img'], 'label': b.get('plabel'), 'w': b['w'], 'h': b['h']} for b in ps]
            labels_txt = {pn['label'] for pn in panels if pn.get('label')}
            fn = list(g.get('extra_note', []))
            for b in ps:
                for x in b.get('fnote', []):
                    t = cl(x)
                    if PANEL.match(t) and any(t == L for L in labels_txt):
                        continue          # 与已用面板标签完全相同的跳过，其余保留
                    fn.append(x)
            caps_txt = [c['text'] for c in sorted(g['caps'], key=lambda c: c['y'])]
            units.append({'type': 'fig', 'panels': panels, 'cap': caps_txt, 'fnote': fn,
                          'y': min(b['y'] for b in ps), 'x0': min(b['x0'] for b in ps),
                          'w': max(b['w'] for b in ps), 'h': sum(b['h'] for b in ps)})
            report.append((gi, p.get('pageno'), ' ／ '.join(caps_txt)[:60], len(ps),
                           sum(1 for x in panels if x['label'])))

        if not units:
            continue

        # **原地替换**：追加到页末会让整组图跑到该页所有正文之后。
        f2u = {}
        for k, g in enumerate(groups):
            for b in g['figs']:
                f2u[id(b)] = units[k]
        emitted, nb = set(), []
        for b in p['blocks']:
            if b['type'] != 'fig':
                nb.append(b)
                continue
            if id(b) in dropped:
                continue
            u = f2u.get(id(b))
            if u is None:
                nb.append(b)
                continue
            if id(u) in emitted:
                continue
            emitted.add(id(u))
            nb.append(u)
        p['blocks'] = nb
        changed += 1

    json.dump(pages, open(pages_path, 'w'), ensure_ascii=False)
    print('去重 %d 块；重建 %d 页 / %d 个图单元' % (dedup, changed, len(report)))
    for r in report:
        print('  idx%-4d p%-5s 面板%d(标签%d)  %s' % (r[0], r[1], r[3], r[4], r[2]))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
