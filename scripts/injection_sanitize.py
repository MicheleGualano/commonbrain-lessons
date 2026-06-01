#!/usr/bin/env python3
"""injection_sanitize.py — aggressive anti-prompt-injection gate (Pillar 0.A).

commonbrain lessons are PUBLIC and read by agents, so a malicious lesson could
try to smuggle instructions into the reading agent's context. This linter treats
every field (and the HTML explain layer) as HOSTILE and BLOCKS on any sign of an
injection / exfiltration / dangerous-advice payload. Posture is MAXIMUM.

Hardened after a red-team pass (multilingual + paraphrase overrides, fake-consent,
permission-disabling, HTML-prose vectors, and unicode obfuscation — fullwidth,
combining marks, homoglyph scripts). Defense relies on THREE layers; this regex
gate is one of them. The other two — a human maintainer merge and (planned)
agentic plausibility review — are required backstops, because a regex can never
catch every phrasing or every piece of subtly-wrong advice (data poisoning).

Usage: injection_sanitize.py lessons/<id>.json [...]
Exit 0 clean · 1 finding · 2 usage/IO.
"""
import json
import os
import re
import sys
import unicodedata

# --- override / role-reassignment / covert / exfil (multilingual + paraphrase) ---
META = [
    # English literal + paraphrase overrides
    (r'ignore\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|above|prior|earlier|preceding)\s+(?:instructions?|prompts?|messages?|context|rules?)', 'override (ignore previous)'),
    (r'disregard\s+(?:all\s+|the\s+)?(?:previous|above|prior|earlier|preceding)', 'override (disregard above)'),
    (r'forget\s+(?:everything|all|(?:the\s+)?(?:above|previous|prior|rules?|instructions?))', 'override (forget above)'),
    (r'(?:set\s+aside|put\s+aside|override|ignore|drop|bypass)\s+(?:whatever|the|any|your)?\s*(?:guidance|instructions?|rules?|framing|constraints?|restrictions?)', 'override (set aside the guidance)'),
    (r'regardless\s+of\s+(?:earlier|prior|previous|any)\s+(?:framing|instructions?|context)', 'override (regardless of earlier framing)'),
    (r'(?:the\s+)?(?:correct|real|actual|true)\s+(?:behavior|behaviour|task|assignment|job|instruction)\s+(?:for|is|of)', 'override (the real task is...)'),
    (r'your\s+(?:real|actual|true|only)\s+(?:task|assignment|job|directive|goal)\s+is', 'override (your real assignment is...)'),
    (r'treat\s+(?:this|the\s+following|these)\s+(?:as|note\s+as)\s+(?:the|your)?\s*(?:top[- ]priority|authoritative|governing|real|highest)', 'override (treat this as authoritative directive)'),
    (r'\bfrom\s+now\s+on\b', 'override (from now on)'),
    (r'\byou\s+are\s+now\b|\bpretend\s+to\s+be\b|\bact\s+as\s+(?:an?\s+)?(?:ai|assistant|language\s+model|agent|dan|developer\s+mode)', 'role-reassignment'),
    (r'act\s+as\s+an\s+agent\s+(?:with|without)\s+no?\s+(?:security|safety)', 'role-reassignment (no-restrictions agent)'),
    # fabricated consent
    (r'the\s+user\s+(?:has\s+)?(?:already\s+)?(?:said|stated|approved|authoriz|consented|agreed|confirmed)', 'fabricated consent (the user already approved)'),
    (r'report\s+that\s+the\s+user\s+authoriz', 'fabricated consent (report the user authorized)'),
    # disabling human-in-the-loop / safety
    (r'(?:stop|skip|bypass|disable|remove)\s+(?:asking|requiring)?\s*(?:the\s+)?(?:operator|user|human)?\s*(?:for\s+)?(?:permission|approval|confirmation|consent)', 'disable approval gate'),
    (r'without\s+(?:asking|requesting|requiring|seeking)\s+(?:for\s+)?(?:permission|approval|confirmation|the\s+(?:user|operator))', 'act without confirmation'),
    (r'do\s+not\s+(?:ask|request|require|wait\s+for)\s+(?:for\s+)?(?:permission|approval|confirmation)', 'do not ask for permission'),
    (r'(?:never|do\s+not|don\'?t)\s+(?:surface|show|display|report|mention|summari[sz]e|tell)\s+[^.\n]{0,40}(?:warning|advisor|security|to\s+the\s+(?:user|operator))', 'suppress warnings / hide from user'),
    (r'(?:suppress|hide|silence|mute)\s+(?:the\s+)?(?:advisor|warning|security|alert|error)', 'suppress advisories'),
    (r'disable\s+(?:signature|checksum|integrity|certificate|tls|ssl|security|firewall)\s*(?:verif|check|valid)?', 'disable integrity/security control'),
    (r'(?:delete|clear|wipe|erase)\s+(?:your\s+)?(?:shell\s+)?(?:history|logs?|audit)', 'erase evidence (delete history/logs)'),
    (r'stay\s+(?:quiet|silent)\s+about\s+it|leave[s]?\s+no\s+trace|so\s+the\s+step\s+leaves\s+no\s+trace', 'covert (stay silent / no trace)'),
    (r'do\s+not\s+(?:tell|inform|alert|notify|summari[sz]e\s+(?:this\s+)?to)\s+the\s+(?:user|operator|human)', 'covert (do not tell the user)'),
    (r'without\s+(?:telling|informing|alerting|notifying)\s+the\s+(?:user|operator)', 'covert (without telling the user)'),
    # exfiltration / sensitive reads
    (r'\bexfiltrat', 'exfiltration verb'),
    (r'(?:open|read|cat|copy|summari[sz]e|dump|print|send|upload|ship)\s+[^.\n]{0,40}(?:\.env\b|\.pem\b|\.ssh\b|/etc/passwd|environment\s+variables?|env\s+vars?|secrets?|credentials?|api[_\s-]?keys?|access\s+keys?)', 'exfiltration (read/send secrets or .env/.pem)'),
    (r'(?:copy|put|paste|write)\s+[^.\n]{0,40}(?:environment\s+variables?|secrets?|keys?)\s+[^.\n]{0,30}(?:comment|pull\s+request|\bpr\b|file|context\.txt)', 'exfiltration (env into PR comment / file)'),
    (r'(?:add|append|plant|inject)\s+[^.\n]{0,30}(?:ssh|access|deploy|public)\s+key', 'persistence (plant ssh/access key)'),
    (r'ship\s+(?:them\s+)?off[- ]box|send\s+(?:them\s+)?off[- ]box', 'exfiltration (ship off-box)'),
    # non-English overrides (it / es / fr / de / pt)
    (r'(?i)ignora\s+(?:le\s+|tutte\s+le\s+)?(?:istruzioni|regole)\s+(?:precedenti|del\s+sistema|sopra)', 'override IT (ignora le istruzioni)'),
    (r'(?i)dimentica\s+(?:le\s+|tutte\s+le\s+)?(?:istruzioni|regole)\s+precedenti', 'override IT (dimentica le istruzioni)'),
    (r'(?i)prima\s+di\s+(?:tutto|rispondere)[^.\n]{0,40}(?:ignora|esegui|invia)', 'override IT (prima di tutto, ignora/esegui)'),
    (r'(?i)olvida\s+(?:tus\s+|las\s+)?(?:reglas|instrucciones)\s+(?:anteriores|previas)?', 'override ES (olvida tus reglas)'),
    (r'(?i)a\s+partir\s+de\s+ahora\b', 'override ES (a partir de ahora)'),
    (r'(?i)ignora\s+(?:las\s+)?(?:instrucciones|reglas)\s+(?:anteriores|previas)', 'override ES (ignora las instrucciones)'),
    (r'(?i)oublie[sz]?\s+(?:tes\s+|les\s+)?(?:consignes|instructions|r[eè]gles)', 'override FR (oublie les consignes)'),
    (r'(?i)avant\s+toute\s+autre\s+chose\b', 'override FR (avant toute autre chose)'),
    (r'(?i)n\'?en\s+parle\s+pas\s+(?:a|à)\s+l\'?utilisateur', 'covert FR (n\'en parle pas a l\'utilisateur)'),
    (r'(?i)ignoriere\s+(?:alle\s+|die\s+)?(?:vorherigen\s+)?(?:anweisungen|regeln)', 'override DE (ignoriere die Anweisungen)'),
    (r'(?i)ignore\s+(?:as\s+)?(?:instru[çc][õo]es|regras)\s+(?:anteriores|acima)', 'override PT (ignore as instruções anteriores)'),
]

