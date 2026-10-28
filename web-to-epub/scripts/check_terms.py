#!/usr/bin/env python3
"""Foreign-term proofreading: Chinese-translation parenthetical terms vs original-language text, aligned by § number.

Usage:
  python3 check_terms.py <german_text.txt> <chinese_book.md> [--json out.json]

German text file: plain text, one § section per block, sections start with a line
matching `^§\s*\d+`. Chinese book: Markdown; parentheticals `(Latin…)` are the
terms to check; `**§ N**` / `^§ N$` lines mark section boundaries.

Output: matched / unmatched / unlocatable counts, then per-unmatched term the
Chinese context and German similar words (shared 4-char prefix).

Known limits: only verifies terms that appear in the German source text; terms
living only in the translation's added commentary (e.g. Zusätze/口授附释) will
show as unmatched — judge by German-language knowledge, don't force a match.
"""
import re, sys, json

def norm_de(s):
    s = re.sub(r'\(\(\d+\)\)', '', s)          # page markers ((nn))
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def parse_sections(de_text):
    secs, cur = {}, None
    for line in de_text.split('\n'):
        line = line.strip()
        m = re.match(r'§\s*(\d+)', line)
        if m:
            cur = int(m.group(1))
            secs.setdefault(cur, [])
            continue
        if cur is not None and line:
            secs[cur].append(line)
    return {k: norm_de(' '.join(v)) for k, v in secs.items()}

def unify(s):
    s = s.lower()
    return (s.replace('ä', 'ae').replace('ö', 'oe')
             .replace('ü', 'ue').replace('ß', 'ss'))

def fuzzy_in(term, de):
    t = term.strip()
    if not t:
        return False
    if t.lower() in de.lower():
        return True
    t2 = t.replace('-', '')
    if t2.lower() in de.lower().replace('-', ''):
        return True
    if unify(t) in unify(de):
        return True
    if unify(t2) in unify(de):
        return True
    return False

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    de_text = open(sys.argv[1], encoding='utf-8').read()
    md = open(sys.argv[2], encoding='utf-8').read()
    out_json = None
    if '--json' in sys.argv:
        out_json = sys.argv[sys.argv.index('--json') + 1]

    de_sections = parse_sections(de_text)
    body = md.split('## 脚注')[0] if '## 脚注' in md else md

    # section boundaries in the Chinese body
    sec_pos = []
    for m in re.finditer(r'\*\*\s*§\s*(\d+)\s*\*\*', body):
        sec_pos.append((m.start(), int(m.group(1))))
    for m in re.finditer(r'^§\s*(\d+)\s*$', body, re.M):
        sec_pos.append((m.start(), int(m.group(1))))
    sec_pos.sort()

    def sec_of(pos):
        cur = None
        for p, n in sec_pos:
            if p <= pos:
                cur = n
            else:
                break
        return cur

    # Latin parentheticals (filter obvious non-terms: book titles, Latin quotes)
    SKIP = {'common sense', 'consensus gentium', 'Tusculanae disputationes',
            'Fermenta Cognitionis', 'sciences exactes', 'infinitum imaginationis',
            'progressus in infinitum', 'medius terminus', 'caput mortuum',
            'philosophus teutonicus', 'index sui et falsi', 'Facta', 'Organon',
            'Kanon', 'Ironie', 'Mysterium', 'Gnosis', 'Paralogismen', 'Energie',
            'Manifestation', 'Spekulation', 'Misologie', 'Ausschließen'}
    terms = []
    for m in re.finditer(r'[（(]([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\s\-\.\'’]{1,80})[）)]', body):
        term = m.group(1).strip()
        if term in SKIP or re.match(r'^(G\.W\.F|E\.|K\.M\.|Theorie|Suhrkamp|Redaktion|Auf der|Erster Teil|Enzyklopädie der|BRIEFE|Verlag|Band|s\.\d)', term):
            continue
        ctx = body[max(0, m.start()-40):m.end()+10]
        terms.append((term, ctx, sec_of(m.start())))

    results = []
    for term, ctx, sec in terms:
        if sec is None:
            results.append((term, ctx, sec, 'NO_SECTION'))
            continue
        de = de_sections.get(sec, '')
        if not de:
            results.append((term, ctx, sec, 'NO_DE'))
            continue
        # exact § first, then adjacent ±2 (translators attach terms loosely)
        found = fuzzy_in(term, de)
        if not found:
            for s in range(max(1, sec-2), sec+3):
                if s in de_sections and fuzzy_in(term, de_sections[s]):
                    found = True
                    break
        results.append((term, ctx, sec, 'OK' if found else 'MISS'))

    ok = [r for r in results if r[3] == 'OK']
    miss = [r for r in results if r[3] == 'MISS']
    nos = [r for r in results if r[3] in ('NO_SECTION', 'NO_DE')]
    print(f"德文原文 § 数: {len(de_sections)}  待校对术语: {len(results)}")
    print(f"✓ 匹配: {len(ok)}   ✗ 未匹配: {len(miss)}   ? 无法定位: {len(nos)}")

    print("\n=== ✗ 未匹配（需人工核对）===")
    for term, ctx, sec, st in miss:
        print(f"§{sec} 「{term}」")
        print(f"  中文上下文: …{ctx}…")
        de = de_sections.get(sec, '')
        t = term.lower().replace('-', '')
        words = re.findall(r'[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]*', de)
        sim = [w for w in words if w.lower().startswith(t[:4]) or t[:4] in w.lower()]
        if sim:
            print(f"  德文相似词: {sim[:6]}")
        print()

    if out_json:
        with open(out_json, 'w') as f:
            json.dump([{'term': t, 'ctx': c, 'sec': s, 'status': st}
                       for t, c, s, st in results], f, ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
