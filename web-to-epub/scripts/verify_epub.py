#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EPUB 质量验证（web-to-epub 技能配套）。

用法: ./epubenv/bin/python verify_epub.py <book.epub>
检查: XML 合法性 / 图片引用完整性 / 垃圾字符残留 / 元数据 / 正文字数。
依赖: pip install lxml
"""
import sys, os, re, zipfile
from lxml import etree

epub_path = sys.argv[1] if len(sys.argv) > 1 else "book.epub"
z = zipfile.ZipFile(epub_path)

print("=== XML 校验 ===")
ok = True
for n in z.namelist():
    if n.endswith((".xhtml", ".opf", ".ncx")):
        try:
            etree.fromstring(z.read(n))
        except Exception as e:
            ok = False
            print(f"  FAIL {n}: {e}")
print("  全部合法" if ok else "  有失败")

# 图片引用完整性
print("\n=== 图片引用 ===")
missing, img_count = [], 0
for n in z.namelist():
    if n.startswith("EPUB/") and n.endswith(".xhtml"):
        c = z.read(n).decode("utf-8")
        for m in re.finditer(r'<img[^>]*src="([^"]*)"', c):
            img_count += 1
            if f"EPUB/{m.group(1)}" not in z.namelist():
                missing.append((n, m.group(1)))
print(f"  图片引用 {img_count} 处; 缺失: {missing if missing else '无'}")

# 垃圾字符残留
print("\n=== 垃圾残留 ===")
all_text = ""
for n in z.namelist():
    if n.endswith(".xhtml"):
        all_text += z.read(n).decode("utf-8", errors="replace")
bad = 0
for pat in ["\u0000", "@@BR@@", "�", "&lt;a id=", "<v:", "![if", "msEquation", "MsoNormal"]:
    cnt = all_text.count(pat)
    if cnt:
        bad += cnt
        print(f"  {pat!r}: {cnt} 处")
print("  无" if bad == 0 else f"  共 {bad} 处残留!")

# 元数据
print("\n=== OPF 元数据 ===")
opf = z.read("EPUB/content.opf").decode("utf-8")
for tag in ["dc:title", "dc:creator", "dc:language", "dc:publisher", "dc:date"]:
    m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", opf)
    print(f"  {tag}: {m.group(1) if m else 'MISSING'}")

# 正文字数
total = 0
for n in z.namelist():
    if re.match(r"EPUB/chap_\d+\.xhtml", n):
        text = re.sub(r"<[^>]+>", "", z.read(n).decode("utf-8"))
        total += len(re.sub(r"\s+", "", text))
print(f"\n总正文: {total} 字符 | 文件: {os.path.getsize(epub_path)//1024} KB")