ROLE = [
    (r'(?im)^\s{0,4}(?:system|assistant|user|developer)\s*:', 'chat role marker at line start'),
    (r'(?im)(?:^|\s)(?:system|assistant)\s*:\s*\S', 'inline chat role marker'),
    (r'<\|\s*(?:im_start|im_end|system|assistant|user|endoftext|eot_id|start_header_id|end_header_id)\s*\|>', 'special chat token (<|...|>)'),
    (r'<\|[^>]{0,40}\|>', 'special-token-shaped marker'),
    (r'\[/?INST\]|<<\s*/?\s*SYS\s*>>', 'Llama-style instruction marker'),
    (r'(?im)^#{2,}\s*(?:system|instruction|response|assistant)\b', 'markdown header role marker'),
    (r'(?i)(?:</?)\s*(?:antml\s*:|invoke\b|function_calls\b|tool_use\b|function_call\b)', 'tool-call / antml invocation marker'),
    (r'(?i)```\s*(?:tool_use|tool_code|function_call|json_tool)', 'fenced tool-call block'),
]

EXEC = [
    (r'(?i)\b(?:curl|wget|fetch)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:bash|sh|zsh|ksh|fish|python3?|perl|node|ruby|php)\b', 'pipe-to-shell (curl|bash)'),
    (r'(?i)\bbase64\s+(?:-d|--decode)\b[^\n]{0,120}\|\s*(?:bash|sh|zsh|python3?|perl)', 'base64-decode pipe-to-shell'),
    (r'(?i)\b(?:bash|sh|zsh)\s*<\(\s*(?:curl|wget)', 'process-substitution pipe-to-shell'),
    (r'(?i)\brm\s+(?:-[a-z]*[rf][a-z]*|--recursive|--force)(?:\s+(?:--recursive|--force|-[a-z]+))*\s+(?:/|~|\.|\$)', 'destructive rm -rf / --recursive --force'),
    (r'(?i)\b(?:eval|exec)\s*\(', 'eval/exec call'),
    (r'(?i):\(\)\s*\{\s*:\|:&\s*\}\s*;', 'fork-bomb'),
    (r'(?i)\b(?:run|execute|paste|enter|drop)\s+(?:the\s+)?(?:following|snippet|command|code|script|line|this)\b', 'instruction to run code/snippet'),
    (r'(?i)\beval\s+["\']?(?:\$\(|`)', 'shell eval of command substitution (eval "$(...)")'),
    (r'(?i)\bcopy\b[^\n]{0,40}\bpaste\b[^\n]{0,40}\b(?:terminal|shell|run|execute)\b', 'copy-paste-and-run instruction'),
    (r'(?i)\bpip\s+install\b[^\n]{0,80}--(?:extra-)?index-url[^\n]{0,40}https?://', 'pip install from a custom index URL'),
    (r'(?i)(?:pre|post)install\b[^\n]{0,60}(?:curl|wget|\bbash\b|\bsh\b|node\s+-e|eval)', 'package lifecycle script runs a command'),
    (r'(?i)curl\s+[^\n]{0,160}-o\s+\S+\.(?:sh|bash|py)\b', 'download a script to run (fetch-then-exec)'),
    (r'(?i)\bchmod\s+\+x\b[^\n]{0,40}(?:&&|;)\s*\./', 'chmod +x && run'),
    (r'(?i)\b(?:bash|sh|zsh|python3?)\s+/tmp/\S+', 'run a downloaded /tmp script'),
    (r'(?i)(?:IEX|Invoke-Expression)\b[^\n]{0,80}(?:DownloadString|New-Object\s+Net\.WebClient|iwr|Invoke-WebRequest)', 'PowerShell download-and-execute (IEX)'),
    (r'(?i)\bbash\s+-i\b[^\n]{0,30}(?:>&|/dev/tcp/)', 'reverse shell (bash -i /dev/tcp)'),
    (r'/dev/tcp/[0-9a-z.]+/[0-9]+', 'reverse-shell /dev/tcp socket'),
    (r'(?i)<\s*function\s*=|\bfunction\s*=\s*["\']?[a-z_]+["\']?\s*[>(]', 'tool-call function= marker'),
]

