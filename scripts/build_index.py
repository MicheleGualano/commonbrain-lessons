#!/usr/bin/env python3
"""build_index.py — build the derived search artifact from the canonical lessons.

Reads lessons/*.json and writes build/lessons.jsonl: ONE compact JSON object per
line, fields ordered id,date,title,rule,tags,triggers,provenance,license,verified.
One record per line means `grep '<error>' build/lessons.jsonl` returns the WHOLE
record (id+rule+everything) in one shot — the retrieval contract the pretty-printed
private index could not satisfy. This is also what CI publishes and what the CLI's
`sync` / offline `--local` mode consumes.

Usage: build_index.py            (repo-relative: lessons/ -> build/lessons.jsonl)
       build_index.py --out PATH
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ['id', 'date', 'title', 'rule', 'tags', 'triggers', 'provenance', 'license', 'verified']


def main(argv):
    out = os.path.join(ROOT, 'build', 'lessons.jsonl')
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    os.makedirs(os.path.dirname(out), exist_ok=True)

    files = sorted(glob.glob(os.path.join(ROOT, 'lessons', '*.json')))
    n = 0
    with open(out, 'w', encoding='utf-8') as f:
        for p in files:
            lesson = json.load(open(p, encoding='utf-8'))
            rec = {k: lesson[k] for k in ORDER if k in lesson}
            f.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
            n += 1
    print(f'build_index: wrote {n} record(s) -> {os.path.relpath(out, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
