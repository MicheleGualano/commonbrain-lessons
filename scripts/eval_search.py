#!/usr/bin/env python3
"""eval_search.py — retrieval-quality regression for the local searcher.

Runs labeled queries through search_local.search() and asserts the brain is both
SMART (the right lesson surfaces) and HONEST (off-topic queries abstain instead of
returning noise). Companion to tests/run.sh, which tests the security gate; this
tests the read side, so a scoring change can't silently wreck recall or abstention.

Fixture: tests/eval.jsonl, one JSON object per line:
  {"query": "...", "expect": "lesson-id"}                 recall: expect in top-K
  {"query": "...", "expect": "lesson-id", "xfail": true}  known lexical miss (documented gap, NOT gated)
  {"query": "...", "abstain": true}                       must return zero results

Exit 0 only if every gated case holds. xfail cases never fail the run; an xfail that
unexpectedly PASSES is reported as "now fixed — promote it" (a semantic-search upgrade
would flip these). Usage: eval_search.py [--k N] [path/to/eval.jsonl]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_local  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    k = 5
    if '--k' in argv:
        i = argv.index('--k'); k = int(argv[i + 1]); del argv[i:i + 2]
    path = argv[1] if len(argv) > 1 else os.path.join(ROOT, 'tests', 'eval.jsonl')
    cases = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
    lessons = search_local.load()

    recall_ok = recall_tot = 0
    abst_ok = abst_tot = 0
    xfail_known = xfail_fixed = 0
    failures = []

    for c in cases:
        q = c['query']
        rows = search_local.search(q, lessons=lessons, limit=k)
        ids = [l['id'] for _, l, _ in rows]
        top = f"{rows[0][0]:.2f} {ids[0]}" if rows else "abstain"

        if c.get('abstain'):
            abst_tot += 1
            if rows:
                failures.append(f"ABSTAIN FAIL  q={q!r} -> returned {len(rows)} (top {top})")
            else:
                abst_ok += 1
            continue

        exp = c['expect']
        hit = exp in ids
        if c.get('xfail'):
            xfail_known += 1
            if hit:
                xfail_fixed += 1
                print(f"  ~ xfail NOW PASSES (promote): q={q!r} -> {exp} at rank {ids.index(exp) + 1}")
            continue

        recall_tot += 1
        if hit:
            recall_ok += 1
        else:
            failures.append(f"RECALL FAIL   q={q!r} -> expected {exp}, got {ids or 'abstain'}")

    print(f"\nrecall@{k}:   {recall_ok}/{recall_tot}")
    print(f"abstention:  {abst_ok}/{abst_tot}")
    extra = f" — {xfail_fixed} now fixed, promote them" if xfail_fixed else ""
    print(f"known gaps:  {xfail_known} xfail{extra}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  " + f)
        print("\nEVAL: FAIL")
        return 1
    print("\nEVAL: PASS")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