# Supplementary secrets the vendored scrub_body does not cover (red-team found GCP,
# GitLab, connection strings, private keys, etc.). scrub_body stays the canonical
# first layer; these benefit from this script's NFKC normalization too.
SECRET_EXTRA = [
    (r'\bAIza[0-9A-Za-z_\-]{35}\b', 'GCP API key (AIza...)'),
    (r'\bya29\.[0-9A-Za-z_\-]{20,}', 'Google OAuth token (ya29.)'),
    (r'\bglpat-[0-9A-Za-z_\-]{20,}', 'GitLab PAT (glpat-)'),
    (r'\bSG\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}', 'SendGrid key (SG.)'),
    (r'\bnpm_[A-Za-z0-9]{36}\b', 'npm token (npm_)'),
    (r'\b(?:AC|SK)[0-9a-f]{32}\b', 'Twilio SID/key'),
    (r'-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+|DSA\s+|PGP\s+)?PRIVATE\s+KEY-----', 'private key block'),
    (r'(?i)AccountKey=[A-Za-z0-9+/]{40,}={0,2}', 'Azure storage AccountKey'),
    (r'(?i)(?:DefaultEndpointsProtocol|AccountName)=[^;\n]+;[^.\n]{0,80}AccountKey=', 'Azure connection string'),
    (r'(?i)\b[a-z0-9+/]{60,}={0,2}\b\s*\|\s*(?:base64|bash|sh)', 'long base64 blob piped to decode/shell'),
    (r'(?i)_authToken\s*=\s*[A-Za-z0-9_\-]{8,}', 'npm _authToken'),
    (r'(?i)//[a-z0-9.\-]+/:_authToken', 'npm registry _authToken'),
    (r'(?i)(?:round[- ]?trip|encode|ship|store|pass|send|transmit)\s+(?:it|them|the\s+\w+)?\s*[^.\n]{0,30}(?:through\s+base64|as\s+hex|hex[- ]?encoded|base64[- ]?encoded|in\s+(?:base64|hex))', 'advice to encode/obfuscate a secret'),
    (r'(?i)(?:base64|hex)[- ]?(?:encod|decod)[^\n]{0,30}(?:key|secret|token|account\s*key|credential)', 'encode/decode a secret'),
    (r'\bsk-(?:proj-)?[A-Za-z0-9]{20,}', 'OpenAI API key (sk-)'),
    (r'(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:/@]+:[^\s@/]{3,}@', 'connection string with inline password'),
    (r'(?i)\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]{3,}@[^\s/]+', 'URL with inline credentials (user:pass@host)'),
]

