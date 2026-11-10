# 用初版扫描件做封面（真实书影，而非 PIL 画一张）

触发：用户说“换成真实封面”“去网上找书籍封面”，或明确拒绝程序生成的封面。
配套脚本：`scripts/prepare_cover_scan.py`（扫描页 → 封面，含抹章与像素自检）。

## 1. 找候选扫描件（archive.org）

```bash
curl -s "https://archive.org/advancedsearch.php?q=title%3A%28<slug>%29\
&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=date&fl%5B%5D=collection&fl%5B%5D=creator\
&rows=20&output=json"
```

- `collection` 里出现 `printdisabled` 的直接跳过（处处 403）；`europeanlibraries` / `german-online-libraries` 一般开放。
- 同一本书常有**两个以上馆藏扫描**，命名形如 `bub_gb_<id>`（Google 扫描）和 `<slug>00<author>goog`。
  两个都取前 10 页比对——洁净度差别很大（一个可能有手写索书号，另一个只有一枚馆藏章）。
- 有的条目 `metadata.date` 是 1847 但 `creator` 是 OCR 垃圾（如 `Rarl marr`），不影响使用。

## 2. 用“墨迹占比”先筛页型，再让 vision 判

逐个下载 `page/n{0..16}_w1400.jpg`，算 `(gray<160).mean()`：

| 比值 | 大概率是 |
|---|---|
| ≈0.000–0.003 | 空白页 / 衬页 |
| 0.010–0.030 | 半书名页、书名页（字少、留白大） |
| 0.030–0.060 | 正文页 |
| ≈1.0 | 纯黑扫描失败页 |

注意 **n0 常是 Google 的“数字化说明页”**（白底英文 + 彩色 logo，ink≈0.05，看起来像正文页），别当封面。
筛出 2–3 个候选后再调 `vision_analyze` 判“半书名页 / 书名页 / 正文首页 / 有没有印章手写”。

## 3. 选哪一页

- **半书名页**（只有书名+副题，无作者/出版者/年代）：最干净，通常无章无手写；信息量最少。
- **书名页**（含 `Par <作者>`、`PARIS / BRUXELLES <出版者>`、年份）：信息最全，最像“书的封面”，
  代价是常带馆藏圆章 / 索书号。**优先这一页**，章落在空白带就抹掉（见 §4），落在文字上就换另一个馆藏。

已知先例：

| 书 | 条目 | 页 | 备注 |
|---|---|---|---|
| 《神圣家族》1845 | `bub_gb_xL4AAAAAcAAJ_2` | n3 | 初版扉页 |
| 《哲学的贫困》1847 | `bub_gb_eCRQAAAAcAAJ` | n8 | 巴黎 A. Frank / 布鲁塞尔 C. G. Vogler 书名页，鲁汶大学旧藏，章已抹 |

## 4. 抹掉空白带里的馆藏章

先定位（逐行找暗像素所在列区间，找出“有墨迹但本来该是空白”的那一段）：

```python
for y in range(y_lo, y_hi, 10):
    xs = np.where(a[y] < 170)[0]
    print(y, len(xs), (xs.min(), xs.max()) if len(xs) else '')
```

花饰横线、两栏出版信息会各自成形；夹在中间那段孤立墨迹就是圆章。给出**比例坐标**给脚本：

```bash
./epubenv/bin/python scripts/prepare_cover_scan.py scan/p8.jpg cover_scan.jpg \
    --erase 0.41,0.73,0.57,0.84
```

脚本会打印 `墨迹占比 before -> after` 与区带最小亮度，并在 `after >= 0.005` 时断言失败。

**坑（真踩过）**：抹章必须发生在**缩放之后**。第一版脚本在缩放前的数组上直接用了成品图像素坐标，
跑完不报错、印章还在原处，而画面别处被抹掉一块。所以脚本的接口是比例坐标，内部乘成品宽高。

**坑**：`vision_analyze` 判不了“章有没有被抹掉”。同一张图它先说“印章完全保留”，放大后说
“几乎看不见”，整页再看又说“明显”。它适合判页型、文字是否完整、留白是否均衡、有无误删小字；
凡涉及“某个局部痕迹是否还在”，一律用像素统计（`(reg<170).mean()`、`reg.min()`）。

## 5. 交付

- `book.set_cover('cover.jpg', bytes)`，并在书名页写一行出处，例如
  `封面：1847 年初版扉页（巴黎 A. Frank / 布鲁塞尔 C. G. Vogler 刊行，archive.org 公有领域扫描件）`。
- 交付时说明做过哪些图像清理（裁扫描背景、去透印、抹馆藏章），并主动提出可以出“保留印章”版本——
  用户把“可审计”看得很重，抹章属于对原件的改动，必须自己先说出来。
- 换封面后要重跑整套校验（文本双向比对 + 脚注 + epubcheck），并在报告里给真实数字。
