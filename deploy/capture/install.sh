#!/usr/bin/env bash
# Install Mandel's Linode data captures, the HMM shadow recorder (T-565, T-566) and the widened asset sleeves
# (T-567 pre-holiday IWM, T-568 GLD/TLT/USO put spreads) next to the paper runner.
#
#   curl -fsSL "https://raw.githubusercontent.com/pointlessbassmusic-byte/polymarket-arbitrage/claude/mandel-genesis/deploy/capture/install.sh?v=1" | bash
#
# What it does (as root or a sudo user; touches nothing of the paper runner in ~/mandel-paper):
#   1. a separate checkout ~/mandel-capture pinned to one commit, and a venv (httpx, numpy, tzdata, pytest)
#   2. data outside the checkout: ~/mandel-capture-data/{archive,state,capture,wide}; the archive index is seeded from
#      the checkout so the in-git histories resolve; raw Cboe chains stay on this box
#   3. /etc/mandel-wide.env (mode 600): Alpaca PAPER keys for the widened sleeves and the shadow's market data.
#      A second Alpaca paper account is recommended; press Enter at the prompt to reuse the paper runner's keys.
#   4. systemd timers, New York time:
#        capture daily 18:30 Mon-Fri, weekly Sun 07:30, shadow 16:35 Mon-Fri,
#        wide close 12:46 and 15:46 (acts only 4-16 minutes before that session's close), options 15:27, reconcile 16:22,
#        status push 19:30 Mon-Fri to branch capture/status (summaries, scores, shadow and wide journals; no raw data)
#   5. dry runs of every phase
# Real money is impossible from this install: no --live flag and no MANDEL_ALPACA_LIVE anywhere.
set -euo pipefail

REPO=${REPO:-https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git}
SSH_REPO=${SSH_REPO:-git@github.com:pointlessbassmusic-byte/polymarket-arbitrage.git}
BRANCH=${BRANCH:-claude/mandel-genesis}
PIN=${PIN:-}
DIR=${DIR:-$HOME/mandel-capture}
DATA=${DATA:-$HOME/mandel-capture-data}
CAPITAL=${CAPITAL:-5000}
USER_NAME=$(id -un)
SUDO=$([ "$(id -u)" = 0 ] && echo "" || echo sudo)

echo "== 1. checkout ($BRANCH) into $DIR"
if [ ! -d "$DIR/.git" ]; then git clone --branch "$BRANCH" "$REPO" "$DIR"; fi
git -C "$DIR" fetch -q origin "$BRANCH"
if [ -n "$PIN" ]; then git -C "$DIR" checkout -q --detach "$PIN"; else git -C "$DIR" checkout -q --detach "origin/$BRANCH"; fi
COMMIT=$(git -C "$DIR" rev-parse --short HEAD); echo "   pinned at $COMMIT"
$SUDO apt-get install -y python3-venv >/dev/null
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q "httpx>=0.25" numpy tzdata pytest
"$DIR/.venv/bin/python" -m pytest -q "$DIR/tests/test_mandel_wide_shadow_capture.py" "$DIR/tests/test_mandel_batch8_markov.py"

echo "== 2. data directories in $DATA"
mkdir -p "$DATA/archive" "$DATA/state" "$DATA/capture" "$DATA/wide"
[ -f "$DATA/archive/INDEX.json" ] || cp "$DIR/mandel/archive/INDEX.json" "$DATA/archive/INDEX.json"

echo "== 3. keys for the widened sleeves (Alpaca PAPER)"
# /etc/mandel-wide.env holds this install's own keys, or only a REUSE line: the units then read the paper runner's
# validated /etc/mandel-paper.env (loaded first; a key in mandel-wide.env overrides it).
if [ -f /etc/mandel-wide.env ] && ! $SUDO grep -Eq '^(ALPACA_API_KEY_ID=[A-Za-z0-9]+|REUSE_PAPER_KEYS=1)$' /etc/mandel-wide.env; then
  echo "   /etc/mandel-wide.env is malformed: asking again"; $SUDO rm -f /etc/mandel-wide.env
fi
if [ ! -f /etc/mandel-wide.env ]; then
  echo "   A second Alpaca paper account keeps these sleeves' cash and P&L apart from the calendar sleeve."
  read -r -p "   ALPACA_API_KEY_ID for the widened sleeves (Enter = reuse the paper runner's keys): " KEY </dev/tty
  KEY=$(printf '%s' "$KEY" | tr -d '[:space:]')
  $SUDO install -m 600 -o "$USER_NAME" /dev/null /etc/mandel-wide.env
  if [ -z "$KEY" ]; then
    [ -f /etc/mandel-paper.env ] || { $SUDO rm -f /etc/mandel-wide.env; echo "refusing: no key given and no /etc/mandel-paper.env to reuse"; exit 1; }
    echo "REUSE_PAPER_KEYS=1" | $SUDO tee /etc/mandel-wide.env >/dev/null
    echo "   reusing the paper runner's keys (one shared paper account)"
  else
    read -r -s -p "   ALPACA_API_SECRET_KEY: " SECRET </dev/tty; echo
    SECRET=$(printf '%s' "$SECRET" | tr -d '[:space:]')
    echo "   read a key id of ${#KEY} characters and a secret of ${#SECRET} characters"
    [[ "$KEY" =~ ^[A-Za-z0-9]+$ ]] || { $SUDO rm -f /etc/mandel-wide.env; echo "refusing: the key id has unexpected characters"; exit 1; }
    [ -n "$SECRET" ] || { $SUDO rm -f /etc/mandel-wide.env; echo "refusing: the secret is empty"; exit 1; }
    printf 'ALPACA_API_KEY_ID=%s\nALPACA_API_SECRET_KEY=%s\n' "$KEY" "$SECRET" | $SUDO tee /etc/mandel-wide.env >/dev/null
  fi
  unset KEY SECRET
