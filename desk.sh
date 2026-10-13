#!/usr/bin/env bash
# Day-to-day control of the desk from any terminal, a phone's SSH app
# included: short commands, prompts instead of file editing, nothing to
# remember. Run it from the repo directory on the server.
#
#   ./desk.sh status      what is running, the dashboard URL, preflight, research counts
#   ./desk.sh keys        add or replace API keys in .env (prompts; a pasted PEM is fine)
#   ./desk.sh arm         perp.live: true + CRYPTOBOT_ARM_LIVE=yes, then restart (real money)
#   ./desk.sh disarm      back to paper, then restart
#   ./desk.sh update      git pull, rebuild, restart
#   ./desk.sh logs        follow the desk log
#   ./desk.sh tunnel      how to reach the dashboard from this phone or laptop
#   ./desk.sh remote      one private HTTPS address for the dashboard (Tailscale), phone and desktop alike
#   ./desk.sh url         the dashboard URL(s) to bookmark
#   ./desk.sh digest      today's digest, as the webhook would get it
#
# `keys`, `arm` and `disarm` edit files only; the restart is skipped when
# Docker is not running (so they also work before the first deploy).
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=.env
dash_port() { local p; p="$(get_env CRYPTOBOT_DASH_PORT)"; echo "${p:-8080}"; }
CFG=cryptobot_config.yaml

dc() {
  if docker info >/dev/null 2>&1; then docker compose "$@"; else sudo docker compose "$@"; fi
}
have_docker() { command -v docker >/dev/null 2>&1 && (docker info >/dev/null 2>&1 || sudo -n docker info >/dev/null 2>&1); }

ensure_env() {
  if [ ! -f "$ENV_FILE" ]; then
    TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -hex 32)"
    sed "s/^CRYPTOBOT_DASH_TOKEN=.*/CRYPTOBOT_DASH_TOKEN=$TOKEN/" .env.example > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "wrote $ENV_FILE with a fresh dashboard token"
  fi
}

# set_env KEY VALUE: replace the line or append it; the value is written verbatim.
set_env() {
  local key="$1" val="$2" tmp
  ensure_env
  tmp="$(mktemp)"
  if grep -q "^${key}=" "$ENV_FILE"; then
    # the value goes through ENVIRON, not -v: awk -v would turn a literal \n into a newline
    K="$key" V="$val" awk 'BEGIN{FS="="} $1==ENVIRON["K"] {print ENVIRON["K"]"="ENVIRON["V"]; next} {print}' "$ENV_FILE" > "$tmp"
  else
    cat "$ENV_FILE" > "$tmp"; printf '%s=%s\n' "$key" "$val" >> "$tmp"
  fi
  cat "$tmp" > "$ENV_FILE"; rm -f "$tmp"; chmod 600 "$ENV_FILE"
}

