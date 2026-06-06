#!/usr/bin/env python3
"""verified_field_lint.py — fail if any given lesson asserts `verified: true`.

`verified` is a MAINTAINER-EARNED trust signal (the rule was reproduced/confirmed),
not something a contribution can self-assert — otherwise an untrusted PR could claim
authority it hasn't earned. A contribution PR (which may only touch lessons/ + html/)
must therefore not set `verified: true`; the maintainer flips it via a direct push or
admin merge after checking the rule. The gate runs this only over the files CHANGED in
a PR, so existing maintainer-set verified lessons are untouched.

Usage: verified_field_lint.py <lesson.json> [<lesson.json> ...]
Exit 0 only if no file asserts verified:true.
"""
import json
import sys


def main(argv):
    bad = []
    for p in argv[1:]:
        try:
            d = json.load(open(p, encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            print(f'verified-lint: cannot read {p}: {e}', file=sys.stderr)
            return 1
        if isinstance(d, dict) and d.get('verified') is True:
            bad.append(p)
    if bad:
        print('::error::a contribution may not set "verified": true — it is maintainer-only '
              '(set by a maintainer after reproducing the rule). Remove it from:', file=sys.stderr)
        for p in bad:
            print(f'  - {p}', file=sys.stderr)
        return 1
    print(f'verified-lint: clean ({len(argv) - 1} file(s)).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
