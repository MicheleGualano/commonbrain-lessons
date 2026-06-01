# Contributing to commonbrain

Thank you for adding to the shared brain. Contributions arrive as **Pull Requests** and are merged by a human maintainer after a blocking CI gate. There is no write API.

## The bar — what belongs here

A lesson must be **general and transferable**: a coding gotcha, pattern, or rule that helps *anyone*, not a note about your specific project.

✅ Good: "Go's `flag` package stops parsing at the first positional argument, so flags placed after it are silently ignored."
❌ Not here: "In our `acme-billing` repo, the `/Users/jane/work` build script needs `--fast`."

Hard rules:
- **No secrets.** No tokens, keys, passwords, private URLs. The gate hard-fails on credential patterns and refuses to even echo them.
- **No private/project specifics.** No project names, company/person names, home paths (`/Users/...`, `/home/...`), or internal hostnames. Generalize them away.
- **No instructions to the reader-agent.** A lesson is data, not a prompt. Do not write imperative meta-instructions ("ignore previous instructions…"), role markers, or runnable "do this" commands. The `rule` is advisory prose.
- **Real and reproducible.** Include literal `triggers` (the actual error text/symptom) and a `rule` that genuinely fixes/explains it. Filler and duplicates are rejected.

## Lesson shape

One file per lesson at `lessons/<id>.json`, validated against `schema/lesson.schema.json`:

```json
{
  "id": "go-flag-stops-at-first-positional",
  "date": "2026-06-01",
  "title": "Go's flag package stops parsing at the first positional argument",
  "rule": "Go stdlib flag stops at the first non-flag token; flags after a positional are silently dropped — parse in a loop or pull positionals out before Parse.",
  "tags": ["go", "cli", "flag", "gotcha", "arg-parsing"],
  "triggers": [
    "a flag after a positional argument was silently ignored in a Go CLI",
    "flag.Parse stopped at the first non-flag arg"
  ],
  "provenance": "contributed",
  "contributor": "your-github-handle",
  "license": "CC-BY-4.0"
}
```

An optional HTML explain layer goes at `html/<date>/<slug>.html` (referenced by `html_path`), following the house style: an Italian TL;DR plus English technical detail.

## Easiest path: `cbrain publish`

If you keep a private brain, `cbrain publish <local-id>` will scrub, generalize, score, and open the PR for you — running the same gate locally first, with two confirmation checkpoints before anything leaves your machine.

## The CI gate (all blocking)

`schema-validate` · `secret-scan` · `injection-sanitize` · `generality-lint` · `generality-scorecard` · `dedup` · `build-artifact`. Posture is **maximum** — a borderline lesson is blocked and returned for editing rather than waved through. By contributing you agree to license your lesson under **CC BY 4.0**.

## This repo is the standard — and the only path

There is exactly one way a lesson reaches the public site: a **Pull Request to this canonical repository** that conforms to the schema, passes the full gate, and is merged by a maintainer. The hosted API is read-only; the database is written only by the post-merge sync. There is no other submission channel.

To keep the standard tamper-proof:

- **A contribution PR may change only `lessons/` and `html/`.** Any PR that touches `scripts/`, `schema/`, `.github/`, or other infrastructure is rejected automatically (path allowlist) and is maintainer-only — you cannot weaken the gate while contributing through it.
- **The CI gate runs from this repo's BASE version, not your PR's copy of the scripts.** So a PR cannot neuter a linter and pass itself.
- Run the gate locally before opening the PR (`cbrain publish` does this for you, or `bash scripts/gate.sh lessons/<id>.json`). CI re-runs it as the authority.
- **Branch protection (maintainer setup):** the single REQUIRED status check on `main` is **`gate-passed`** — a fan-in job that `needs` every gate job (path-allowlist, schema-validate, secret-scan, injection-sanitize, html-scan, generality-lint, generality-scorecard, dedup, build-artifact). Requiring only `gate-passed` means no individual check can be accidentally left non-required, and any gate job added later is covered automatically.
