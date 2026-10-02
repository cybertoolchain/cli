#!/bin/sh
# Install the secret-scan pre-commit hook by COPYING it into .git/hooks (untracked), so checking out
# someone else's branch cannot change the code that runs on your next commit. Idempotent; re-run it
# whenever .githooks/pre-commit changes. Also unsets the old core.hooksPath=.githooks setup.
set -e
root=$(git rev-parse --show-toplevel)
if [ "$(git config --get core.hooksPath 2>/dev/null || true)" = ".githooks" ]; then
  git config --unset core.hooksPath
fi
hooks=$(git rev-parse --git-path hooks)
dest="$hooks/pre-commit"
mkdir -p "$hooks"
if [ -e "$dest" ] && ! cmp -s "$root/.githooks/pre-commit" "$dest" && ! grep -q 'secret-scan hook: gitleaks' "$dest"; then
  echo "install.sh: $dest already exists and is not this hook - not overwriting" >&2
  exit 1
fi
cp "$root/.githooks/pre-commit" "$dest"
chmod +x "$dest"
echo "installed secret-scan pre-commit hook -> $dest"
