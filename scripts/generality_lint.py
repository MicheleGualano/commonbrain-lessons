#!/usr/bin/env python3
"""generality_lint.py — block project-specific leaks in a public lesson (Pillar 0.B/0.C).

High-precision MECHANICAL leaks fail the gate (max posture):
  - home / user paths (/Users/<name>, /home/<name>, C:\\Users\\<name>, /root/)
  - localhost / private-IP / internal-hostname URLs
  - real email addresses (defense-in-depth behind scrub_body)
  - any entity in the stop-list (scripts/stoplist.txt, plaintext or sha256:<hash>,
    plus the optional ~/.printing-press/amend-config.yaml)
  - leftover <REDACTED:...> tags (a public lesson should be rewritten, not redacted)

Lower-precision PROPER-NOUN guesses (CamelCase / ALLCAPS unknown tokens) are
reported as REVIEW notes only — they do NOT fail, because legit code lessons are
full of identifiers like GetLesson/APISpec. The fuzzy "is this project-specific?"
judgment is left to the agentic generality scorecard, not a regex.

Usage: generality_lint.py lessons/<id>.json [...]
Exit 0 clean · 1 finding · 2 usage/IO.
"""
import hashlib
import json
import os
import re
import sys

HOME_PATHS = [
    (r'(?i)/Users/(?!shared\b)[A-Za-z0-9._-]+', 'macOS home path with username'),
    (r'(?i)/home/(?!runner\b)[A-Za-z0-9._-]+', 'Linux home path with username'),
    (r'(?i)C:\\Users\\[A-Za-z0-9._-]+', 'Windows home path with username'),
    (r'/root/[A-Za-z0-9._-]+', 'root home path'),
    (r'~[a-z][a-z0-9._-]+/', 'named user home (~user/)'),
    (r'\$HOME/|%USERPROFILE%', 'home env var path'),
    (r'\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9._$-]+', 'Windows UNC path (\\\\server\\share)'),
]

NET_LEAKS = [
    (r'(?i)\b(?:https?://)?localhost(?::\d+)?\b', 'localhost reference'),
    (r'\b127\.0\.0\.1\b|\b0\.0\.0\.0\b', 'loopback IP'),
    (r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'private IP (10.x)'),
    (r'\b192\.168\.\d{1,3}\.\d{1,3}\b', 'private IP (192.168.x)'),
    (r'\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b', 'private IP (172.16-31.x)'),
    (r'(?i)\bhttps?://[A-Za-z0-9.-]+\.(?:local|internal|lan|corp|intranet)\b', 'internal hostname URL'),
    (r'(?i)\bfile://[A-Za-z0-9][A-Za-z0-9.-]*/', 'file:// URL with a host authority (internal host)'),
]

EMAIL = (
    r'\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|net|org|invalid)\b|[^\s]*\.(?:test|localhost|example)\b)'
    r'[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'email address',
)

REDACTION_TAG = (r'<REDACTED:[^>]+>', 'leftover <REDACTED:..> tag — rewrite to general form instead of redacting')
OBFUSCATED_EMAIL = (r'(?i)[a-z0-9._%+-]+\s*[\[(]\s*at\s*[\])]\s*[a-z0-9.-]+\s*[\[(]\s*dot\s*[\])]', 'obfuscated email ("x [at] y [dot] z")')

# Tech/vendor names that are fine to mention (NOT project-specific).
SAFE_NOUNS = {
    'GitHub', 'GitLab', 'Git', 'Go', 'Golang', 'Python', 'Rust', 'Java', 'JavaScript',
    'TypeScript', 'Node', 'Deno', 'Bun', 'Claude', 'Anthropic', 'OpenAI', 'Slack',
    'Linear', 'Stripe', 'AWS', 'GCP', 'Azure', 'Supabase', 'Postgres', 'PostgreSQL',
    'SQLite', 'MySQL', 'Redis', 'Docker', 'Kubernetes', 'Terraform', 'macOS', 'Linux',
    'Windows', 'Unix', 'POSIX', 'JSON', 'JSONL', 'YAML', 'TOML', 'HTML', 'CSS', 'HTTP',
    'HTTPS', 'API', 'CLI', 'MCP', 'SQL', 'OpenAPI', 'Cobra', 'Bash', 'Zsh', 'Homebrew',
    'OAuth', 'JWT', 'TLS', 'SSH', 'URL', 'URI', 'UTF', 'ASCII', 'Unicode', 'RFC',
    'CWE', 'CVE', 'README', 'TODO', 'CI', 'PR', 'IDE', 'VS', 'Code', 'GitHub.com',
    'GNU', 'EOF', 'EOL', 'EOT', 'ANSI', 'UUID', 'CSV', 'XML', 'DNS', 'TCP', 'UDP',
}

PROPER_NOUN = re.compile(r'\b(?:[A-Z][a-z]+){2,}\b|\b[A-Z]{3,}\b')

