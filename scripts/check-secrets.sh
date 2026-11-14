#!/usr/bin/env bash
# Secret scan for FINN: stops API keys, tokens and .env files from being committed.
#
#   scripts/check-secrets.sh          scan the files staged for commit (pre-commit mode)
#   scripts/check-secrets.sh --all    scan every tracked file (CI mode)
#
# A match is reported as "file:line [rule]"; the secret itself is never printed.
# To silence a reviewed false positive, put the marker  secret-check:allow  on that line.
# Exit status: 0 clean, 1 findings, 2 usage or git error.
#
# Speed: starting a process is slow on Windows, so the staged files are exported once and
# searched with three recursive greps, not a few greps per file.

set -uo pipefail
export LC_ALL=C

mode=staged
case "${1:-}" in
  "") ;;
  --all) mode=all ;;
  -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
  *) echo "usage: $0 [--all]" >&2; exit 2 ;;
esac

root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "check-secrets: not inside a git repository" >&2; exit 2; }
cd "$root" || exit 2

ALLOW="secret-check:allow"

# Vendor patterns, written as "rule name::extended regex".
RULES=(
  "Google API key (AIza)::AIza[0-9A-Za-z_-]{35}"
  "Groq API key (gsk_)::gsk_[0-9A-Za-z]{20,}"
  "Tavily API key (tvly-)::tvly-[0-9A-Za-z_-]{16,}"
  "OpenAI/Anthropic-style key (sk-)::(^|[^0-9A-Za-z_-])sk-[0-9A-Za-z_-]{20,}"
  "GitHub token::(gh[pousr]_[0-9A-Za-z]{36,}|github_pat_[0-9A-Za-z_]{22,})"
  "AWS access key id::AKIA[0-9A-Z]{16}"
  "Slack token::xox[abprs]-[0-9A-Za-z-]{10,}"
  "Private key block::-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
vendor_re=""
for rule in "${RULES[@]}"; do vendor_re="${vendor_re:+$vendor_re|}(${rule#*::})"; done

# Generic "name = value" assignment with a long value, e.g. api_key = "..." or TOKEN=...
Q="[\"']"
ASSIGN_RE="(api[_-]?key|apikey|secret|token|passw(or)?d|pwd|private[_-]?key|credential)[A-Za-z0-9_]*${Q}?[[:space:]]*[:=][[:space:]]*${Q}?[A-Za-z0-9_+/=-]{24,}"
# A long unbroken run that mixes lower case, upper case and digits looks like a token.
LONG_RE='[A-Za-z0-9_=-]{40,}'
# URLs (BSE attachment links and the like) are long but harmless, so they are dropped first.
URL_RE="https?://[^[:space:]\"')>]*"
# Lockfiles and minified assets are full of long hashes; the vendor rules still apply to them.
LONG_EXCLUDES=(--exclude=package-lock.json --exclude=pnpm-lock.yaml --exclude=yarn.lock
               --exclude=poetry.lock --exclude=uv.lock --exclude='*.min.js' --exclude='*.map' --exclude='*.svg')

is_env_file() {
  case "$1" in
    .env.example) return 1 ;;
    .env|.env.*|*.env) return 0 ;;
    *) return 1 ;;
  esac
}

is_key_file() {
  case "$1" in
    *.pem|*.key|*.p12|*.pfx|*.keystore|id_rsa|id_ed25519) return 0 ;;
    *) return 1 ;;
  esac
}

found=0
checked=0
report() { echo "  BLOCKED  $1:$2  [$3]" >&2; found=$((found + 1)); }

listfile="$(mktemp)"; exportdir="$(mktemp -d)"
trap 'rm -rf "$listfile" "$exportdir"' EXIT

if [ "$mode" = all ]; then
  list_files() { git ls-files -z; }
else
  list_files() { git diff --cached --name-only --diff-filter=ACMR -z; }
fi

# 1) File-name rules. Everything else is queued for a content scan.
while IFS= read -r -d '' f; do
  checked=$((checked + 1))
  base="${f##*/}"
  if is_env_file "$base"; then report "$f" "-" "env file must never be committed"; continue; fi
  if is_key_file "$base"; then report "$f" "-" "private key or certificate file"; continue; fi
  printf '%s\0' "$f" >> "$listfile"
done < <(list_files)

# 2) Export the staged content once, and fail closed if the export is not what we expect.
if [ -s "$listfile" ]; then
  git checkout-index -f -z --stdin --prefix="$exportdir/" < "$listfile" \
    || { echo "check-secrets: could not export staged files" >&2; exit 2; }
  expected=$(tr -cd '\0' < "$listfile" | wc -c)
  actual=$(find "$exportdir" -type f | wc -l)
  if [ $((expected)) -ne $((actual)) ]; then
    echo "check-secrets: exported $((actual)) of $((expected)) files; refusing to report a clean scan" >&2
    exit 2
  fi
fi

# grep prints "path:line:content". Sets file, ln and content; returns 1 for allow-listed lines.
parse_hit() {
  local rel="${1#"$exportdir"/}"
  file="${rel%%:*}"; rel="${rel#*:}"
  ln="${rel%%:*}"; content="${rel#*:}"
  [[ $content != *"$ALLOW"* ]]
}

# 3a) Vendor-specific key formats (one combined grep, then name the rule in bash).
while IFS= read -r hit; do
  parse_hit "$hit" || continue
  for rule in "${RULES[@]}"; do
    if [[ $content =~ ${rule#*::} ]]; then report "$file" "$ln" "${rule%%::*}"; fi
  done
done < <(grep -rnIE -e "$vendor_re" "$exportdir")

# 3b) Hard-coded "secret = value" assignments. Real keys contain both letters and digits.
shopt -s nocasematch
while IFS= read -r hit; do
  parse_hit "$hit" || continue
  s="$content"
  while [[ $s =~ $ASSIGN_RE ]]; do
    m="${BASH_REMATCH[0]}"; s="${s#*"$m"}"
    val="${m#*[:=]}"; val="${val//\"/}"; val="${val//\'/}"; val="${val// /}"
    case "$val" in *[0-9]*) ;; *) continue ;; esac
    case "$val" in *[A-Za-z]*) ;; *) continue ;; esac
    report "$file" "$ln" "hard-coded secret assignment"; break
  done
done < <(grep -rniIE -e "$ASSIGN_RE" "$exportdir")
shopt -u nocasematch

# 3c) Long random-looking tokens (mixed case plus digits).
while IFS= read -r hit; do
  parse_hit "$hit" || continue
  s="$content"
  while [[ $s =~ $URL_RE ]]; do s="${s/"${BASH_REMATCH[0]}"/}"; done
  while [[ $s =~ $LONG_RE ]]; do
    tok="${BASH_REMATCH[0]}"; s="${s#*"$tok"}"
    case "$tok" in *[a-z]*) ;; *) continue ;; esac
    case "$tok" in *[A-Z]*) ;; *) continue ;; esac
    case "$tok" in *[0-9]*) ;; *) continue ;; esac
    report "$file" "$ln" "long random-looking token"; break
  done
done < <(grep -rnIE "${LONG_EXCLUDES[@]}" -e "$LONG_RE" "$exportdir")

if [ "$found" -gt 0 ]; then
  {
    echo "check-secrets: $found finding(s) in $checked file(s). Commit blocked."
    echo "  Remove the secret, and rotate it if it was ever real. Keys belong in .env (gitignored)."
    echo "  Reviewed false positive? Add the marker  secret-check:allow  to that line."
  } >&2
  exit 1
fi

echo "check-secrets: OK ($checked file(s) scanned, mode=$mode)"
