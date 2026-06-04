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


def contain_bonus(nq, target, weight=0.4):
    """Substring-containment reward scaled by how much of the target the query
    covers, so a short/common query (e.g. the bare word 'error') inside a long
    trigger earns almost nothing while a near-full match earns the full weight.
    Without this, a flat +0.4 stacked across triggers + title/rule let generic
    one-word queries outscore specific multi-word ones."""
    nt = norm(target)
    if not nq or nq not in nt:
        return 0.0
    return weight * (len(nq) / len(nt))


def score(query, lesson):
    qt, qw = trigrams(query), words(query)
    nq = norm(query)
    # trigger similarity (the primary recall key)
    trig_best, best_trigger = 0.0, ''
    for t in lesson.get('triggers', []):
        s = jaccard(qt, trigrams(t))
        s += contain_bonus(nq, t)
        if s > trig_best:
            trig_best, best_trigger = s, t
    # title + rule word overlap
    text = lesson.get('title', '') + ' ' + lesson.get('rule', '')
    tw = words(text)
    overlap = len(qw & tw) / len(qw) if qw else 0.0
    overlap += contain_bonus(nq, text)
    # tag boost
    tagboost = 0.2 if (qw & set(lesson.get('tags', []))) else 0.0
    total = 1.0 * trig_best + 0.6 * overlap + tagboost
    return total, best_trigger


# Abstention: retrieval must be able to say "nothing relevant" rather than always
# returning rows. ABS_FLOOR is the absolute confidence a top hit needs to be worth
# showing (calibrated so off-topic trigram noise — which tops out ~0.2 — abstains,
# while real trigger matches — which exceed ~1.0 — survive); REL_FLOOR drops tail
# rows sitting far below the best hit. Both are exercised by scripts/eval_search.py.
ABS_FLOOR = 0.40
REL_FLOOR = 0.50


def _select(scored, limit):
    """Apply abstention + tail-trim to sorted (score, lesson, trigger) rows."""
    if not scored:
        return []
    best = scored[0][0]
    if best < ABS_FLOOR:
        return []
    keep = [r for r in scored if r[0] >= REL_FLOOR * best]
    return keep[:limit]


def search(query, lessons=None, tag=None, limit=5):
    """Rank lessons for a query and apply abstention. Shared by the CLI and the
    eval harness so both exercise identical retrieval behavior."""
    if lessons is None:
        lessons = load()
    scored = []
    for l in lessons:
        if tag and tag not in l.get('tags', []):
            continue
        sc, bt = score(query, l)
        scored.append((sc, l, bt))
    scored.sort(key=lambda r: r[0], reverse=True)
    return _select(scored, limit)


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
    rows = search(query, tag=tag, limit=limit)
    if as_json:
        print(json.dumps({'meta': {'source': 'local', 'query': query, 'count': len(rows)},
                          'results': [{'id': l['id'], 'title': l['title'], 'rule': l['rule'],
                                       'tags': l.get('tags', []), 'matched_trigger': bt,
                                       'score': round(sc, 3)} for sc, l, bt in rows]},
                         ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print('(no relevant lesson — nothing in the brain is a confident match; verify before acting)')
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
