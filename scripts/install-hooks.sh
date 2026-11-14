#!/usr/bin/env bash
# Installs the git pre-commit hook that runs scripts/check-secrets.sh. Safe to re-run.
# Hooks are not copied by "git clone", so run this once in every fresh clone.

set -euo pipefail

root="$(git rev-parse --show-toplevel)"
cd "$root"

hook="$(git rev-parse --git-path hooks/pre-commit)"
marker="finn-secret-check-hook"

mkdir -p "$(dirname "$hook")"
if [ -f "$hook" ] && ! grep -q "$marker" "$hook"; then
  cp "$hook" "$hook.bak"
  echo "install-hooks: kept your existing pre-commit hook as $hook.bak"
fi

cat > "$hook" <<'EOF'
#!/usr/bin/env bash
# finn-secret-check-hook (installed by scripts/install-hooks.sh; re-run that instead of editing)
root="$(git rev-parse --show-toplevel)"
exec bash "$root/scripts/check-secrets.sh"
EOF
chmod +x "$hook"

echo "install-hooks: pre-commit hook installed at $hook"
