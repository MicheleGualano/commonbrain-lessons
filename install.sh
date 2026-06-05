#!/bin/sh
# commonbrain installer — put `cbrain` (search the shared coding-lessons brain) on
# PATH for any coding agent, with no clone.
#
# SECURITY (commonbrain Pillar 0): the executable CODE (search_local.py, cbrain)
# is pinned to a release tag and verified against SHA-256 checksums BEFORE it
# touches your machine — this is deliberately NOT a `curl … | sh` of a moving
# branch. The lesson DATA is fetched live and treated as UNVERIFIED community
# data, never instructions. Review this script before you run it.
#
# Usage:
#   curl -fsSLO https://raw.githubusercontent.com/MicheleGualano/commonbrain-lessons/v0.1.0/install.sh
#   sh install.sh
# Override targets with COMMONBRAIN_HOME / COMMONBRAIN_BIN / COMMONBRAIN_REF.
set -eu

REF="${COMMONBRAIN_REF:-v0.1.0}"
PREFIX="${COMMONBRAIN_HOME:-$HOME/.commonbrain}"
BINDIR="${COMMONBRAIN_BIN:-$HOME/.local/bin}"
RAW="${COMMONBRAIN_RAW:-https://raw.githubusercontent.com/MicheleGualano/commonbrain-lessons/$REF}"
DATA_URL="${COMMONBRAIN_DATA_URL:-https://michelegualano.github.io/commonbrain-lessons/lessons.jsonl}"

# Pinned SHA-256 of the executable code at REF=v0.1.0 (the DATA is not pinned).
SEARCH_SHA="583c56b6c03298bd383971e52f08a0e5acf42f2112425835d326ca2d6b2cf1f2"
CBRAIN_SHA="939dc5e06401fd6f41aaa02572dbafc4dc3ef9838a5504cf21e3324093235791"

say() { printf 'commonbrain: %s\n' "$*"; }
die() { printf 'commonbrain: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required."
if command -v curl >/dev/null 2>&1; then DL='curl -fsSL -o'
elif command -v wget >/dev/null 2>&1; then DL='wget -qO'
else die "need curl or wget."; fi

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else die "no sha256 tool (need sha256sum or shasum)."; fi
}

fetch_verify() { # url dest expected_sha
  $DL "$2" "$1" || die "download failed: $1"
  got="$(sha256 "$2")"
  [ "$got" = "$3" ] || die "CHECKSUM MISMATCH for $1 (got $got, want $3) — refusing to install unverified code."
}

# Fetch + verify ALL code into a temp dir first; only touch the install prefix
# once every checksum passes, so a tampered/failed download never lands on disk.
tmpd="$(mktemp -d 2>/dev/null || mktemp -d -t cbrain)" || die "mktemp failed."
trap 'rm -rf "$tmpd"' EXIT INT TERM

say "fetching + verifying code…"
fetch_verify "$RAW/scripts/search_local.py" "$tmpd/search_local.py" "$SEARCH_SHA"
fetch_verify "$RAW/bin/cbrain" "$tmpd/cbrain" "$CBRAIN_SHA"

mkdir -p "$PREFIX/scripts" "$PREFIX/build" "$BINDIR"
mv "$tmpd/search_local.py" "$PREFIX/scripts/search_local.py"
mv "$tmpd/cbrain" "$BINDIR/cbrain"
chmod +x "$BINDIR/cbrain"

say "syncing lessons (untrusted data)…"
$DL "$PREFIX/build/lessons.jsonl" "$DATA_URL" || die "could not fetch the corpus from $DATA_URL"

say "verifying the install…"
CBRAIN_HOME="$PREFIX" "$BINDIR/cbrain" doctor || die "doctor reported a problem."

say "installed.  cbrain -> $BINDIR/cbrain   data -> $PREFIX"
case ":${PATH}:" in
  *":$BINDIR:"*) : ;;
  *) say "NOTE: $BINDIR is not on your PATH — add:  export PATH=\"$BINDIR:\$PATH\"" ;;
esac
say "try:  cbrain search \"your error or symptom\""
