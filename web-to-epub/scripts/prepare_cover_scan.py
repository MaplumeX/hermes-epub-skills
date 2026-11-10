#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prepare_cover_scan.py — 把公有领域扫描页（初版扉页/封面）做成电子书封面。

用法：
    python prepare_cover_scan.py SRC.jpg DST.jpg \
        [--width 1400] [--erase 0.40,0.72,0.57,0.84 ...]

  --erase 抹除区块，坐标是**相对成品宽高的比例** (fx0,fy0,fx1,fy1)，可重复多次。
          典型用途：抹掉位于空白带的馆藏圆章（它不带正文，抹掉不损失内容）。

处理链：检测书页区域裁掉扫描背景 → 按墨迹行列收紧取景 → 块状最大值估背景做除法归一
（去扫描阴影/透印，比高斯模糊好，不会在笔画周围出白晕）→ 硬阈值 + “仅保留墨迹邻域”
去孤立淡痕 → 暖白纸色映射 → 缩放到目标宽 → 按比例抹章（带羽化）→ 输出 JPEG。

⚠️ 两个踩过的坑，本脚本已内置：
  1. 抹章坐标必须在**缩放之后**换算成像素再抹。在缩放前的数组上直接用成品像素坐标，
     会静默抹在错误位置：跑完看着“没报错”，印章却还在，而别处被抹掉一块。
  2. 抹完必须用像素统计自检（本脚本会打印），不要问 vision_analyze “章还在吗”——
     它在同一张图上会前后矛盾。
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter

PAPER = np.array([248.0, 244.0, 233.0], np.float32)   # 暖白纸，不要纯白（屏幕上刺眼）
INK = np.array([46.0, 41.0, 35.0], np.float32)


def page_area(gray):
    """裁掉扫描背景：纸面比背景略暗。"""
    h, w = gray.shape
    paper = gray < 238
    rows = np.where(paper.mean(axis=1) > 0.55)[0]
    cols = np.where(paper.mean(axis=0) > 0.55)[0]
    if len(rows) > 100 and len(cols) > 100:
        y0, y1, x0, x1 = int(rows[0]), int(rows[-1]), int(cols[0]), int(cols[-1])
        dx, dy = int((x1 - x0) * 0.01), int((y1 - y0) * 0.01)
        return gray[y0 + dy:y1 - dy, x0 + dx:x1 - dx]
    return gray[int(h * .03):int(h * .97), int(w * .03):int(w * .97)]


def tighten(gray):
    """按有墨迹的行列再裁一次，四周留少量均匀边。"""
    ink = gray < 195
    rr = np.where(ink.mean(axis=1) > 0.002)[0]
    cc = np.where(ink.mean(axis=0) > 0.002)[0]
    if len(rr) < 50 or len(cc) < 50:
        return gray
    ty0, ty1, tx0, tx1 = int(rr[0]), int(rr[-1]), int(cc[0]), int(cc[-1])
    py = int((ty1 - ty0) * 0.03) + 12
    px = int((tx1 - tx0) * 0.07) + 12
    return gray[max(0, ty0 - py):min(gray.shape[0], ty1 + py),
                max(0, tx0 - px):min(gray.shape[1], tx1 + px)]


def normalize(gray, k=48):
    """块状最大值估背景 + 除法归一；再压暗字迹、丢掉孤立淡痕。"""
    h, w = gray.shape
    bh, bw = (h + k - 1) // k, (w + k - 1) // k
    pad = np.full((bh * k, bw * k), 255.0, np.float32)
    pad[:h, :w] = gray
    bmax = pad.reshape(bh, k, bw, k).max(axis=(1, 3))
    small = Image.fromarray(bmax.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=4))
    bg = np.asarray(small.resize((w, h), Image.BICUBIC)).astype(np.float32)
    bg[bg < 70] = 70
    n = np.clip(gray / bg * 250.0, 0, 255) / 255.0
    n = np.clip((n - 0.42) / 0.34, 0, 1) ** 0.8
    ink = n < 0.35
    near = ink.copy()
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            near |= np.roll(np.roll(ink, dy, axis=0), dx, axis=1)
    keep = ink | (near & (n < 0.60))
    n = np.where(keep, n, 1.0)
    print('  墨迹像素占比 %.2f%%' % (100 * keep.mean()))
    return INK[None, None, :] + (PAPER - INK)[None, None, :] * n[..., None]


def erase_bands(rgb, bands, feather=12):
    """按**比例**坐标抹除区块（缩放后换算像素），边缘羽化避免硬边白块，并自检。"""
    h, w = rgb.shape[:2]
    for fx0, fy0, fx1, fy1 in bands:
        x0, x1 = int(fx0 * w), int(fx1 * w)
        y0, y1 = int(fy0 * h), int(fy1 * h)
        before = (rgb[y0:y1, x0:x1].mean(axis=2) < 170).mean()
        band = rgb[y0:y1, x0:x1].mean(axis=2)
        ys, xs = np.where(band < 215)
        if len(ys) == 0:
            print(f'  抹章 {fx0:.2f},{fy0:.2f}-{fx1:.2f},{fy1:.2f}: 区带内无墨迹，跳过')
            continue
        bx0, bx1 = max(0, x0 + xs.min() - feather), min(w, x0 + xs.max() + feather)
        by0, by1 = max(0, y0 + ys.min() - feather), min(h, y0 + ys.max() + feather)
        hh, ww = by1 - by0, bx1 - bx0
        fy = np.minimum(np.arange(hh), np.arange(hh)[::-1]) / feather
        fx = np.minimum(np.arange(ww), np.arange(ww)[::-1]) / feather
        alpha = np.clip(np.minimum(fy[:, None], fx[None, :]), 0, 1)[..., None]
        rgb[by0:by1, bx0:bx1] = rgb[by0:by1, bx0:bx1] * (1 - alpha) + PAPER * alpha
        after = (rgb[y0:y1, x0:x1].mean(axis=2) < 170).mean()
        print(f'  抹章 ({bx0},{by0})-({bx1},{by1}): 墨迹占比 {before:.4f} -> {after:.4f}，'
              f'最小亮度 {(rgb[y0:y1, x0:x1].mean(axis=2)).min():.0f}')
        assert after < 0.005, '抹除后区内仍有墨迹——检查比例坐标是否落在印章上'
    return rgb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--width', type=int, default=1400)
    ap.add_argument('--erase', action='append', default=[],
                    help='fx0,fy0,fx1,fy1 相对成品宽高的比例，可重复')
    args = ap.parse_args()

    gray = np.asarray(Image.open(args.src).convert('L')).astype(np.float32)
    print(f'原图 {gray.shape[1]}x{gray.shape[0]}')
    gray = page_area(gray)
    gray = tighten(gray)
    print(f'取景后 {gray.shape[1]}x{gray.shape[0]}')

    rgb = normalize(gray)
    res = Image.fromarray(rgb.astype(np.uint8), 'RGB')
    res = res.resize((args.width, int(res.height * args.width / res.width)), Image.LANCZOS)

    arr = np.asarray(res).astype(np.float32)
    bands = [tuple(float(v) for v in s.split(',')) for s in args.erase]
    if bands:
        arr = erase_bands(arr, bands)
    res = Image.fromarray(arr.astype(np.uint8), 'RGB')
    res.save(args.dst, 'JPEG', quality=90, optimize=True)
    print(f'封面 -> {args.dst} {res.size}')
    print('下一步：用 vision 只看“这是哪一页/文字是否完整/留白是否均衡”，'
          '不要问它“印章还在不在”。')


if __name__ == '__main__':
    main()
