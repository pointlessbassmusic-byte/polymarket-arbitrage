#!/usr/bin/env bash
# Push data-free capture summaries to branch capture/status: status.json, scores.json, shadow.jsonl, the widened
# sleeves' journal. Uses the deploy key ~/.ssh/mandel_journal when present (see mandel/OPERATIONS.md), else HTTPS,
# which fails quietly without credentials. Usage: push_status.sh <data dir> <https repo> <ssh repo>
set -euo pipefail
DATA=$1; REPO=$2; SSH_REPO=$3
J=$HOME/mandel-capture-push
R=$REPO; [ -f "$HOME/.ssh/mandel_journal" ] && R=$SSH_REPO
if [ ! -d "$J/.git" ]; then
  git clone -q "$R" "$J"; git -C "$J" checkout -q --orphan capture/status; git -C "$J" rm -rfq . || true
fi
git -C "$J" remote set-url origin "$R"
cp "$DATA"/capture/*.json* "$J"/ 2>/dev/null || true
cp "$DATA"/wide/journal.jsonl "$J"/wide-journal.jsonl 2>/dev/null || true
cd "$J"
git add -A
git -c user.name=MandelCapture -c user.email=mandel@localhost commit -qm "capture status $(date -u +%FT%TZ)" || exit 0
git push -q origin HEAD:capture/status
