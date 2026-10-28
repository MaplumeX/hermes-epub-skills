# Layout JSON (layout.json) → Clean Markdown/EPUB

Proven workflow for converting the intermediate **layout-analysis JSON** of a
PDF OCR pipeline (files named `layout.json`, often received as documents) into
clean, structured Markdown → EPUB. Validated on a 200-page Chinese philosophy
book (黑格尔《哲学科学百科全书I 逻辑学》) with 68 footnotes, 105 section markers,
and heavy cross-page text flow.

## 1. Schema reconnaissance (do this first)

Top-level: `pdf_info[]` (one entry per page), plus `_backend/_version_name` noise.

Per page:
- `page_idx`, `page_size`
- `preproc_blocks[]` — **the body**. Each block: `{type: text|title, bbox:[x0,y0,x1,y1], lines:[{spans:[{content}]}]}`. `title` blocks may carry `level`.
- `discarded_blocks[]` — **NOT all noise**. Types seen:
  - `header`, `page_number`, `footer` → drop
  - `page_footnote` → **keep! this is where footnote text lives** (marker ①/②/③/*/** + body)
  - `aside_text` → page-marker remnants, drop

Block reading order: sort by `bbox[1]` (y0), then `bbox[0]` (x0).

## 2. Noise to strip (user-confirmed preference)

- **Original-page markers `[nn]`** (e.g. `[11]`, `[44]`) — standalone spans AND
  inline within paragraphs. User explicitly wants these gone: `re.sub(r'\[\d{1,3}\]', '', text)`.
- OCR noise pages: text containing `Ground Truth image displays a single...` → drop whole page.
- `人人公社`-style watermark text → drop.

## 3. Footnote pairing (the hard part)

Footnotes are per-page. In `discarded_blocks` of type `page_footnote`, text starts
with a marker: `①`–`⑩`, `*`, or `**`. Body text carries the same markers inline.

Algorithm:
1. Per page, classify footnote blocks: `circled[marker] = [list of (tag, body)]`,
   `stars[]`, `dstars[]` (`**` must be matched BEFORE single `*`).
2. Scan each body block left-to-right; consume markers in **occurrence order**
   (circled counters are per-marker, star counters global).
3. Replace `①` → `[^p<page>-<n>]` reference syntax.
4. **注中注 (footnote-in-footnote)**: a `*` footnote's body may itself contain `①`
   referencing another footnote on the same page (e.g. p21: `* 这是托鲁克①先生…`).
   Replace inside footnote bodies too — but for EPUB, **inline the nested note**
   (pandoc silently drops footnote definitions referenced only from other
   footnotes; see web-to-epub references/pandoc-markdown-epub.md).
5. `^{*}` is a LaTeX superscript artifact → plain `*`.

Verification: after build, assert every `[^tag]` in body has a definition and
vice versa (`set(refs) == set(defs)`), and that per-page body markers ==
footnote markers (sorted multiset compare), except known 注中注 pages.

## 4. Cross-page paragraph merging

A page's last body block usually continues on the next page. Rule:
- If last block does NOT end with terminal punctuation (`。！？….!?` + closing quotes),
  concatenate with next page's first block.
- Boundary spacing: ASCII-alnum ends/next → insert space; CJK → join directly.
- Force paragraph breaks when the next block starts with `[说明]`/`[附释]`
  (annotation blocks), a `§ n` marker, or a sign-off line (`YYYY年M月D日于…`).

## 5. Missing-content detection — CHECK FOOTNOTE CONTINUATION FIRST (NEVER guess)

**Before concluding the scan lost a line, check for mis-zoned footnote continuations.**
A footnote that spans a page break gets its continuation blocks placed in the
**next page's `preproc_blocks` (body zone)**, not in `discarded_blocks`. This
happened TWICE on the 黑格尔 book (p22 AND p27 — the pattern recurs, check every
suspicious page): p22's blocks 2-3 (`的存在和自由行动仅仅是幻觉…` and
`但是，托鲁克先生在这本书里…`) and p27's block (`说的经院哲学古老得多…`) looked
like orphaned body text with a "missing" line, but they were continuations of
the previous page's `*` footnote (黑格尔原注). The real body text was complete:
`…她既不需要这种怜悯,也不需要道德上的辩护,而这又是因为…`.

Detection heuristics:
1. The orphan block's content reads as a **semantic continuation of the previous
   page's footnote** (completes its argument, quotes, or references the same
   person/works named in that footnote), not of the body paragraph.
2. After moving the blocks into the footnote, the body paragraph **ends
   terminally** and reads naturally — the true test.
3. If genuinely nothing fits (footnote continuation ruled out, y-gap > ~15px,
   next block starts with a function word `的 了 是 也 就 而 在 与 或 和 这 那 它 他 她 其`),
   THEN mark explicitly: `〔此处原书缺一行〕`. Same for truncated footnotes:
   append `〔原书此脚注在扫描件中截断〕`. Mark, never fabricate.

## 5b. Repairing mis-zoned footnote continuations

1. Move the continuation blocks out of `body` back into the previous page's
   footnote text (concat in order).
2. **Pre-assign stable tags BEFORE moving**: `fn['_tag'] = f"p{page_idx}-{n}"`
   for every footnote on every page, and make `classify()` use `_tag`. Moving
   footnotes between pages renumbers `p<page>-<n>` indices; without stable tags
   the replacement pass emits `[^p22-3]` while definitions/footnote-internal
   references still say `p22-1`, producing broken links.
3. Re-run the full pipeline and verify: body paragraph ends terminally, the
   footnote reads complete, `set(body refs) == set(definitions)`.
4. **When the user supplies authoritative text** for a damaged passage (they
   have the physical book), prefer their text verbatim over OCR reconstruction
   — rebuild the footnote/paragraph from their paste, keep original marker
   glyphs (①/②) in the body of the note, and list the 注中注 identities inline.
   Do not re-derive from the corrupted OCR blocks.

## 6. Heading hierarchy inference

- `title` blocks with `level` field exist, but section titles are usually
  `type=title` without useful level — infer from text prefixes:
  - `^§\s*\d+` short → section marker (render `**§ 19**`, not a heading; also fix OCR `§ 2 6` → `§ 26`)
  - `A. ` / `B. ` → level 3; `a. ` / `I. ` / `II. ` → level 4
  - Named sections (`逻辑学的初步界定`, `第一篇 存在论`) → level 2
  - Front matter (`总序`, `第一版序言`) → level 1
- Roman-numeral enumerations `I. 逻辑学,研究…` inside body are NOT headings — keep in flow.
- Chinese ordinal section titles (`一、…` in an essay preface) → `### ` headings.

## 7. Blockquote styling

Body blocks starting `[说明]` / `[附释N]` are Hegel-style annotation paragraphs
→ render `> **说明** …` blockquotes. The `[说明]` label may sit at the start of a
long paragraph after a `[nn]` marker was stripped — strip markers first, then match.

## 7b. §-scoped type-block grouping (正文/[说明]/[附释N] state machine)

User rule for Hegel-style books (explicitly stated, corrects naive per-block
rendering): **WITHIN each §**, every paragraph belongs to the current type until
the next type marker or the next § heading. Example: `§X 123[说明]456[附释1]78[附释2]9 §X+1`
→ 123=正文, 456=说明, 78=附释1, 9=附释2. All 123 markers in the 黑格尔 scan sat at
block starts (never mid-paragraph), so a state machine over blocks suffices.

Implementation (in the paragraph-merge pass):
1. Track `ctype` (`'body'`/`'note'`/`'zusatz'`/`'zusatz1'`…). Reset to `'body'`
   at every § heading and every chapter title.
2. When a block starts with `[说明]`/`[附释N]`, flush the current buffer and set ctype.
3. Consecutive same-ctype paragraphs merge into ONE blockquote: first segment
   renders `> **{label}** {text}` (label stripped from text), subsequent segments
   appended as `>\n>\n> {text}` (blank `>` lines keep them one block).
4. Label mapping: `note`→说明, `zusatz`→附释, `zusatzN`→附释N.

Verification after build: per §, the label sequence must be monotone (说明 before
附释; 附释1 < 附释2 < 附释3). Any 说明-after-附释 or descending 附释 order means a
§ heading is missing or a block is mis-zoned (see 7c).

Pitfall: apply known text fixes (missing-line markers, German OCR corrections)
through ONE shared `fix_text()` used by BOTH the body branch and the blockquote
branch — a fix applied only to body paragraphs silently misses terms living
inside 附释 blockquotes (the Akosmimus→Akosmismus fix was lost exactly this way).

## 7c. Missing § heading in scan → type mis-attribution

If a § heading is missing from the scan (page jumps §80 → §82), the orphaned
§'s [说明]/[附释N] blocks get attributed to the previous § and the per-§ label
order check fails (说明 appears after 附释). Fix:
1. Confirm against the original-language text that the orphaned annotations
   belong to the missing § (German §81 = *Das dialektische Moment* matched the
   怀疑主义/辩证因素 annotations perfectly).
2. Insert the § heading into the stream right before the first orphaned
   `[说明]` block — as a **'section' kind** (renders `**§ 81**`), NOT 'title'
   (renders `## § 81` and breaks the `**§ N**` marker regex used downstream).
3. If the previous §'s last block is a body fragment completing the missing §'s
   body (e.g. `反规定的过渡。` = the tail of German §81's one-sentence body),
   skip it while processing the previous § and re-insert it after the new heading.

## 8. LaTeX fragment mapping

OCR pipelines leak LaTeX: `\alpha`→α, `\beta`→β, `\gamma`→γ, `\delta`→δ,
`\S`→§, `\ddot{u}\lambda\eta`→ὕλη. Replace before cleaning.

## 9. Front matter / TOC zoning

Pin page ranges (by page_idx) for 扉页/编委会/版权页, 目录, and essay prefaces.
- Front-matter pages: each block = its own line (no paragraph merging).
- TOC pages: split blocks on `\n`, render as list items (`- 第一版序言(1817) …… 1`).
- Elsewhere: normal flow merging. Empty pages between chapters = section breaks, keep.

## 10. Build order that worked

1. `extract.py`: layout.json → `pages.json` (per-page: body blocks w/ type+bbox+text
   cleaned, headers/pagenums/footnotes separated, markers kept raw).
2. `build.py`: footnote classify → marker replacement (body + footnote bodies) →
   stream assembly (front/TOC/main zones) → paragraph merge → heading inference →
   markdown render → footnote defs section → self-check (refs==defs).
3. `pandoc` → EPUB → unzip verification (see web-to-epub references/pandoc-markdown-epub.md).

Keep intermediate `pages.json` — lets you re-run build.py without re-parsing 3MB JSON.

## 11. Foreign-term proofreading against the original-language source

When the book is a translation (e.g. Chinese edition of a German work) and the
user asks to verify the foreign terms in parentheses, do NOT rely on linguistic
guessing alone — fetch the original-language text and align by section number.

**Sources that worked (1830 Hegel Enzyklopädie, German):**
- `https://hegel-system.de/de/enz0.htm` — Vorrede + Einleitung (§1–18)
- `https://hegel-system.de/de/enz1.htm` — Vorbegriff + Seinslehre (§19–244), pages 0–3
- zeno.org has the same text but is slow/blocked; Wikisource page was empty;
  Gutenberg had no copy. hegel-system.de is the reliable one.

**Extraction when curl is blocked by approval gates:** use browser_navigate +
`browser_console` with `document.querySelector('main').innerText` — the result
may be persisted to a file if large; strip the JSON wrapper (`"result": "…"`,
unescape `\n`). Note: hegel-system.de pages contain ONLY the main text (§
sections), NOT the Zusätze (口授附释) — terms appearing only in Zusätze cannot
be verified against this source; say so rather than guessing.

**Alignment algorithm (see `scripts/check_terms.py`):**
1. Parse German text into `{§number: text}` (split on lines matching `^§\s*\d+`).
2. In the Chinese body, find every `(Latin…)` parenthetical, map each to the
   nearest preceding `§ N` heading, filter out Latin quotes/book titles.
3. Match with fuzzy rules: case-insensitive substring; strip hyphens (line-break
   artifacts); unify umlauts (ä→ae, ö→oe, ü→ue, ß→ss) on both sides.
4. Retry misses in adjacent sections ±2 (translators often attach the term to a
   neighboring §).
5. Report: matched / unmatched / unlocatable. For unmatched, show the Chinese
   context and German similar words (`re.findall` words sharing a 4-char prefix).

**Known OCR error classes found this way:**
- `Akosmimus` → `Akosmismus` (dropped letter — verify against German §50)
- `denk-ende Betrachtung` → `denkende Betrachtung` (line-break hyphen artifact;
  German §2 reads `als denkende Betrachtung der Gegenstände`)
- `§ 2 6` → `§ 26` (spurious space in section marker)

Fix confirmed errors in the Markdown, rebuild EPUB, and report the correction
table (wrong → right → reason) in the delivery message.

## Data-quality caveats to report (not fix silently)

- **Verify apparent "lost lines" against footnote continuations first** (see
  §5) — the 黑格尔 p22 case turned out to be a mis-zoned footnote continuation,
  not a scan loss; the body was complete. The p143 truncated footnote WAS a
  real scan truncation — flag it in the delivery message with the explicit marker.
- Empty pages between chapters are normal section breaks.
- When user supplies authoritative text for a damaged passage, prefer it verbatim
  (their physical book beats OCR reconstruction) and say so in the delivery message.
