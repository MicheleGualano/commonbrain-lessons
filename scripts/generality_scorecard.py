#!/usr/bin/env python3
"""generality_scorecard.py — quality gate for a candidate public lesson (anti-slop).

Combines the hard BLOCKING checks (schema, secrets, injection, leaks — each must
pass) with soft 0-10 QUALITY dimensions (trigger quality, rule clarity, non-
specificity, tag quality). Verdict PASS only if every blocking check passes AND
the weighted soft score >= threshold. Posture is MAXIMUM (default threshold 70).

This is the mechanical first layer; the full agentic plausibility review
(printing-press-output-review style) layers on top in `cbrain publish`.

Usage: generality_scorecard.py [--threshold N] [--json] lessons/<id>.json [...]
Exit 0 all pass · 1 any fail · 2 usage.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

VERBS = ('use', 'prefer', 'avoid', 'gate', 'wrap', 'normalize', 'never', 'always',
         'put', 'keep', 'check', 'verify', 'read', 'quote', 'assemble', 'react',
         'trim', 'parse', 'do not', "don't", 'set', 'pin', 'add', 'strip', 'replace')
SAFE_NOUNS = {
    'GitHub', 'Git', 'Go', 'Python', 'Claude', 'Anthropic', 'Slack', 'Linear', 'AWS',
    'Supabase', 'Postgres', 'SQLite', 'Docker', 'macOS', 'Linux', 'Windows', 'JSON',
    'YAML', 'HTML', 'HTTP', 'HTTPS', 'API', 'CLI', 'MCP', 'SQL', 'OpenAPI', 'Cobra',
    'Bash', 'Zsh', 'Homebrew', 'OAuth', 'JWT', 'GNU', 'EOF', 'ANSI', 'PR', 'CI',
    'PIPESTATUS', 'MERGED', 'README', 'TODO',
}
PROPER = re.compile(r'\b(?:[A-Z][a-z]+){2,}\b|\b[A-Z]{3,}\b')


def _rc(cmd):
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def blocking(path):
    return {
        'schema_valid': _rc(['python3', os.path.join(HERE, 'validate_lessons.py'), path]),
        'no_secrets': _rc(['bash', os.path.join(HERE, 'scrub_body.sh'), '--check', path]),
        'no_injection': _rc(['python3', os.path.join(HERE, 'injection_sanitize.py'), path]),
        'no_leaks': _rc(['python3', os.path.join(HERE, 'generality_lint.py'), path]),
    }


def soft(lesson):
    triggers = lesson.get('triggers') or []
    rule = lesson.get('rule', '')
    tags = lesson.get('tags') or []

    # trigger quality: >=2 triggers, each reasonably literal (>=4 words or has symbols)
    def literal(t):
        return len(t.split()) >= 4 or bool(re.search(r'[:=/().%${}\[\]-]', t))
    tq = 0
    if triggers:
        good = sum(1 for t in triggers if literal(t)) / len(triggers)
        tq = round(10 * good * (1.0 if len(triggers) >= 2 else 0.6))

    # rule clarity: good length band + has an actionable verb
    rc = 0
    if 40 <= len(rule) <= 600:
        rc += 6
    has_verb = any(re.search(r'\b' + re.escape(v) + r'\b', rule.lower()) for v in VERBS)
    rc += 4 if has_verb else 0

    # non-specificity: penalize un-allowlisted proper nouns
    hits = [m for m in PROPER.findall(rule + ' ' + lesson.get('title', '')) if m not in SAFE_NOUNS]
    ns = max(0, 10 - len(hits))

    # tag quality: 2..6 kebab tags
    n = len(tags)
    tag = 10 if 2 <= n <= 6 else (6 if n in (1, 7, 8) else 3)

    dims = {'trigger_quality': tq, 'rule_clarity': rc, 'non_specificity': ns, 'tag_quality': tag}
    weights = {'trigger_quality': 0.35, 'rule_clarity': 0.25, 'non_specificity': 0.30, 'tag_quality': 0.10}
    overall = round(sum(dims[k] * 10 * weights[k] for k in dims))  # 0..100
    return dims, overall, hits


def score_lesson(path, threshold):
    try:
        lesson = json.load(open(path, encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        return {'file': path, 'error': str(e), 'verdict': 'FAIL'}
    blk = blocking(path)
    dims, overall, hits = soft(lesson)
    verdict = 'PASS' if all(blk.values()) and overall >= threshold else 'FAIL'
    return {'file': path, 'id': lesson.get('id'), 'blocking': blk, 'dimensions': dims,
            'overall': overall, 'threshold': threshold, 'proper_noun_review': hits, 'verdict': verdict}


def main(argv):
    args = argv[1:]
    threshold = 70
    as_json = False
    if '--threshold' in args:
        i = args.index('--threshold'); threshold = int(args[i + 1]); del args[i:i + 2]
    if '--json' in args:
        as_json = True; args.remove('--json')
    if not args:
        print('usage: generality_scorecard.py [--threshold N] [--json] lessons/<id>.json [...]', file=sys.stderr)
        return 2
    results = [score_lesson(p, threshold) for p in args]
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            if 'error' in r:
                print(f'✗ {r["file"]}: {r["error"]}'); continue
            flag = '✓' if r['verdict'] == 'PASS' else '✗'
            blk = ' '.join(f'{k}={"ok" if v else "FAIL"}' for k, v in r['blocking'].items())
            print(f'{flag} {r["id"]}  overall={r["overall"]}/{threshold}  [{r["verdict"]}]')
            print(f'    blocking: {blk}')
            print(f'    soft: {r["dimensions"]}')
            if r['proper_noun_review']:
                print(f'    review proper-nouns: {r["proper_noun_review"]}')
    return 0 if all(r.get('verdict') == 'PASS' for r in results) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
