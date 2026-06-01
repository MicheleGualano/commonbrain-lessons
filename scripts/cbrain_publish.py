#!/usr/bin/env python3
"""cbrain_publish.py — PROTOTYPE of the `cbrain publish` write path (local only).

Pipeline (stops at the outward boundary):
  1. Load a lesson from the private brain (--from-brain <id>) or a file (--file).
  2. Map it to the public shape (provenance=promoted, license=CC-BY-4.0,
     contributor=null); auto-lowercase id + tags and report the normalization.
  3. Stage it at build/publish/<id>.json.
  4. Run the full gate + generality scorecard on the staged candidate.
  5. If it PASSES, report "ready" and the EXACT PR that WOULD be opened — but DO
     NOT touch git or gh. Opening the PR is an outward action, parked behind an
     explicit human "go".
  If it FAILS, print the gaps so the agent can generalize/scrub-and-fix the
  candidate (agent-in-the-loop rewrite) and re-run. Never auto-rewrites.

Usage:
  cbrain_publish.py --from-brain <id> [--brain-dir ~/claude-second-brain]
  cbrain_publish.py --file <lesson.json>
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_from_brain(brain_dir, lesson_id):
    idx = os.path.join(os.path.expanduser(brain_dir), 'brain-index.json')
    data = json.load(open(idx, encoding='utf-8'))
    for l in data.get('lessons', []):
        if l.get('id') == lesson_id:
            return l
    raise SystemExit(f'cbrain publish: no lesson "{lesson_id}" in {idx}')


def to_public(priv):
    notes = []
    pid = priv.get('id', '')
    if pid != pid.lower():
        notes.append(f'lowercased id {pid} -> {pid.lower()}')
    tags = []
    for t in (priv.get('tags') or []):
        if t != t.lower():
            notes.append(f'lowercased tag {t} -> {t.lower()}')
        tags.append(t.lower())
    pub = {
        'id': pid.lower(),
        'date': priv.get('date', ''),
        'title': priv.get('title', ''),
        'rule': priv.get('rule', ''),
        'tags': tags,
        'triggers': priv.get('triggers') or [],
        'provenance': 'promoted',
        'contributor': None,
        'license': 'CC-BY-4.0',
    }
    return pub, notes


def main(argv):
    args = argv[1:]
    brain_dir = '~/claude-second-brain'
    if '--brain-dir' in args:
        i = args.index('--brain-dir'); brain_dir = args[i + 1]; del args[i:i + 2]
    if '--from-brain' in args:
        i = args.index('--from-brain'); pub, notes = to_public(load_from_brain(brain_dir, args[i + 1]))
    elif '--file' in args:
        i = args.index('--file'); pub, notes = to_public(json.load(open(args[i + 1], encoding='utf-8')))
    else:
        print('usage: cbrain_publish.py --from-brain <id> | --file <lesson.json>', file=sys.stderr)
        return 2

    stage_dir = os.path.join(ROOT, 'build', 'publish')
    os.makedirs(stage_dir, exist_ok=True)
    staged = os.path.join(stage_dir, f'{pub["id"]}.json')
    with open(staged, 'w', encoding='utf-8') as f:
        json.dump(pub, f, ensure_ascii=False, indent=2)

    print(f'staged candidate -> {os.path.relpath(staged, ROOT)}')
    for n in notes:
        print(f'  normalized: {n}')
    print()
    rc = subprocess.run(['python3', os.path.join(HERE, 'generality_scorecard.py'), staged]).returncode
    print()
    if rc == 0:
        print('READY. The next step WOULD open a PR to commonbrain-lessons:')
        print(f'    branch publish/{pub["id"]}  ·  add lessons/{pub["id"]}.json  ·  gh pr create')
        print('    → PARKED: opening the PR is an outward action. Awaiting explicit "go".')
        return 0
    print('BLOCKED by the gate. Generalize/scrub the staged candidate (remove project specifics,')
    print('tighten the rule, add literal triggers), then re-run. The publish path never auto-rewrites.')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