get_env() { grep "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true; }

# prompt VAR "label" [secret]: read one value; empty keeps what is there.
prompt() {
  local key="$1" label="$2" secret="${3:-}" cur val
  cur="$(get_env "$key")"
  if [ -n "$cur" ]; then label="$label [set, enter keeps it]"; else label="$label [blank to skip]"; fi
  if [ -n "$secret" ]; then read -r -s -p "$label: " val; echo; else read -r -p "$label: " val; fi
  if [ -n "$val" ]; then set_env "$key" "$val"; echo "  $key saved"; fi
}

# prompt_pem KEY "label": a file path, a one-line PEM with literal \n, or a pasted multi-line PEM.
prompt_pem() {
  local key="$1" label="$2" first lines line
  echo "$label: paste the PEM (ends with END ... KEY), or type a file path, or enter to skip"
  read -r first
  [ -z "$first" ] && return 0
  if [ -f "$first" ]; then
    set_env "$key" "$(awk 'BEGIN{ORS="\\n"} {print}' "$first")"
    echo "  $key saved from $first"; return 0
  fi
  if [[ "$first" == *'\n'* ]]; then set_env "$key" "$first"; echo "  $key saved"; return 0; fi
  lines="$first"
  if [[ "$first" != *"END"* ]]; then
    while IFS= read -r line; do
      lines="$lines\\n$line"
      [[ "$line" == *"END"* ]] && break
    done
  fi
  set_env "$key" "$lines"
  echo "  $key saved"
}

cmd_keys() {
  ensure_env
  echo "Keys go into $ENV_FILE (mode 600). Never a key with withdrawal permission."
  echo
  echo "Kalshi (the live venue): key id, then the private key PEM."
  prompt CRYPTOBOT_KALSHI_KEY_ID "Kalshi key id"
  prompt_pem CRYPTOBOT_KALSHI_KEY_PEM "Kalshi private key"
  echo
  echo "Alpaca (stocks, paper or live keys):"
  prompt CRYPTOBOT_ALPACA_KEY_ID "Alpaca key id"
  prompt CRYPTOBOT_ALPACA_SECRET_KEY "Alpaca secret" secret
  echo
  echo "Optional:"
  prompt CRYPTOBOT_ALERT_WEBHOOK "Discord/Slack webhook URL"
  prompt CRYPTOBOT_KRAKEN_KEY "Kraken API key"
  prompt CRYPTOBOT_KRAKEN_SECRET "Kraken API secret" secret
  prompt CRYPTOBOT_TASTY_CLIENT_SECRET "tastytrade client secret" secret
  prompt CRYPTOBOT_TASTY_REFRESH_TOKEN "tastytrade refresh token" secret
  echo
  restart_if_running
  echo "next: ./desk.sh status"
}

set_live() {
  local flag="$1" tmp
  tmp="$(mktemp)"
  # only the perp: block's own `live:` line (the first `  live:` after `^perp:`)
  awk -v f="$flag" '
    /^perp:/ {inperp=1}
    inperp && /^  live:/ && !done {sub(/live: *(true|false)/, "live: " f); done=1}
    /^[a-z]/ && !/^perp:/ {inperp=0}
    {print}' "$CFG" > "$tmp"
  cat "$tmp" > "$CFG"; rm -f "$tmp"
}

cmd_arm() {
  ensure_env
  if [ -z "$(get_env CRYPTOBOT_KALSHI_KEY_ID)" ] || [ -z "$(get_env CRYPTOBOT_KALSHI_KEY_PEM)" ]; then
    echo "no Kalshi key in $ENV_FILE yet: run ./desk.sh keys first"; exit 1
  fi
  set_live true
  set_env CRYPTOBOT_ARM_LIVE yes
  echo "armed: perp.live: true, CRYPTOBOT_ARM_LIVE=yes. Real orders go out once preflight is all [ok]."
  restart_if_running
  echo "next: ./desk.sh status (preflight must be all [ok]; the dashboard's real toggle is then unlocked)"
}

cmd_disarm() {
  ensure_env
  set_live false
  set_env CRYPTOBOT_ARM_LIVE ""
  echo "disarmed: paper trading only"
  restart_if_running
}

restart_if_running() {
  if have_docker && dc ps --status running 2>/dev/null | grep -q desk; then
    echo "restarting the desk…"; dc up -d --force-recreate >/dev/null
  else
    echo "(desk not running; ./deploy.sh starts it)"
  fi
}

cmd_status() {
  ensure_env
  local token ip
  token="$(get_env CRYPTOBOT_DASH_TOKEN)"
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if have_docker; then
    echo "containers:"; dc ps 2>/dev/null | sed 's/^/  /'
  else
    echo "docker is not installed or not running: ./deploy.sh"
  fi
  echo
  echo "armed: perp.live=$(grep -A40 '^perp:' "$CFG" | grep -m1 '^  live:' | awk '{print $2}'), CRYPTOBOT_ARM_LIVE=$(get_env CRYPTOBOT_ARM_LIVE | sed 's/^$/(blank)/')"
  echo "keys: kalshi=$([ -n "$(get_env CRYPTOBOT_KALSHI_KEY_ID)" ] && echo yes || echo no) alpaca=$([ -n "$(get_env CRYPTOBOT_ALPACA_KEY_ID)" ] && echo yes || echo no) webhook=$([ -n "$(get_env CRYPTOBOT_ALERT_WEBHOOK)" ] && echo yes || echo no)"
  cmd_url | sed 's/^/dashboard /'
  echo
  if have_docker && dc ps --status running 2>/dev/null | grep -q desk; then
    echo "preflight:"; dc run --rm desk python -m cryptobot.desk --preflight 2>/dev/null | sed 's/^/  /'
    echo
    echo "research data:"; dc run --rm desk python -m cryptobot.vrp_collect --state /data --report 2>/dev/null | head -4 | sed 's/^/  /'
  fi
}

cmd_update() {
  git pull --ff-only
  if have_docker; then dc build >/dev/null && dc up -d && echo "rebuilt and restarted"; else echo "pulled; ./deploy.sh to start"; fi
}

tailscale_name() {
  command -v tailscale >/dev/null 2>&1 || return 0
  tailscale status --json 2>/dev/null | python3 -c 'import json,sys
d=json.load(sys.stdin); print((d.get("Self") or {}).get("DNSName","").rstrip("."))' 2>/dev/null || true
}

cmd_url() {
  ensure_env
  local token name
  token="$(get_env CRYPTOBOT_DASH_TOKEN)"
  name="$(get_env CRYPTOBOT_DASH_HOSTS | cut -d, -f1)"
  echo "through an SSH tunnel (./desk.sh tunnel):  http://localhost:$(dash_port)/?t=$token"
  if [ -n "$name" ]; then
    echo "from any device on your tailnet:            https://$name/?t=$token"
  else
    echo "(./desk.sh remote gives one HTTPS address that works from the phone and the desktop)"
  fi
}

cmd_remote() {
  # Tailscale Serve: the dashboard stays on the server's localhost; Tailscale
  # proxies it to https://<server>.<tailnet>.ts.net for devices signed into
  # your tailnet only. No port is opened to the internet.
  ensure_env
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "installing tailscale…"
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  if [ -z "$(tailscale_name)" ]; then
    echo "sign this server into your tailnet (a login link prints once; open it on any device):"
    sudo tailscale up
  fi
  local name
  name="$(tailscale_name)"
  if [ -z "$name" ]; then
    echo "tailscale is not signed in yet; run ./desk.sh remote again afterwards"; exit 1
  fi
  set_env CRYPTOBOT_DASH_HOSTS "$name"
  sudo tailscale serve --bg "$(dash_port)" >/dev/null 2>&1 || sudo tailscale serve --bg "http://127.0.0.1:$(dash_port)" >/dev/null
  restart_if_running
  echo "install Tailscale on the phone and the desktop, sign in with the same account, then bookmark:"
  echo "  https://$name/?t=$(get_env CRYPTOBOT_DASH_TOKEN)"
}

cmd_tunnel() {
  local token ip
  token="$(get_env CRYPTOBOT_DASH_TOKEN)"
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  cat <<EOF
The dashboard listens on the server's localhost only. Reach it through SSH:

  laptop:   ssh -L 8080:localhost:$(dash_port) $USER@$ip
  Termius:  open the host > Port Forwarding > Local: port 8080 to localhost:$(dash_port),
            connect, then open the URL below in the phone's browser

  http://localhost:8080/?t=$token
EOF
}

case "${1:-}" in
  status) cmd_status ;;
  keys) cmd_keys ;;
  arm) cmd_arm ;;
  disarm) cmd_disarm ;;
  update) cmd_update ;;
  logs) dc logs -f --tail 100 ;;
  tunnel) cmd_tunnel ;;
  remote) cmd_remote ;;
  url) cmd_url ;;
  digest) dc run --rm desk python -m cryptobot.desk --digest --state-dir /data ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