# Core vendor-prefix tokens, also scanned against a WHITESPACE-STRIPPED copy of each
# field to catch space-obfuscated secrets ("g h p _ ...").
SECRET_CORE = [
    (r'ghp_[A-Za-z0-9]{20,}', 'GitHub PAT'),
    (r'gho_[A-Za-z0-9]{20,}', 'GitHub OAuth token'),
    (r'ghs_[A-Za-z0-9]{20,}', 'GitHub server token'),
    (r'\bAKIA[0-9A-Z]{12,}', 'AWS access key'),
    (r'sk_live_[A-Za-z0-9]{16,}', 'Stripe live key'),
    (r'sk-ant-api03-[A-Za-z0-9_\-]{20,}', 'Anthropic key'),
    (r'xox[baprs]-[A-Za-z0-9-]{10,}', 'Slack token'),
    (r'lin_api_[A-Za-z0-9_\-]{20,}', 'Linear key'),
    (r'AIza[0-9A-Za-z_\-]{30,}', 'GCP API key'),
    (r'glpat-[0-9A-Za-z_\-]{18,}', 'GitLab PAT'),
]

# A few high-signal pieces of DANGEROUS ADVICE (data-poisoning). This is only a
# partial net — most subtly-wrong advice is caught by human merge + agentic review.
DANGEROUS_ADVICE = [
    (r'(?i)\bchmod\s+(?:-R\s+|--recursive\s+)?(?:0)?777\b', 'dangerous advice: chmod 777'),
    (r'(?i)(?:commit|check\s*in|add|do\s+not\s+gitignore|don\'?t\s+gitignore)\s+[^.\n]{0,40}\.env\b', 'dangerous advice: commit/keep .env in the repo'),
    (r'(?i)check\s+(?:your\s+)?\.env[^.\n]{0,80}into\b', 'dangerous advice: check .env into the repo'),
    (r'(?i)(?:verify\s*=\s*False|InsecureSkipVerify\s*[:=]\s*true|--no-check-certificate|rejectUnauthorized\s*[:=]\s*false)', 'dangerous advice: disable TLS verification'),
    (r'(?i)curl\s+[^\n]{0,40}(?:-k|--insecure)\b', 'dangerous advice: curl --insecure'),
    (r'(?i)Access-Control-Allow-Origin[^\n]{0,40}\*[^\n]{0,80}credential', 'dangerous advice: CORS wildcard with credentials'),
    (r'(?i)allow[- ]?origin[^\n]{0,20}(?:\*|wildcard)[^\n]{0,60}(?:allow[- ]?credentials|with\s+credentials)', 'dangerous advice: CORS wildcard with credentials'),
    (r'(?i)\beval\b[^\n]{0,30}(?:the\s+)?(?:config|configuration|user\s+input|the\s+input|untrusted)', 'dangerous advice: eval config / user input'),
]

