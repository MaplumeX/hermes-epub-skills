#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 Agent Skills 开放标准（https://agentskills.io/specification）体检一个或多个技能目录。

用法：
    python3 check_skill_format.py <skill-dir> [<skill-dir> ...]

检查项（required = 不合规即 exit 1；hint = 仅提示）：
  required  SKILL.md 存在且含 YAML frontmatter
  required  name / description 齐备；name 只含小写字母、数字、连字符，≤64 字符，且 == 目录名
  required  description ≤1024 字符（并提示是否写了「何时用」）
  required  frontmatter 无标准外字段（允许 name/description/license/allowed-tools/compatibility/metadata）
  hint      正文 token 估算是否超过规范建议的 5000（中文按 1.5 字符/token）
  hint      scripts/ 下 .py 能否通过语法编译
"""
import os
import re
import sys

ALLOWED = {'name', 'description', 'license', 'allowed-tools', 'compatibility', 'metadata'}
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
WHEN_HINTS = ('use when', 'when ', '当用户', '当任务', '何时', '要求', 'if the user', 'whenever')


def load_frontmatter(text):
    if not text.startswith('---'):
        return None, text
    end = text.find('\n---', 3)
    if end < 0:
        return None, text
    raw = text[3:end].strip('\n')
    body = text[end + 4:]
    try:
        import yaml
        data = yaml.safe_load(raw)
    except Exception:
        # 没有 pyyaml 时退回最小解析（仅 key: value 单行）
        data = {}
        for line in raw.split('\n'):
            m = re.match(r'^([A-Za-z0-9_-]+):\s*(.+)$', line)
            if m:
                data[m.group(1)] = m.group(2).strip().strip('"\'')
        if not data:
            return None, body
    return data, body


def check(skill_dir):
    problems, hints = [], []
    p = os.path.join(skill_dir, 'SKILL.md')
    if not os.path.isfile(p):
        return ['缺少 SKILL.md'], []
    text = open(p, encoding='utf-8').read()
    fm, body = load_frontmatter(text)
    if fm is None:
        return ['SKILL.md 没有可解析的 YAML frontmatter'], []
    name = str(fm.get('name') or '')
    desc = str(fm.get('description') or '')
    if not name:
        problems.append('frontmatter 缺 name')
    else:
        if not NAME_RE.match(name):
            problems.append('name 只允许小写字母/数字/连字符且不以连字符开头结尾：%r' % name)
        if len(name) > 64:
            problems.append('name 超过 64 字符')
        if name != os.path.basename(os.path.abspath(skill_dir)):
            problems.append('name 与目录名不一致：%r vs %r' % (name, os.path.basename(os.path.abspath(skill_dir))))
    if not desc:
        problems.append('frontmatter 缺 description')
    elif len(desc) > 1024:
        problems.append('description 超过 1024 字符（%d）' % len(desc))
    elif not any(h in desc.lower() for h in WHEN_HINTS):
        hints.append('description 似乎没写「什么时候用」（规范建议写清 when to use）')
    extra = sorted(set(fm) - ALLOWED)
    if extra:
        problems.append('标准外字段（其他客户端会忽略或报错）：%s' % ', '.join(extra))
    est = round(len(body) / 1.5)          # 中文约 1.5 字符/token
    if est > 5000:
        hints.append('正文约 %d tokens，超过规范建议的 5000（拆进 references/ 可缓解）' % est)
    sdir = os.path.join(skill_dir, 'scripts')
    if os.path.isdir(sdir):
        import ast
        for f in sorted(os.listdir(sdir)):
            if f.endswith('.py'):
                try:
                    ast.parse(open(os.path.join(sdir, f), encoding='utf-8').read())
                except SyntaxError as e:
                    problems.append('scripts/%s 语法错误：%s' % (f, e))
    return problems, hints


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    bad = 0
    for d in argv[1:]:
        problems, hints = check(d)
        print('== %s' % d)
        for m in problems:
            print('   ✗ %s' % m)
        for m in hints:
            print('   · %s' % m)
        if not problems:
            print('   ✓ 符合 Agent Skills 标准%s' % ('（有提示项）' if hints else ''))
        bad += bool(problems)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv)
