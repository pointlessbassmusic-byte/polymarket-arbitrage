#!/usr/bin/env bash
# Install the Mandel Alpaca PAPER runner (forward tests T-559 and T-560) on the Linode.
#
#   curl -fsSL https://raw.githubusercontent.com/pointlessbassmusic-byte/polymarket-arbitrage/claude/mandel-genesis/deploy/paper/install.sh | bash
#   (or: bash deploy/paper/install.sh from a checkout)
#
# What it does, as the current (non-root) user with sudo:
#   1. a separate checkout ~/mandel-paper pinned to one commit (the forward test's code must not change mid-test)
#   2. a venv with the runner's dependencies
#   3. /etc/mandel-paper.env (mode 600) holding the Alpaca PAPER keys, asked for once and never echoed
#   4. systemd timers in New York time: open 08:30, options 15:25, close 15:44, reconcile 16:20, weekdays
#   5. a nightly push of the paper journal to the branch 'paper/journal' (not the research branch: one ledger writer)
#   6. a dry run of every phase and a status read
# Real money is impossible from this install: no --live flag and no MANDEL_ALPACA_LIVE in the env file.
set -euo pipefail

REPO=${REPO:-https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git}
BRANCH=${BRANCH:-claude/mandel-genesis}
PIN=${PIN:-}                       # a commit to pin; empty = the branch head at install time
DIR=${DIR:-$HOME/mandel-paper}
STATE=${STATE:-$HOME/mandel-paper-state}
USER_NAME=$(id -un)

echo "== 1. checkout ($BRANCH) into $DIR"
if [ ! -d "$DIR/.git" ]; then git clone --branch "$BRANCH" "$REPO" "$DIR"; fi
git -C "$DIR" fetch origin "$BRANCH"
if [ -n "$PIN" ]; then git -C "$DIR" checkout --detach "$PIN"; else git -C "$DIR" checkout --detach "origin/$BRANCH"; fi
COMMIT=$(git -C "$DIR" rev-parse --short HEAD); echo "   pinned at $COMMIT"

echo "== 2. venv"
sudo apt-get install -y python3-venv >/dev/null
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q "httpx>=0.25" "tzdata"
"$DIR/.venv/bin/python" -m pytest -q "$DIR/tests/test_mandel_live.py" 2>/dev/null || "$DIR/.venv/bin/pip" install -q pytest
"$DIR/.venv/bin/python" -m pytest -q "$DIR/tests/test_mandel_live.py"

echo "== 3. keys (Alpaca PAPER account: dashboard -> Paper Trading -> API keys)"
if [ ! -f /etc/mandel-paper.env ]; then
  read -r -p "   ALPACA_API_KEY_ID (paper): " KEY
  read -r -s -p "   ALPACA_API_SECRET_KEY (paper): " SECRET; echo
  sudo install -m 600 -o "$USER_NAME" /dev/null /etc/mandel-paper.env
  printf 'ALPACA_API_KEY_ID=%s\nALPACA_API_SECRET_KEY=%s\nMANDEL_PAPER_STATE=%s\nMANDEL_PAPER_LEDGER=0\n' "$KEY" "$SECRET" "$STATE" | sudo tee /etc/mandel-paper.env >/dev/null
  unset KEY SECRET
fi
grep -q MANDEL_ALPACA_LIVE /etc/mandel-paper.env && { echo "refusing: /etc/mandel-paper.env contains MANDEL_ALPACA_LIVE"; exit 1; }
mkdir -p "$STATE"

echo "== 4. systemd units"
sudo tee /etc/systemd/system/mandel-paper@.service >/dev/null <<UNIT
[Unit]
Description=Mandel paper runner phase %i (Alpaca PAPER)
After=network-online.target
[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DIR
EnvironmentFile=/etc/mandel-paper.env
ExecStart=$DIR/.venv/bin/python -m mandel.live.runner %i
UNIT
declare -A WHEN=([open]="08:30" [options]="15:25" [close]="15:44" [reconcile]="16:20")
for phase in open options close reconcile; do
  sudo tee /etc/systemd/system/mandel-paper-$phase.timer >/dev/null <<UNIT
[Unit]
Description=Mandel paper runner: $phase
[Timer]
OnCalendar=Mon..Fri ${WHEN[$phase]}:00 America/New_York
Unit=mandel-paper@$phase.service
AccuracySec=10s
[Install]
WantedBy=timers.target
UNIT
done

echo "== 5. nightly journal push to branch paper/journal"
sudo tee /etc/systemd/system/mandel-paper-journal.service >/dev/null <<UNIT
[Unit]
Description=Push the Mandel paper journal to branch paper/journal
[Service]
Type=oneshot
User=$USER_NAME
ExecStart=/bin/bash -lc 'set -e; J=$HOME/mandel-paper-journal; [ -d \$J/.git ] || { git clone $REPO \$J; git -C \$J checkout --orphan paper/journal; git -C \$J rm -rfq . || true; }; cp $STATE/*.json* \$J/ 2>/dev/null || true; cd \$J; git add -A; git -c user.name=MandelPaper -c user.email=mandel@localhost commit -qm "paper journal \$(date -u +%%FT%%TZ)" || exit 0; git push -q origin HEAD:paper/journal'
UNIT
sudo tee /etc/systemd/system/mandel-paper-journal.timer >/dev/null <<UNIT
[Unit]
Description=Nightly paper journal push
[Timer]
OnCalendar=Mon..Fri 17:00:00 America/New_York
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
for t in open options close reconcile journal; do sudo systemctl enable --now mandel-paper-$t.timer; done

echo "== 6. dry runs and status"
set -a; . /etc/mandel-paper.env; set +a
cd "$DIR"
.venv/bin/python -m mandel.live.runner status
for phase in open options close; do .venv/bin/python -m mandel.live.runner $phase --dry-run || true; done
systemctl list-timers 'mandel-paper-*' --no-pager
echo "Installed at commit $COMMIT. Stop all orders: touch $STATE/KILL. Logs: journalctl -u 'mandel-paper@*'"
