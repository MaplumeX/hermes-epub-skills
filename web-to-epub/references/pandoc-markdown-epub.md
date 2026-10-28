# Pandoc Markdown → EPUB (footnote integrity focus)

Validated on a 150K-char Chinese philosophy book (68 footnotes, 12 chapters).
Use this when the EPUB source is **Markdown** (not scraped HTML) — complements
the main SKILL.md pipeline which handles website HTML.

## Build command

```bash
pandoc book.md -o book.epub \
  --metadata title="…" --metadata author="…" --metadata lang="zh-CN" \
  --toc --toc-depth=3 --epub-chapter-level=2 --metadata date="2026"
```

- `--epub-chapter-level=2` → each `##` section becomes a spine chapter.
- `--toc-depth=3` → nav includes `###`/`####` sub-sections.
- zh-CN translation warnings ("Could not load translations for zh-CN",
  "The term Abstract has no translation") are **harmless** — ignore.
- pandoc ≥2.17 required; `apt-get install -y pandoc` on Debian.

## Footnote integrity — the critical check

pandoc converts `[^tag]:` definitions into per-chapter `<li id="fnN">` blocks
with `↩︎` backlinks. It **silently drops footnote definitions that are only
referenced from inside other footnote definitions** (注中注 / nested notes):
68 defs in Markdown → 67 in EPUB, no error raised.

Fixes:
1. In the Markdown, **inline nested notes** — replace `[^nested-tag]` inside a
   footnote body with the nested note's text (or `〔见下注〕` if keeping it short),
   then delete the nested definition line.
2. Verify AFTER every build by unzipping:

```python
import zipfile, re
z = zipfile.ZipFile('book.epub')
total = 0
for n in sorted(x for x in z.namelist() if x.startswith('EPUB/text/ch')):
    c = z.read(n).decode('utf-8')
    d = len(re.findall(r'id="fn\d+"', c)); r = len(re.findall(r'class="footnote-ref"', c))
    assert d == r, f"{n}: defs {d} != refs {r}"   # per-chapter defs == refs
    total += d
assert total == expected_footnote_count
```

Also spot-check: `EPUB/nav.xhtml` link count/texts vs expected TOC; a sampled
`<h1>/<h2>` anchor exists in its chapter; one `<blockquote>` renders.

## Markdown conventions that carry over well

- `**§ 19**`-style section markers → `<p><strong>` (fine, but don't expect a heading).
- `> **说明** …` blockquotes → `<blockquote>`; the `**label**` stays inside.
- Footnote refs `[^tag]` render as `<a href="#fnN" class="footnote-ref" epub:type="noteref">N</a>`.
- `{...}` pandoc attribute syntax on headings is fine for CJK anchors, but
  CJK heading IDs get transliterated/encoded in nav.xhtml — acceptable.

## Verify with the existing script too

`scripts/verify_epub.py` (XML validity, images, garbage residues) still applies
to pandoc output — run it after the footnote check.
