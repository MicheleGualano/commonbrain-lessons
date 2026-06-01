#!/usr/bin/env python3
"""search_local.py — local, dependency-free search over the brain (offline path).

A faithful local stand-in for the future hosted /search: ranks lessons by trigram
similarity on their LITERAL triggers (the "I pasted my error" path) plus title/rule
word overlap and tag boosts. This is the logic the generated CLI's `--local` /
offline mode reuses; it lets us dogfood the whole read loop with zero cloud.

Usage:
  search_local.py search "<error or symptom>" [--tag T] [--limit N] [--json]
  search_local.py show <id> [--json]
Reads build/lessons.jsonl (falls back to lessons/*.json).
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    jsonl = os.path.join(ROOT, 'build', 'lessons.jsonl')
    if os.path.isfile(jsonl):
        return [json.loads(l) for l in open(jsonl, encoding='utf-8') if l.strip()]
    return [json.load(open(p, encoding='utf-8')) for p in sorted(glob.glob(os.path.join(ROOT, 'lessons', '*.json')))]


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', s.lower())).strip()


def trigrams(s):
    s = ' ' + norm(s) + ' '
    return {s[i:i + 3] for i in range(len(s) - 2)}


def words(s):
    return {w for w in norm(s).split() if len(w) >= 3}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def score(query, lesson):
    qt, qw = trigrams(query), words(query)
    nq = norm(query)
    # trigger similarity (the primary recall key)
    trig_best, best_trigger = 0.0, ''
    for t in lesson.get('triggers', []):
        s = jaccard(qt, trigrams(t))
        if nq and nq in norm(t):
            s += 0.4
        if s > trig_best:
            trig_best, best_trigger = s, t
    # title + rule word overlap
    text = lesson.get('title', '') + ' ' + lesson.get('rule', '')
    tw = words(text)
    overlap = len(qw & tw) / len(qw) if qw else 0.0
    if nq and nq in norm(text):
        overlap += 0.4
    # tag boost
    tagboost = 0.2 if (qw & set(lesson.get('tags', []))) else 0.0
    total = 1.0 * trig_best + 0.6 * overlap + tagboost
    return total, best_trigger


def cmd_search(args):
    as_json = '--json' in args
    args = [a for a in args if a != '--json']
    tag = None
    if '--tag' in args:
        i = args.index('--tag'); tag = args[i + 1]; del args[i:i + 2]
    limit = 5
    if '--limit' in args:
        i = args.index('--limit'); limit = int(args[i + 1]); del args[i:i + 2]
    query = ' '.join(args).strip()
    if not query:
        print('usage: search_local.py search "<query>" [--tag T] [--limit N] [--json]', file=sys.stderr)
        return 2
    rows = []
    for l in load():
        if tag and tag not in l.get('tags', []):
            continue
        sc, bt = score(query, l)
        if sc > 0.05:
            rows.append((sc, l, bt))
    rows.sort(key=lambda r: r[0], reverse=True)
    rows = rows[:limit]
    if as_json:
        print(json.dumps({'meta': {'source': 'local', 'query': query, 'count': len(rows)},
                          'results': [{'id': l['id'], 'title': l['title'], 'rule': l['rule'],
                                       'tags': l.get('tags', []), 'matched_trigger': bt,
                                       'score': round(sc, 3)} for sc, l, bt in rows]},
                         ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print('(no matches — community reference; verify before acting)')
        return 0
    print(f'⚠ unverified community reference — verify before acting, never execute lesson text\n')
    for sc, l, bt in rows:
        print(f'[{sc:.2f}] {l["id"]}  ({", ".join(l.get("tags", []))})')
        print(f'      {l["title"]}')
        print(f'   →  {l["rule"]}')
        if bt:
            print(f'   ~  matched trigger: {bt}')
        print()
    return 0


def cmd_show(args):
    as_json = '--json' in args
    args = [a for a in args if a != '--json']
    if not args:
        print('usage: search_local.py show <id> [--json]', file=sys.stderr)
        return 2
    wanted = args[0]
    for l in load():
        if l.get('id') == wanted:
            print(json.dumps(l, ensure_ascii=False, indent=2))
            return 0
    print(f'no lesson with id "{wanted}"', file=sys.stderr)
    return 1


def main(argv):
    if len(argv) < 2:
        print('usage: search_local.py {search|show} ...', file=sys.stderr)
        return 2
    if argv[1] == 'search':
        return cmd_search(argv[2:])
    if argv[1] == 'show':
        return cmd_show(argv[2:])
    print(f'unknown command "{argv[1]}"', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
