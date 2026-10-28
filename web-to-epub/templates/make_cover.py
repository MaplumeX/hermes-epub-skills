#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EPUB 封面生成（web-to-epub 技能配套）。

深红底 + 米色字，文泉驿正黑中文字体。改 SAVE_PATH / 书名 / 作者行即可。
依赖: pip install pillow
"""
from PIL import Image, ImageDraw, ImageFont

SAVE_PATH = "/tmp/book/cover.jpg"   # 与 make_epub.py 同目录（其自动检测 cover.jpg）
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

W, H = 900, 1300
img = Image.new("RGB", (W, H), "#8C1F28")  # 深红
draw = ImageDraw.Draw(img)

font_title = ImageFont.truetype(FONT_PATH, 72)
font_sub = ImageFont.truetype(FONT_PATH, 40)
font_en = ImageFont.truetype(FONT_PATH, 32)

# 书名（可多行）
lines = ["书名主标题", "副标题"]
y = 340
for line in lines:
    bbox = draw.textbbox((0, 0), line, font=font_title)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2, y), line, font=font_title, fill="#F5E9D0")
    y += 110

# 分隔线
draw.line([(W*0.3, y+10), (W*0.7, y+10)], fill="#F5E9D0", width=2)
y += 60

# 作者/译者/原文信息
for line in ["〔英〕作者（Author）著", "译者 译", "Original Title（1994）"]:
    font = font_sub if "著" in line else font_en
    bbox = draw.textbbox((0, 0), line, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2, y), line, font=font, fill="#E8D5B0")
    y += 80

img.save(SAVE_PATH, "JPEG", quality=92)
print("cover saved:", SAVE_PATH)
