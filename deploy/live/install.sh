#!/usr/bin/env bash
# Install the Mandel LIVE execution test of the calendar sleeve (T-744) on the Linode: REAL MONEY, MINIMUM SIZE.
#
#   curl -fsSL "https://raw.githubusercontent.com/pointlessbassmusic-byte/polymarket-arbitrage/claude/mandel-genesis/deploy/live/install.sh?v=1" | bash
#   (or: bash deploy/live/install.sh from a checkout; PIN=<commit> pins the code)
#
# What it does, as the current (non-root) user with sudo, touching nothing of the paper runner (~/mandel-paper):
#   1. a separate checkout ~/mandel-live pinned to one commit, and a venv; the CLI must import in that venv
#   2. /etc/mandel-live.env (mode 600): the Alpaca LIVE keys (key id starts with AK, never the paper PK keys), the live
#      state directory, MANDEL_LIVE_SHARES=1 and MANDEL_LIVE_MAX_LOSS_USD=40. It does NOT write MANDEL_ALPACA_LIVE.
#   3. systemd timers, New York time, weekdays: open 08:30 (opening-auction sale), close 15:40 (closing-auction buys;
#      the MOC cutoff is 15:50), reconcile 16:20, journal push 17:00 to branch live/journal. No options phase.
#   4. a read-only status and dry run of both order phases against the live account (no order can be placed: the
#      client is read-only until the switch exists)
#   5. prints the ONE line the user types to arm it. Until then every timer runs and places nothing.
# Stop: touch ~/mandel-live-state/KILL (no orders) or remove the switch line from /etc/mandel-live.env.
set -euo pipefail

REPO=${REPO:-https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git}
SSH_REPO=${SSH_REPO:-git@github.com:pointlessbassmusic-byte/polymarket-arbitrage.git}
BRANCH=${BRANCH:-claude/mandel-genesis}
PIN=${PIN:-}
DIR=${DIR:-$HOME/mandel-live}
STATE=${STATE:-$HOME/mandel-live-state}
SHARES=${SHARES:-1}
MAX_LOSS=${MAX_LOSS:-40}
USER_NAME=$(id -un)

echo "== 1. checkout ($BRANCH) into $DIR"
# An ARMED install (the switch is in the env file) never moves its code to the branch tip by accident: a re-run must
# name the commit (PIN=...) or be disarmed first. The new commit is tested before the running checkout moves to it.
if [ -f /etc/mandel-live.env ] && sudo grep -q '^MANDEL_ALPACA_LIVE=I-UNDERSTAND$' /etc/mandel-live.env && [ -z "$PIN" ]; then
  echo "refusing: this install is ARMED; re-run with PIN=<commit> to move its code, or remove the switch line first"; exit 1
fi
if [ ! -d "$DIR/.git" ]; then git clone --branch "$BRANCH" "$REPO" "$DIR"; fi
OLD=$(git -C "$DIR" rev-parse HEAD)
git -C "$DIR" fetch -q origin "$BRANCH"
TARGET=${PIN:-origin/$BRANCH}
git -C "$DIR" checkout -q --detach "$TARGET"
COMMIT=$(git -C "$DIR" rev-parse --short HEAD); echo "   pinned at $COMMIT"
sudo apt-get install -y python3-venv >/dev/null
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q "httpx>=0.25" tzdata pytest
if ! (cd "$DIR" && "$DIR/.venv/bin/python" -c "import mandel.live.runner" && "$DIR/.venv/bin/python" -m pytest -q "$DIR/tests/test_mandel_live.py"); then
  echo "   tests failed at $COMMIT: restoring the previous checkout $(git -C "$DIR" rev-parse --short "$OLD")"
  git -C "$DIR" checkout -q --detach "$OLD"; exit 1
fi

echo "== 2. keys (Alpaca LIVE account: dashboard -> Live Trading -> API keys). Never the paper keys."
ENV_OK='^ALPACA_API_KEY_ID=[A-Za-z0-9]+$'
if [ -f /etc/mandel-live.env ] && ! sudo grep -Eq "$ENV_OK" /etc/mandel-live.env; then
  echo "   /etc/mandel-live.env is malformed: asking for the keys again"; sudo rm -f /etc/mandel-live.env
