# Build log

One entry per step: what was asked, what was done, what went wrong. Newest at the bottom.

## Step 1: Scaffold and security baseline (2026-11-15)

**Asked:** the folder structure from CLAUDE.md section 4, `.gitignore`, `.env.example`, a secret-check script installed as a pre-commit hook, the portfolio / research / categories / defaults config, a README stub, decisions and this log, then commit and push. No product features.

**Done:**
- Scaffolded every folder from CLAUDE.md section 4. Python modules hold a one-line docstring; empty frontend folders hold a `.gitkeep`.
- `.gitignore` (ignores `.env*`, keeps `.env.example`), `.gitattributes` (LF line endings), `.env.example` (names only).
- `scripts/check-secrets.sh` and `scripts/install-hooks.sh`. The scanner also has an `--all` mode for CI.
- `config/`: 18-company portfolio, 4 research companies, 17 announcement categories (weight, routine flag, alert default, card type, rationale) and the smart defaults (24 h window, 2x volume, 5% move, 20-day lookback).
- `backend/tests/test_config.py`: 7 standard-library tests over the config files.
- README stub and `docs/` (decisions, data-sources, architecture, cost, this log).

**Verified:**
- `git check-ignore -v .env` matches `.gitignore:2:.env*`, and `.env.example` is not ignored.
- A real `git commit` was blocked by the installed hook while fake Google, Groq, Tavily and `sk-` keys, a password assignment, a random token and a `.env` file were staged. The output named file, line and rule and printed no key material. A line marked `secret-check:allow` was skipped.
- The scanner raised no false positives on: a BSE-style URL with a long token, a lockfile hash, a sha256, a hyphenated word ending in "sk", variable references on the right of `api_key =`, and a GitHub Actions `secrets.` expression.
- `py -m unittest discover -s backend/tests`: 7 tests OK.

**Issues:**
- Step 0 had not been done: there was no GitHub repo yet and git had no identity. The repo was initialised locally first, then created as an empty public repo with the `gh` CLI. Commits use a repo-local GitHub noreply identity because the repo is public.
- GitHub rejected the first push because the `gh` token has no `workflow` scope, so the one-job CI workflow (secret scan with `--all`) was taken out of the commit. To add it later, run `gh auth refresh -h github.com -s workflow` once. The same scope is needed for the GitHub Actions source probe in Step 3 and for a scheduled pipeline run.
- The first scanner took 35 s per run on Windows, because it started about 15 processes per file. It now exports the staged files once and runs three recursive greps: 0.7 s, same detections. It also refuses to report "clean" if its export is incomplete.
- `python` is not on PATH on this machine (a Microsoft Store alias); `py` works (Python 3.14).
- Symbols and `size_bucket` labels in `config/` are not verified against live data yet. That is Step 3.
