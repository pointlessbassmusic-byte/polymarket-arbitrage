#!/usr/bin/env bash
# Push the paper runner's journal and spread state to branch paper/journal (deploy key ~/.ssh/mandel_journal when
# present, else HTTPS). Usage: push_journal.sh <state dir> <https repo> <ssh repo>
set -euo pipefail
STATE=$1; REPO=$2; SSH_REPO=$3
J=$HOME/mandel-paper-journal
R=$REPO; [ -f "$HOME/.ssh/mandel_journal" ] && R=$SSH_REPO
if [ ! -d "$J/.git" ]; then
  git clone -q "$R" "$J"; git -C "$J" checkout -q --orphan paper/journal; git -C "$J" rm -rfq . || true
fi
git -C "$J" remote set-url origin "$R"
cp "$STATE"/*.json* "$J"/ 2>/dev/null || true
cd "$J"
git add -A
git -c user.name=MandelPaper -c user.email=mandel@localhost commit -qm "paper journal $(date -u +%FT%TZ)" || exit 0
git push -q origin HEAD:paper/journal
