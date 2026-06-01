#!/usr/bin/env bash
# scrub_body.sh — secret HARD-FAIL + PII auto-redact.
#
# The scrub_body() function below is VENDORED VERBATIM from the printing-press
# machinery: ~/.claude/skills/printing-press-retro/references/secret-scrubbing.md
# (Layer 0a vendor-prefix hard-fail + Layer 0b PII auto-redact). Keep it in sync
# with that source; do not edit the logic here without updating the origin.
#
# CLI wrappers (added for commonbrain):
#   scrub_body.sh <in> <out>     scrub <in> into <out>; exit 1 if a secret hard-fails
#   scrub_body.sh --check <in>   scan only (scrub into a temp, discard); exit 1 on hard-fail
#
# Used by the CI `secret-scan` job and by `cbrain publish` client-side. NOTE: we
# do NOT `set -e` — the function relies on grep returning 1 (no match) as normal
# control flow.

# ---- VENDORED (do not edit) -------------------------------------------------
scrub_body() {
  local in="$1" out="$2"
  if [ -z "$in" ] || [ -z "$out" ] || [ ! -f "$in" ]; then
    echo "scrub_body: usage: scrub_body <in-file> <out-file>" >&2
    return 2
  fi

  # Layer 0a: vendor-prefix HARD-FAIL patterns. Order: most-specific first.
  local VENDOR_PATTERNS=(
    'stripe-live-key|sk_live_[A-Za-z0-9]{20,}'
    'stripe-test-key|sk_test_[A-Za-z0-9]{20,}'
    'github-pat|ghp_[A-Za-z0-9]{36,}'
    'github-oauth|gho_[A-Za-z0-9]{36,}'
    'github-server|ghs_[A-Za-z0-9]{36,}'
    'slack-bot-token|xoxb-[A-Za-z0-9-]{20,}'
    'slack-user-token|xoxp-[A-Za-z0-9-]{20,}'
    'aws-access-key|\bAKIA[0-9A-Z]{16}\b'
    'openrouter-key|sk-or-v1-[A-Za-z0-9_-]{24,}'
    'anthropic-key|sk-ant-api03-[A-Za-z0-9_-]{40,}'
    'linear-key|\blin_api_[A-Za-z0-9_-]{32,}'
    'mailchimp-key|\b[a-f0-9]{32}-us[0-9]{1,2}\b'
    'jwt-token|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}'
    'bearer-with-value|Bearer [A-Za-z0-9._~+/=-]{30,}'
  )

  local hard_fail=0
  for entry in "${VENDOR_PATTERNS[@]}"; do
    IFS='|' read -r name regex <<< "$entry"
    if grep -qE "$regex" "$in" 2>/dev/null; then
      lines=$(grep -nE "$regex" "$in" 2>/dev/null | cut -d: -f1 | head -5 | tr '\n' ',' | sed 's/,$//')
      echo "scrub_body: HARD FAIL — $name pattern matched in $in (lines: $lines)" >&2
      hard_fail=1
    fi
  done
  if [ "$hard_fail" -eq 1 ]; then
    echo "scrub_body: refusing to write $out. Hand-redact the matches above with <REDACTED:<vendor>-<kind>:<first4>...<last4>:<len>ch> per references/secret-scrubbing.md Layer 0, then retry." >&2
    return 1
  fi

  # Layer 0b: PII auto-redact patterns (written copy only; input untouched).
  cp "$in" "$out" 2>/dev/null || { echo "scrub_body: failed to copy $in -> $out" >&2; return 2; }

  perl -i -pe 's/\bus\d{1,2}-[a-f0-9]{8,}-[a-f0-9]{8,}\@inbound\.mailchimp\.com\b/<REDACTED:mailchimp-inbox-id>/g' "$out" 2>/dev/null

  perl -i -pe 's/\b([A-Za-z0-9._%+-]+)@(?!example\.(?:com|net|org|invalid)\b|[^\s]*\.(?:test|localhost|example)\b)([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/<REDACTED:email>/g' "$out" 2>/dev/null

  perl -i -pe 's{(?<![0-9])(?:\+?1[-\s.]?)?\(?([2-9][0-9]{2})\)?[-\s.]?([0-9]{3})[-\s.]?[0-9]{4}(?![0-9])}{my $w=$&; my $a=$1; my $e=$2; ($a eq "555" && $e =~ /^01/) ? $w : "<REDACTED:phone-us>"}ge' "$out" 2>/dev/null

  perl -i -pe 's/\b\d{5}-\d{4}\b/<REDACTED:zip-plus-4>/g' "$out" 2>/dev/null

  return 0
}
# ---- end VENDORED -----------------------------------------------------------

main() {
  case "${1:-}" in
    --check)
      local in="${2:-}"
      [ -n "$in" ] && [ -f "$in" ] || { echo "usage: scrub_body.sh --check <in>" >&2; exit 2; }
      local tmp; tmp="$(mktemp)"
      scrub_body "$in" "$tmp"; local rc=$?
      rm -f "$tmp"
      exit $rc
      ;;
    "" )
      echo "usage: scrub_body.sh <in> <out> | scrub_body.sh --check <in>" >&2
      exit 2
      ;;
    *)
      scrub_body "$1" "${2:?usage: scrub_body.sh <in> <out>}"
      exit $?
      ;;
  esac
}

# Run main only when executed directly (not when sourced).
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