HTML_DANGER = [
    (r'(?i)<\s*script\b', '<script> tag'),
    (r'(?i)<\s*(?:iframe|object|embed|applet|frame)\b', 'embedded-frame/object tag'),
    (r'(?i)javascript\s*:', 'javascript: URI'),
    (r'(?i)\son[a-z]+\s*=', 'inline event handler'),
    (r'(?i)srcdoc\s*=', 'iframe srcdoc'),
    (r'(?i)data\s*:\s*text/html', 'data:text/html URI'),
    (r'(?i)<\s*meta[^>]+http-equiv', 'meta http-equiv'),
    (r'(?i)<\s*link[^>]+rel\s*=\s*["\']?\s*import', 'HTML import'),
]

CONFUSABLE = {'CYRILLIC', 'GREEK', 'CHEROKEE', 'ARMENIAN', 'COPTIC', 'FULLWIDTH',
              'MATHEMATICAL', 'CIRCLED', 'SQUARED', 'PARENTHESIZED', 'GEORGIAN'}


def variants(s):
    """Raw + NFKC + combining-stripped + NFKC(combining-stripped) — defeats fullwidth,
    homoglyph normalization, and diacritic-split obfuscation before pattern matching."""
    out = {s}
    nfkc = unicodedata.normalize('NFKC', s)
    out.add(nfkc)
    stripped = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    out.add(stripped)
    out.add(unicodedata.normalize('NFKC', stripped))
    # percent-decode the few separators attackers use to hide a credential boundary
    out.add(nfkc.replace('%40', '@').replace('%3A', ':').replace('%3a', ':'))
    return out


def _script(ch):
    try:
        return unicodedata.name(ch).split(' ')[0]
    except ValueError:
        return None


def unicode_findings(label, s):
    out = []
    for ch in s:
        cp, cat = ord(ch), unicodedata.category(ch)
        if cat == 'Cf' or cp == 0x00AD or 0xE0000 <= cp <= 0xE007F:
            out.append((label, 'unicode', f'zero-width/format/bidi/tag char U+{cp:04X}'))
        elif cat in ('Co', 'Cs'):
            out.append((label, 'unicode', f'private-use/surrogate char U+{cp:04X}'))
        elif cat == 'Cc' and ch not in '\n\t\r':
            out.append((label, 'unicode', f'control char U+{cp:04X}'))
        elif cat in ('Mn', 'Mc', 'Me'):
            out.append((label, 'unicode', f'combining mark U+{cp:04X} (diacritic-split obfuscation)'))
        elif ch.isalpha():
            sc = _script(ch)
            if sc in CONFUSABLE:
                out.append((label, 'unicode', f'{sc.lower()} homoglyph char U+{cp:04X} ({ch!r})'))
    # mixed-script token (alpha chars from >1 script)
    for word in re.split(r'\s+', s):
        scripts = {_script(c) for c in word if c.isalpha()}
        scripts.discard(None)
        if len(scripts) > 1:
            out.append((label, 'unicode', f'mixed-script token {word!r} ({sorted(scripts)})'))
    # de-dup
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f); uniq.append(f)
    return uniq[:12]


def scan(label, s, banks):
    out = []
    vs = variants(s)
    for bank in banks:
        for pat, desc in bank:
            if any(re.search(pat, v) for v in vs):
                out.append((label, 'pattern', desc))
    return out


