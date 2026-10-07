#!/usr/bin/env sh
# Refuse to commit media or secrets (the LEARNINGS rule: sources and notes only).
set -e
HOOK=.git/hooks/pre-commit
cat > "$HOOK" <<'H'
#!/usr/bin/env sh
if git diff --cached --name-only | grep -E '\.(mp4|mov|wav|mp3|m4a)$|^secrets/|token.*\.json$|client_secret' >/dev/null; then
  echo "pre-commit: refusing to commit media or secrets" >&2; exit 1
fi
if git diff --cached -U0 | grep -E '^\+.*(sk-ant-[A-Za-z0-9_-]{20,}|sk_[0-9a-f]{20,}|xi-api-key: *[A-Za-z0-9])' >/dev/null; then
  echo "pre-commit: an API key is in the diff" >&2; exit 1
fi
H
chmod +x "$HOOK"
echo "installed $HOOK"
