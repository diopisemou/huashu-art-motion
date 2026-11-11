#!/usr/bin/env bash
# Prepare a Claude Code cloud container for the shorts pipeline. Run it ONCE at the START of a run, before
# `shorts next`: it overwrites the working copy's source and state files with the branch's versions.
# Idempotent. Prints a status block at the end. Usage:
#   bash /home/user/sp-branch/shorts-pipeline/scripts/cloud_setup.sh
# (first time, when /home/user/sp-branch does not exist yet:
#   git -C /home/user/huashu-art-motion fetch origin "+refs/heads/shorts-pipeline:refs/remotes/origin/shorts-pipeline"
#   git -C /home/user/huashu-art-motion worktree add --detach /home/user/sp-branch origin/shorts-pipeline)
set -euo pipefail
ENGINE=${ENGINE:-/home/user/huashu-art-motion}   # checkout of the repository
BRANCH_WT=${BRANCH_WT:-/home/user/sp-branch}     # worktree of branch shorts-pipeline: pipeline source + patched engine
WORK=${WORK:-/home/user/shorts-pipeline}         # working copy the builds run in (out/, .venv, plan.json live here)
export SSL_CERT_FILE=${SSL_CERT_FILE:-/root/.ccr/ca-bundle.crt}

echo "== 1. branch worktree"
git -C "$ENGINE" fetch -q origin "+refs/heads/shorts-pipeline:refs/remotes/origin/shorts-pipeline"
if [ ! -d "$BRANCH_WT" ]; then
  git -C "$ENGINE" worktree add -q --detach "$BRANCH_WT" origin/shorts-pipeline
else
  git -C "$BRANCH_WT" checkout -q --detach origin/shorts-pipeline
fi
echo "branch at $(git -C "$BRANCH_WT" log --oneline -1)"

echo "== 2. working copy (source and state from the branch; out/ and .venv are kept)"
mkdir -p "$WORK"
cp -r "$BRANCH_WT/shorts-pipeline/." "$WORK/"

echo "== 3. python environment"
cd "$WORK"
uv sync -q 2>&1 | grep -v UV_NATIVE_TLS || true

echo "== 4. Playwright Chromium"
# The image ships one Chromium build under /opt/pw-browsers; the venv's playwright may look for another build
# number. Never download a browser here: link the path playwright asks for to the binary that is installed.
ok=""
for _ in 1 2 3; do
  out=$(uv run python - 2>&1 <<'PY' || true
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); print("CHROMIUM_OK", b.version); b.close()
PY
)
  if grep -q CHROMIUM_OK <<<"$out"; then ok=$(grep CHROMIUM_OK <<<"$out"); break; fi
  want=$(grep -o "Executable doesn't exist at [^ ]*" <<<"$out" | head -1 | sed "s/.*exist at //" || true)
  if [ -z "$want" ]; then echo "chromium launch failed for another reason:"; tail -5 <<<"$out"; exit 1; fi
  bdir=$(dirname "$(dirname "$want")"); base=$(basename "$bdir"); root=$(dirname "$bdir"); kind=${base%-*}
  case "$kind" in
    chromium_headless_shell) have=$( (ls "$root"/chromium_headless_shell-*/*/chrome-headless-shell "$root"/chromium_headless_shell-*/*/headless_shell 2>/dev/null || true) | grep -v "/$base/" | head -1 || true);;
    chromium)                have=$( (ls "$root"/chromium-*/*/chrome 2>/dev/null || true) | grep -v "/$base/" | head -1 || true);;
    *) have="";;
  esac
  if [ -z "$have" ]; then echo "no installed browser to link for $want"; exit 1; fi
  mkdir -p "$(dirname "$want")"; ln -sf "$have" "$want"; touch "$bdir/INSTALLATION_COMPLETE"
  echo "linked $want -> $have"
done
[ -n "$ok" ] || { echo "chromium still does not launch"; exit 1; }
echo "$ok"

echo "== 5. status"
python3 - <<'PY'
import json, os, ssl, datetime, urllib.request, urllib.error
for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "YT_TOKEN_JSON", "POSTIZ_API_KEY"):
    print(f"{k}: {'set' if os.environ.get(k) else 'MISSING'}")
raw = os.environ.get("YT_TOKEN_JSON")
if raw:
    try:
        sc = json.loads(raw).get("scopes") or []
        ok = {s.rstrip("/").rsplit("/", 1)[-1] for s in sc} & {"yt-analytics.readonly", "yt-analytics-monetary.readonly", "youtube.readonly", "youtube", "youtubepartner"}
        print("youtube retention (Analytics API):", "yes" if ok else "NO (token has no scope the Analytics API accepts)")
    except Exception:
        print("YT_TOKEN_JSON is not valid JSON")
key = os.environ.get("POSTIZ_API_KEY")
if key:
    try:
        ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))
        req = urllib.request.Request("https://api.postiz.com/public/v1/integrations", headers={"Authorization": key})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            print("postiz api: OK,", len(json.loads(r.read())), "integrations")
    except urllib.error.HTTPError as e:
        print("postiz api:", e.code, e.read()[:120].decode("utf-8", "replace"), "-> skip cross-posting")
    except Exception as e:
        print("postiz api: unreachable", type(e).__name__, "-> skip cross-posting")
d = json.load(open("state/history.json"))
today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
built = [e.get("video_id") for e in d if e["date"].startswith(today)]
print(f"history: {len(d)} entries; built today (UTC {today}): {len(built)} {built}")
print("topics left:", sum(1 for l in open("topics.yaml") if l.startswith("- ")))
PY
echo "next: cd $WORK && export HUASHU_DIR=$BRANCH_WT SSL_CERT_FILE=$SSL_CERT_FILE"
