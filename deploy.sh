#!/usr/bin/env bash
# One-shot setup for an always-on Linux server (a Linode, Ubuntu/Debian).
# Installs Docker if missing, writes .env with a random dashboard token,
# builds the history seed, starts the desk in PAPER mode, and prints the
# dashboard URL. Safe to re-run: it never overwrites an existing .env.
#
#   git clone <this repo> && cd polymarket-arbitrage && ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "installing docker…"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi
DC="docker compose"
# `docker compose version` never talks to the daemon; probe it, since the
# docker group added above is not effective in this shell yet.
docker info >/dev/null 2>&1 || DC="sudo docker compose"

if [ ! -f .env ]; then
  TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -hex 32)"
  sed "s/^CRYPTOBOT_DASH_TOKEN=.*/CRYPTOBOT_DASH_TOKEN=$TOKEN/" .env.example > .env
  chmod 600 .env
  echo "wrote .env (paper mode; live keys blank)"
fi

mkdir -p state
$DC build
if [ ! -f state/hl_daily_us3.pkl ]; then
  echo "building history seed from Hyperliquid's public API (no account)…"
  $DC run --rm desk python -m cryptobot.data.coinbase_futures --seed /data/hl_daily_us3.pkl
fi
$DC up -d

TOKEN="$(grep '^CRYPTOBOT_DASH_TOKEN=' .env | cut -d= -f2-)"
echo
echo "running. From your laptop:"
echo "  ssh -L 8080:localhost:8080 $USER@$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "then open  http://localhost:8080/?t=$TOKEN"
echo
echo "logs:       $DC logs -f"
echo "preflight:  $DC run --rm desk python -m cryptobot.desk --preflight"
