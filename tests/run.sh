#!/usr/bin/env bash
# run.sh — regression tests proving the gate BLOCKS each attack class and PASSES
# clean lessons. Exit 0 only if every assertion holds.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(dirname "$HERE")/scripts"
FX="$HERE/fixtures"
pass=0; fail=0

assert() { # <expected-rc> <label> <cmd...>
  local exp="$1" label="$2"; shift 2
  "$@" >/dev/null 2>&1; local rc=$?
  if [ "$rc" -eq "$exp" ]; then echo "  ok   $label (rc=$rc)"; pass=$((pass+1));
  else echo "  FAIL $label (rc=$rc, expected $exp)"; fail=$((fail+1)); fi
}

echo "[schema-validate]"
assert 0 "valid lesson"        python3 "$SCRIPTS/validate_lessons.py" "$FX/gate-clean-sample.json"
assert 1 "invalid lesson"      python3 "$SCRIPTS/validate_lessons.py" "$FX/bad-schema-sample.json"
echo "[secret-scan]"
assert 0 "clean -> ok"         bash    "$SCRIPTS/scrub_body.sh" --check "$FX/gate-clean-sample.json"
assert 1 "ghp_ token -> fail"  bash    "$SCRIPTS/scrub_body.sh" --check "$FX/secret-token-sample.json"
echo "[injection-sanitize]"
assert 0 "clean -> ok"         python3 "$SCRIPTS/injection_sanitize.py" "$FX/gate-clean-sample.json"
assert 1 "override payload"    python3 "$SCRIPTS/injection_sanitize.py" "$FX/injection-override-sample.json"
assert 1 "unicode/bidi"        python3 "$SCRIPTS/injection_sanitize.py" "$FX/unicode-bidi-sample.json"
echo "[generality-lint]"
assert 0 "clean -> ok"         python3 "$SCRIPTS/generality_lint.py" "$FX/gate-clean-sample.json"
assert 1 "home path leak"      python3 "$SCRIPTS/generality_lint.py" "$FX/home-path-sample.json"
echo "[dedup]"
assert 0 "single -> ok"        python3 "$SCRIPTS/dedup.py" "$FX/gate-clean-sample.json"
assert 1 "near-duplicate pair" python3 "$SCRIPTS/dedup.py" "$FX/dup-one.json" "$FX/dup-two.json"
echo "[gate orchestrator]"
assert 0 "clean -> PASS"       bash    "$SCRIPTS/gate.sh" "$FX/gate-clean-sample.json"
assert 1 "secret -> BLOCKED"   bash    "$SCRIPTS/gate.sh" "$FX/secret-token-sample.json"
assert 1 "injection -> BLOCKED" bash   "$SCRIPTS/gate.sh" "$FX/injection-override-sample.json"
echo "[retrieval-eval]"
assert 0 "search recall + abstention" python3 "$SCRIPTS/eval_search.py"

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