fi
[ -f /etc/mandel-paper.env ] || $SUDO install -m 600 -o "$USER_NAME" /dev/null /etc/mandel-paper.env
$SUDO grep -q MANDEL_ALPACA_LIVE /etc/mandel-wide.env && { echo "refusing: /etc/mandel-wide.env contains MANDEL_ALPACA_LIVE"; exit 1; }
$SUDO tee /etc/mandel-capture.env >/dev/null <<ENV
MANDEL_ARCHIVE_ROOT=$DATA/archive
MANDEL_DATA_ROOT=$DATA/state
MANDEL_CAPTURE_OUT=$DATA/capture
MANDEL_WIDE_STATE=$DATA/wide
MANDEL_WIDE_CAPITAL=$CAPITAL
ENV

echo "== 4. systemd units"
unit() {  # name, command, description
  $SUDO tee "/etc/systemd/system/$1.service" >/dev/null <<UNIT
[Unit]
Description=$3
After=network-online.target
[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DIR
EnvironmentFile=/etc/mandel-capture.env
EnvironmentFile=/etc/mandel-paper.env
EnvironmentFile=/etc/mandel-wide.env
ExecStart=$2
TimeoutStartSec=3h
UNIT
}
timer() {  # name, OnCalendar (one or more, ';'-separated)
  { echo "[Unit]"; echo "Description=$1"; echo "[Timer]"
    IFS=';' read -ra CALS <<< "$2"; for c in "${CALS[@]}"; do echo "OnCalendar=$c America/New_York"; done
    echo "Unit=$1.service"; echo "AccuracySec=10s"; echo "Persistent=false"; echo "[Install]"; echo "WantedBy=timers.target"
  } | $SUDO tee "/etc/systemd/system/$1.timer" >/dev/null
}
PY="$DIR/.venv/bin/python"
unit mandel-capture-daily "/bin/bash -lc '$PY -m mandel.live.capture daily; $PY -m mandel.live.capture score'" "Mandel daily captures"
unit mandel-capture-weekly "$PY -m mandel.live.capture weekly" "Mandel weekly history refresh"
unit mandel-shadow "$PY -m mandel.live.shadow record" "Mandel HMM shadow record (T-565, T-566)"
unit mandel-wide-close "$PY -m mandel.live.wide close" "Mandel widened sleeves: closing auction (T-567)"
unit mandel-wide-options "$PY -m mandel.live.wide options" "Mandel widened sleeves: put spreads (T-568)"
unit mandel-wide-reconcile "$PY -m mandel.live.wide reconcile" "Mandel widened sleeves: reconcile fills"
unit mandel-capture-push "/bin/bash $DIR/deploy/capture/push_status.sh $DATA $REPO $SSH_REPO" "Push capture status (no raw data) to branch capture/status"
timer mandel-capture-daily "Mon..Fri 18:30:00"
timer mandel-capture-weekly "Sun 07:30:00"
timer mandel-shadow "Mon..Fri 16:35:00"
timer mandel-wide-close "Mon..Fri 12:46:00;Mon..Fri 15:46:00"
timer mandel-wide-options "Mon..Fri 15:27:00"
timer mandel-wide-reconcile "Mon..Fri 16:22:00"
timer mandel-capture-push "Mon..Fri 19:30:00"
$SUDO systemctl daemon-reload
for t in capture-daily capture-weekly shadow wide-close wide-options wide-reconcile capture-push; do
  $SUDO systemctl enable --now "mandel-$t.timer" >/dev/null
done

echo "== 5. dry runs"
set -a; . /etc/mandel-capture.env; . <($SUDO cat /etc/mandel-paper.env); . <($SUDO cat /etc/mandel-wide.env); set +a
export MANDEL_PAPER_STATE=   # the paper runner's state path is not this install's
cd "$DIR"
"$PY" -m mandel.live.wide status
"$PY" -m mandel.live.wide close --dry-run || true
"$PY" -m mandel.live.wide options --dry-run || true
"$PY" -m mandel.live.shadow record --dry-run || true
"$PY" -m mandel.live.capture status | head -20 || true
systemctl list-timers 'mandel-*' --no-pager
echo "Installed at commit $COMMIT. The first capture runs at 18:30 ET; to run it now: sudo systemctl start mandel-capture-daily.service"
echo "Stop the widened sleeves' orders: touch $DATA/wide/KILL. Logs: journalctl -u 'mandel-*' -n 50"
