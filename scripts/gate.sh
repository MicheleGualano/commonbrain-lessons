#!/usr/bin/env bash
# gate.sh — run the full local security/quality gate over lesson files.
# Default target: lessons/*.json. Used by CI jobs and by `cbrain publish`
# client-side. Exit 0 ONLY if every check passes (maximum posture).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

files=( "$@" )
if [ ${#files[@]} -eq 0 ]; then
  shopt -s nullglob
  files=( "$ROOT"/lessons/*.json )
fi
if [ ${#files[@]} -eq 0 ]; then
  echo "gate: no lesson files to check"; exit 0
fi

rc=0
echo "== schema-validate =="
python3 "$HERE/validate_lessons.py" "${files[@]}" || rc=1
echo "== secret-scan =="
for f in "${files[@]}"; do bash "$HERE/scrub_body.sh" --check "$f" || rc=1; done
[ $rc -eq 0 ] && echo "secret-scan: clean (${#files[@]} file(s))."
echo "== injection-sanitize =="
python3 "$HERE/injection_sanitize.py" "${files[@]}" || rc=1
echo "== generality-lint =="
python3 "$HERE/generality_lint.py" "${files[@]}" || rc=1
echo "== dedup =="
python3 "$HERE/dedup.py" "${files[@]}" || rc=1

if [ $rc -ne 0 ]; then echo "GATE: BLOCKED"; else echo "GATE: PASS"; fi
exit $rc
