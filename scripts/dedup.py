#!/usr/bin/env python3
"""dedup.py — block duplicate ids and near-duplicate lessons (anti-slop, Pillar 0.B).

Across the given lesson set:
  - duplicate `id` (or filename/id mismatch handled by validate) -> FAIL
  - near-duplicate content: trigram (char 3-gram) Jaccard similarity over the
    normalized rule + triggers above --threshold (default 0.72) -> FAIL

So the same gotcha can't be published twice under different ids.

Usage: dedup.py [--threshold 0.72] lessons/*.json
Exit 0 clean · 1 duplicate(s) · 2 usage.
"""
import json
import re
import sys


def normalize(lesson):
    parts = [lesson.get('rule', '')] + list(lesson.get('triggers') or [])
    s = ' '.join(parts).lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', s)).strip()


def trigrams(s):
    s = re.sub(r'\s+', ' ', s)
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main(argv):
    args = argv[1:]
    threshold = 0.72
    if args and args[0] == '--threshold':
        threshold = float(args[1])
        args = args[2:]
    if not args:
        print('usage: dedup.py [--threshold N] lessons/*.json', file=sys.stderr)
        return 2

    lessons = []
    for p in args:
        try:
            lessons.append((p, json.load(open(p, encoding='utf-8'))))
        except (OSError, json.JSONDecodeError) as e:
            print(f'✗ {p}: cannot read/parse: {e}', file=sys.stderr)
            return 1

    fails = 0
    # duplicate ids
    seen = {}
    for p, l in lessons:
        i = l.get('id')
        if i in seen:
            print(f'✗ duplicate id "{i}": {seen[i]} and {p}', file=sys.stderr)
            fails += 1
        else:
            seen[i] = p

    # near-duplicate content
    grams = [(p, l.get('id'), trigrams(normalize(l))) for p, l in lessons]
    for i in range(len(grams)):
        for j in range(i + 1, len(grams)):
            sim = jaccard(grams[i][2], grams[j][2])
            if sim >= threshold:
                print(f'✗ near-duplicate ({sim:.2f} >= {threshold}): "{grams[i][1]}" vs "{grams[j][1]}"', file=sys.stderr)
                fails += 1

    if fails:
        print(f'dedup: BLOCKED — {fails} collision(s).', file=sys.stderr)
        return 1
    print(f'dedup: clean ({len(lessons)} lesson(s)).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