# Candidate-token shape for hashed stop-list matching: a word, optionally joined by
# single . _ - separators (so "alpha-beta", "x.y", "name100" tokenize as one unit —
# mirrors the word-boundary precision of the plaintext match).
TOKEN_RE = re.compile(r'[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*')


def _texts(lesson):
    out = []
    for k in ('title', 'rule'):
        if isinstance(lesson.get(k), str):
            out.append((k, lesson[k]))
    for i, t in enumerate(lesson.get('triggers') or []):
        out.append((f'triggers[{i}]', t))
    return out


def _strip_html(html):
    html = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', html)
    return re.sub(r'(?s)<[^>]+>', ' ', html)


def load_stoplist():
    """Entity stop-list. Sources, in order:
      - repo scripts/stoplist.txt: plaintext terms (# comments) AND `sha256:<hex>` lines
        (the SHA-256 of a lowercased SENSITIVE term, kept hashed so the term itself never
        ships in this public file).
      - optional ~/.printing-press/amend-config.yaml (plaintext companies/people/emails).
    Returns (terms, hashes): terms = list of (term, kind); hashes = set of hex digests."""
    terms = []
    hashes = set()
    repo_list = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stoplist.txt')
    if os.path.isfile(repo_list):
        for line in open(repo_list, encoding='utf-8'):
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if line.lower().startswith('sha256:'):
                h = line.split(':', 1)[1].strip().lower()
                if h:
                    hashes.add(h)
            else:
                terms.append((line, 'stoplist'))
    path = os.path.expanduser('~/.printing-press/amend-config.yaml')
    if not os.path.isfile(path):
        return terms, hashes
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(open(path, encoding='utf-8')) or {}
        for kind in ('companies', 'people', 'emails'):
            for v in (data.get(kind) or []):
                if isinstance(v, str) and v.strip():
                    terms.append((v.strip(), kind))
    except Exception:
        # minimal fallback: lines like "  - value" under a known key
        kind = None
        for line in open(path, encoding='utf-8'):
            m = re.match(r'^(companies|people|emails)\s*:', line)
            if m:
                kind = m.group(1)
                continue
            m = re.match(r'^\s*-\s*(.+?)\s*$', line)
            if m and kind:
                terms.append((m.group(1).strip('\'"'), kind))
    return terms, hashes


def scan(label, s, terms, hashes):
    fails, reviews = [], []
    for bank in (HOME_PATHS, NET_LEAKS):
        for pat, desc in bank:
            if re.search(pat, s):
                fails.append((label, desc))
    for pat, desc in (EMAIL, REDACTION_TAG, OBFUSCATED_EMAIL):
        if re.search(pat, s):
            fails.append((label, desc))
    for term, kind in terms:
        if re.search(r'(?i)(?<!\w)' + re.escape(term) + r'(?!\w)', s):
            fails.append((label, f'stop-list {kind}: "{term}"'))
    if hashes:
        for tok in TOKEN_RE.findall(s):
            if hashlib.sha256(tok.lower().encode('utf-8')).hexdigest() in hashes:
                # never echo the matched token: this file and CI logs are public.
                fails.append((label, 'stop-list (hashed entity)'))
                break
    for m in PROPER_NOUN.findall(s):
        if m not in SAFE_NOUNS:
            reviews.append((label, f'possible proper noun "{m}" — confirm it is not project-specific'))
    return fails, reviews


def main(argv):
    paths = argv[1:]
    if not paths:
        print('usage: generality_lint.py lessons/<id>.json [...]', file=sys.stderr)
        return 2
    terms, hashes = load_stoplist()
    total_fail = 0
    for p in paths:
        try:
            lesson = json.load(open(p, encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            print(f'✗ {p}: cannot read/parse: {e}', file=sys.stderr)
            total_fail += 1
            continue
        items = _texts(lesson)
        hp = lesson.get('html_path')
        if isinstance(hp, str):
            root = os.path.dirname(os.path.dirname(os.path.abspath(p)))
            hf = os.path.join(root, hp)
            if os.path.isfile(hf):
                raw = open(hf, encoding='utf-8').read()
                items.append((f'html:{hp}', _strip_html(raw)))
                items.append((f'html-raw:{hp}', raw))  # catch leaks in attributes / comments
        fails, reviews = [], []
        for label, s in items:
            f, r = scan(label, s, terms, hashes)
            fails += f
            reviews += r
        if fails:
            total_fail += len(fails)
            print(f'✗ {p}', file=sys.stderr)
            for label, desc in fails:
                print(f'    [leak] {label}: {desc}', file=sys.stderr)
        for label, desc in reviews:
            print(f'    [review] {p} {label}: {desc}', file=sys.stderr)
    if total_fail:
        print(f'generality_lint: BLOCKED — {total_fail} leak(s).', file=sys.stderr)
        return 1
    print(f'generality_lint: clean ({len(paths)} lesson(s)).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
