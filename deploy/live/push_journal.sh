#!/usr/bin/env bash
# Push the live runner's journal (fills, decisions, arming rows, halts; no keys) to branch live/journal.
# Usage: push_journal.sh <state dir> <https repo> <ssh repo>
set -euo pipefail
STATE=$1; REPO=$2; SSH_REPO=$3
J=$HOME/mandel-live-journal
R=$REPO; [ -f "$HOME/.ssh/mandel_journal" ] && R=$SSH_REPO
if [ ! -d "$J/.git" ]; then
  git clone -q "$R" "$J"; git -C "$J" checkout -q --orphan live/journal; git -C "$J" rm -rfq . || true
fi
git -C "$J" remote set-url origin "$R"
cp "$STATE"/*.json* "$J"/ 2>/dev/null || true
[ -f "$STATE/HALT" ] && cp "$STATE/HALT" "$J"/HALT || rm -f "$J"/HALT
cd "$J"
git add -A
git -c user.name=MandelLive -c user.email=mandel@localhost commit -qm "live journal $(date -u +%FT%TZ)" || exit 0
git push -q origin HEAD:live/journal