def strip_html(html, drop_code=False):
    html = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', html)
    if drop_code:
        html = re.sub(r'(?is)<(pre|code)\b.*?</\1>', ' ', html)
    return re.sub(r'(?s)<[^>]+>', ' ', html)


def _dedup(items):
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it); out.append(it)
    return out


def check_lesson(path):
    """Returns (findings, reviews). findings BLOCK (unambiguous: injection / exec /
    secret / unicode). reviews are non-blocking DANGEROUS_ADVICE flags — a regex
    cannot tell a lesson that ADVOCATES bad advice from one that WARNS against it,
    so that judgment is surfaced to the agentic review + human merge instead."""
    findings, reviews = [], []
    try:
        lesson = json.loads(open(path, encoding='utf-8').read())
    except (OSError, json.JSONDecodeError) as e:
        return [(path, 'io', f'cannot read/parse: {e}')], []

    fields = []
    for k in ('title', 'rule'):
        if isinstance(lesson.get(k), str):
            fields.append((k, lesson[k]))
    for i, t in enumerate(lesson.get('triggers') or []):
        if isinstance(t, str):
            fields.append((f'triggers[{i}]', t))
    for i, t in enumerate(lesson.get('tags') or []):
        if isinstance(t, str):
            fields.append((f'tags[{i}]', t))

    def scan_one(label, s):
        findings.extend(unicode_findings(label, s))
        findings.extend(scan(label, s, [META, ROLE, EXEC, SECRET_EXTRA]))
        despaced = re.sub(r'\s+', '', s)
        for pat, desc in SECRET_CORE:
            if re.search(pat, despaced):
                findings.append((label, 'pattern', f'{desc} (whitespace-obfuscated)'))
        reviews.extend(scan(label, s, [DANGEROUS_ADVICE]))

    for label, s in fields:
        scan_one(label, s)

    hp = lesson.get('html_path')
    if isinstance(hp, str):
        root = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        hf = os.path.join(root, hp)
        if os.path.isfile(hf):
            html = open(hf, encoding='utf-8').read()
            findings.extend(scan(f'html:{hp}', html, [HTML_DANGER]))
            # prose with code blocks dropped (genuine command samples allowed),
            # but META/ROLE/EXEC/secret directives in prose ARE caught.
            scan_one(f'html-text:{hp}', strip_html(html, drop_code=True))
        else:
            findings.append((f'html:{hp}', 'io', 'html_path does not resolve to a file'))
    return _dedup(findings), _dedup(reviews)


def scan_html_file(path):
    """Scan a RAW HTML file directly (for orphan/standalone html/ files that no
    lesson references but that still get served). Same banks as the HTML branch
    of check_lesson. Returns (findings, reviews)."""
    findings, reviews = [], []
    try:
        html = open(path, encoding='utf-8').read()
    except OSError as e:
        return [(path, 'io', f'cannot read: {e}')], []
    findings.extend(scan(path, html, [HTML_DANGER]))
    prose = strip_html(html, drop_code=True)
    findings.extend(unicode_findings(path, prose))
    findings.extend(scan(path, prose, [META, ROLE, EXEC, SECRET_EXTRA]))
    despaced = re.sub(r'\s+', '', prose)
    for pat, desc in SECRET_CORE:
        if re.search(pat, despaced):
            findings.append((path, 'pattern', f'{desc} (whitespace-obfuscated)'))
    reviews.extend(scan(path, prose, [DANGEROUS_ADVICE]))
    return _dedup(findings), _dedup(reviews)


def main(argv):
    args = argv[1:]
    html_mode = False
    if args and args[0] == '--html':
        html_mode = True
        args = args[1:]
    paths = args
    if not paths:
        print('usage: injection_sanitize.py [--html] <file> [...]', file=sys.stderr)
        return 2
    total = 0
    for p in paths:
        fs, rv = scan_html_file(p) if html_mode else check_lesson(p)
        if fs:
            total += len(fs)
            print(f'✗ {p}', file=sys.stderr)
            for label, kind, desc in fs:
                print(f'    [{kind}] {label}: {desc}', file=sys.stderr)
        for label, kind, desc in rv:
            print(f'    [review] {p} {label}: {desc} — confirm the lesson WARNS against this, not advocates it', file=sys.stderr)
    if total:
        print(f'injection_sanitize: BLOCKED — {total} finding(s).', file=sys.stderr)
        return 1
    print(f'injection_sanitize: clean ({len(paths)} lesson(s)).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
