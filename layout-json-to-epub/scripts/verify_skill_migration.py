#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能重构后的无损校验：旧 SKILL.md 的每条行首加粗结论，必须在新结构里找到。

用法：
  python3 verify_skill_migration.py <旧 SKILL.md> <技能目录>
  python3 verify_skill_migration.py SKILL.old.md /root/.hermes/skills/productivity/layout-json-to-epub

技能目录里会扫描 SKILL.md + references/mechanisms/*.md + references/*.md。
退出码 0 = 全部命中；1 = 有遗漏（逐条打印，必须补完再交付）。

为什么需要它：把 SKILL.md 拆成 mechanisms/ 时，条目靠脚本分桶 + 人工复核，
漏条不会报错、也不会被下一次 skill_view 发现——只能靠机械比对兜住。
上一次重构基线：旧版 298 条行首加粗结论、402 条条目 → 新版 355 条条目、0 丢失。
"""
import glob
import os
import re
import sys


def norm(s):
    s = re.sub(r'\*\*', '', s)
    s = re.sub(r'`', '', s)
    return re.sub(r'\s+', '', s)


def main(old_path, skill_dir):
    old = open(old_path, encoding='utf-8').read()
    new = open(os.path.join(skill_dir, 'SKILL.md'), encoding='utf-8').read()
    for f in glob.glob(os.path.join(skill_dir, 'references', 'mechanisms', '*.md')):
        new += '\n' + open(f, encoding='utf-8').read()
    for f in glob.glob(os.path.join(skill_dir, 'references', '*.md')):
        new += '\n' + open(f, encoding='utf-8').read()

    newN = norm(new)
    olds = re.findall(r'^[-*]\s*\*\*(.{4,90}?)\*\*', old, re.M)
    miss = [t for t in olds if norm(t)[:24] and norm(t)[:24] not in newN]

    print('旧版行首加粗结论：%d 条' % len(olds))
    print('未找到：%d 条' % len(miss))
    for t in miss:
        print('  ✗ %s' % t[:80])

    cnt = 0
    for f in glob.glob(os.path.join(skill_dir, 'references', 'mechanisms', '*.md')):
        cnt += len(re.findall(r'^[-*] ', open(f, encoding='utf-8').read(), re.M))
    print('机制篇条目合计：%d' % cnt)
    print('SKILL.md 字符：%d（旧 %d）'
          % (len(open(os.path.join(skill_dir, 'SKILL.md'), encoding='utf-8').read()), len(old)))
    return 1 if miss else 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