fi
if [ ! -f /etc/mandel-live.env ]; then
  read -r -p "   ALPACA_API_KEY_ID (LIVE): " KEY </dev/tty
  read -r -s -p "   ALPACA_API_SECRET_KEY (LIVE): " SECRET </dev/tty; echo
  KEY=$(printf '%s' "$KEY" | tr -d '[:space:]'); SECRET=$(printf '%s' "$SECRET" | tr -d '[:space:]')
  echo "   read a key id of ${#KEY} characters and a secret of ${#SECRET} characters"
  [[ "$KEY" =~ ^[A-Za-z0-9]+$ ]] || { echo "refusing: the key id is empty or has characters other than letters and digits"; exit 1; }
  # [:graph:] not a !-~ range: in a UTF-8 locale glibc orders ranges by collation and a secret with / or + failed it (2026-11-09)
  [ -n "$SECRET" ] || { echo "refusing: the secret is empty (nothing was pasted at the hidden prompt?)"; exit 1; }
  [[ "$SECRET" =~ [^[:graph:]] ]] && { echo "refusing: the secret has a character that is not printable ASCII"; exit 1; }
  [[ "$KEY" == PK* ]] && { echo "refusing: PK... is a PAPER key id; the live test needs the live account's keys (AK...)"; exit 1; }
  if [ -f /etc/mandel-paper.env ] && sudo grep -q "ALPACA_API_KEY_ID=$KEY\$" /etc/mandel-paper.env; then
    echo "refusing: these are the paper runner's keys"; exit 1
  fi
  sudo install -m 600 -o "$USER_NAME" /dev/null /etc/mandel-live.env
  printf 'ALPACA_API_KEY_ID=%s\nALPACA_API_SECRET_KEY=%s\nMANDEL_LIVE_STATE=%s\nMANDEL_PAPER_LEDGER=0\nMANDEL_LIVE_SHARES=%s\nMANDEL_LIVE_MAX_LOSS_USD=%s\n' \
    "$KEY" "$SECRET" "$STATE" "$SHARES" "$MAX_LOSS" | sudo tee /etc/mandel-live.env >/dev/null
  unset KEY SECRET
fi
mkdir -p "$STATE"

echo "== 3. systemd units (open 08:30, close 15:40, reconcile 16:20, journal 17:00 New York; no options phase)"
sudo tee /etc/systemd/system/mandel-live@.service >/dev/null <<UNIT
[Unit]
Description=Mandel LIVE calendar sleeve (T-744) phase %i, minimum size
After=network-online.target
[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DIR
EnvironmentFile=/etc/mandel-live.env
ExecStart=$DIR/.venv/bin/python -m mandel.live.runner %i --live
UNIT
declare -A WHEN=([open]="08:30" [close]="15:40" [reconcile]="16:20")
for phase in open close reconcile; do
  sudo tee /etc/systemd/system/mandel-live-$phase.timer >/dev/null <<UNIT
[Unit]
Description=Mandel live sleeve: $phase
[Timer]
OnCalendar=Mon..Fri ${WHEN[$phase]}:00 America/New_York
Unit=mandel-live@$phase.service
AccuracySec=10s
[Install]
WantedBy=timers.target
UNIT
done
sudo tee /etc/systemd/system/mandel-live-journal.service >/dev/null <<UNIT
[Unit]
Description=Push the Mandel live journal to branch live/journal
[Service]
Type=oneshot
User=$USER_NAME
ExecStart=/bin/bash $DIR/deploy/live/push_journal.sh $STATE $REPO $SSH_REPO
UNIT
sudo tee /etc/systemd/system/mandel-live-journal.timer >/dev/null <<UNIT
[Unit]
Description=Nightly live journal push
[Timer]
OnCalendar=Mon..Fri 17:00:00 America/New_York
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload

echo "== 4. read-only status and dry runs against the LIVE account (nothing can be placed: the switch is unset here)"
set -a; . /etc/mandel-live.env; set +a
unset MANDEL_ALPACA_LIVE
cd "$DIR"
if ! .venv/bin/python -m mandel.live.runner status --live; then   # a failure here (bad keys) stops the install before any timer
  echo
  echo "   the LIVE endpoint (api.alpaca.markets) refused these keys. Common causes: keys generated on the paper dashboard"
  echo "   (paper ids start with PK, live ids with AK), a live account not yet approved/active, or a stray character"
  echo "   in the paste. The key file is removed so the next run asks again; no timer was enabled."
  sudo rm -f /etc/mandel-live.env
  exit 1
fi
for phase in open close; do .venv/bin/python -m mandel.live.runner $phase --live --dry-run || true; done

echo "== 5. timers (enabled only now that the keys and the code have been exercised)"
for t in open close reconcile journal; do sudo systemctl enable --now mandel-live-$t.timer; done
systemctl list-timers 'mandel-live-*' --no-pager
cat <<MSG

Installed at commit $COMMIT, NOT ARMED. Every timer runs; no order can be placed until you add the switch:

    echo MANDEL_ALPACA_LIVE=I-UNDERSTAND | sudo tee -a /etc/mandel-live.env

Before you do: the live account should hold about \$1,000 cash (the sleeve uses at most ~\$400: $SHARES share of QQQM
every night, $SHARES of SPYM when IBS or the turn of the month fires; the rest is a settlement buffer), as a margin
account so overnight round trips do not trip good-faith violations; nothing is ever borrowed. The loss halt is
\$$MAX_LOSS marked (realised plus unrealised): it stops new buys, held shares still sell by their rule. Disarm: remove that line, or touch $STATE/KILL. Logs: journalctl -u 'mandel-live@*'
MSG
