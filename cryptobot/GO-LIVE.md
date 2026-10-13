# Tonight's list: real money on Kalshi tomorrow

Everything is typed into Termius. Expect 30–45 minutes if the server
exists, plus however long Kalshi takes to enable perpetuals. Items are
in order; each one is needed for the next.

## 1. A server (skip if you already have one)

An always-on Linux box with SSH: a Linode or DigitalOcean Ubuntu
droplet at the smallest size is enough. Note its IP, add it to
Termius, log in once.

## 2. Put the desk on it (10 minutes)

In the GitHub app: Settings > Developer settings > Fine-grained tokens
> new token, **read-only Contents** on this repository. Copy it. Then:

```bash
git clone -b claude/crypto-arbitrage-volatility-bot-qic8gv https://TOKEN@github.com/pointlessbassmusic-byte/polymarket-arbitrage.git
cd polymarket-arbitrage
git remote set-url origin https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git
./deploy.sh
```

`deploy.sh` installs Docker, writes `.env` with a random dashboard
token, builds the history seed and starts the desk in paper mode. The
daily collectors start with it. It ends by printing the dashboard URL.

## 3. Kalshi account (the part only you can do)

In the Kalshi app or kalshi.com, all from the phone:

1. Identity verified (if the account is new, this is the slow step).
2. **Perpetuals enabled.** Kalshi rolls perps access out per member;
   the preflight asks the API whether it is on. If the app shows no
   perpetuals section, request access from Kalshi support tonight.
3. Move the trading amount to the **perps (margin) balance**: $100–250.
   DOGE and SHIB contracts are about $5–8 each at 2–3x margin, so $100
   already holds every slot whole. Keep the rest of your money out of
   that account; the desk only ever sees the perps balance.
4. Account > API keys > create. Kalshi gives a key id and a private
   key file (PEM). Download or copy the PEM now; it is shown once.
   Kalshi keys cannot withdraw, so there is no permission to restrict.

## 4. Keys into the desk (2 minutes)

```bash
./desk.sh keys
```

Paste the Kalshi key id, then the PEM as it comes (several lines is
fine) or the path of a file you uploaded. Enter skips Alpaca, Kraken
and tastytrade. A Discord webhook is optional but worth it: fills,
exits, halts and the daily digest arrive on the phone.

## 5. Preflight until every line is [ok]

```bash
./desk.sh status
```

The lines that matter and what fixes them:

| line | if it fails |
|---|---|
| Kalshi API key id + private key PEM | re-run `./desk.sh keys` |
| Kalshi perps enabled for this account | step 3.2 |
| perps balance >= the need | step 3.3 |
| inactive Kalshi markets excluded | informational: PEPE is listed but inactive, the desk skips it |
| orders fit under max_trade_usd | leave `max_trade_usd: 500` as is |
| each live slot buys at least one contract | fund at least $100 |

## 6. One dashboard address for the desktop and the phone

The dashboard listens on the server's localhost only. Two ways in; the
second is the one to set up tonight.

**SSH tunnel** (works now, per device):

```bash
./desk.sh tunnel      # prints the URL and the Termius / ssh -L steps
```

From the desktop: `ssh -L 8080:localhost:8080 user@SERVER-IP`, then
open `http://localhost:8080/?t=TOKEN`. The tunnel must be up each time.

**Tailscale** (one private HTTPS address, same bookmark everywhere):

```bash
./desk.sh remote      # installs Tailscale on the server, signs it in, proxies the dashboard
```

It prints `https://SERVER.TAILNET.ts.net/?t=TOKEN`. Install the
Tailscale app on the phone and the desktop, sign in with the same
account, and that address works on both with no tunnel and no port open
to the internet. Save it as a desktop bookmark and a phone home-screen
icon. `./desk.sh url` prints it again any time.

The token in the URL is the only way in; keep the bookmark private.

## 7. Arm (tomorrow morning, or tonight if preflight is green)

```bash
./desk.sh arm
./desk.sh status
```

`arm` sets `perp.live: true` and `CRYPTOBOT_ARM_LIVE=yes` and
restarts. The dashboard's real toggle unlocks. `./desk.sh disarm` goes
back to paper at any time.

## What happens once it is armed

- The bounce-short on DOGE and SHIB reads closed daily candles once a
  day after 00:00 UTC. A first entry can take days; nothing fires
  intraday. Positions are checked hourly against live mids: −20%
  target, +10% stop, 14-day time exit.
- The allocator starts the real book at half its evidence weight and
  grows it with live fills. It halves size on bad slippage, pauses
  after four stop-outs in two hours, and stops new entries when real
  equity is 25% below its peak. The manual override is on the
  dashboard.
- `./desk.sh digest` is the day in one screen; `./desk.sh logs`
  follows the log.

## Runs on its own

Nothing needs a hand day to day once it is armed:

- The container restarts itself (`restart: unless-stopped`), survives a
  server reboot, and rotates its logs.
- The signal runs after 00:00 UTC (8 pm ET) on closed daily candles;
  stops and targets are checked hourly; the collectors run at 21:15 UTC.
- The daily digest and every fill, exit and halt go to the Discord
  webhook if one is set (`./desk.sh keys`); that is the phone's view
  during the day.

The two things that do wait for you, by design:

- A **halt** (four stop-outs in two hours, or real equity 25% below its
  peak) stops new entries until you press resume on the dashboard.
- **Code updates**: `./desk.sh update` pulls, rebuilds and restarts;
  nothing updates itself.

## Daily rhythm

| when | where | what |
|---|---|---|
| morning, phone | dashboard bookmark or the Discord digest | equity, open positions, any halt |
| during the day | Discord alerts | fills and exits; nothing to do |
| evening, desktop | dashboard | the day's fills, the allocator's weights, `./desk.sh status` once a week |

## Not for tomorrow

- The opening-range stock pilot needs Alpaca paper keys (free) and runs
  paper only.
- The Bitcoin volatility premium is real but its safe form needs about
  $25,000 of options margin; the Kalshi hourly-binaries version is
  being judged now and is not traded before a verdict.
- Kraken margin is wired and killed on costs; leave the venue at kalshi.

## Safety, once more

Never a key with withdrawal permission (Kalshi has none). Never the
Hyperliquid wallet from the US. `.env` stays mode 600 and is never
committed. Fund only the amount you are prepared to lose.
