# Running the desk from a phone

Everything below is a short command typed into an SSH app (Termius,
Blink, the Linode console). Nothing needs a file editor. The dashboard
itself is laid out for a phone screen.

## First time: put the desk on the server (about 10 minutes)

1. In the GitHub app or browser: Settings > Developer settings >
   Fine-grained tokens > a token with **read-only Contents** on this
   repository. Copy it.
2. In the SSH app, on the server:

```bash
git clone -b claude/crypto-arbitrage-volatility-bot-qic8gv https://TOKEN@github.com/pointlessbassmusic-byte/polymarket-arbitrage.git
cd polymarket-arbitrage
git remote set-url origin https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git   # the token leaves the URL
./deploy.sh
```

`deploy.sh` installs Docker, writes `.env` with a random dashboard
token, builds the history seed and starts paper trading. It ends by
printing the dashboard URL.

## See the dashboard on the phone

```bash
./desk.sh tunnel
```

prints the URL and the Termius steps: on the host, Port Forwarding >
Local, port 8080 to localhost:8080; connect; open
`http://localhost:8080/?t=…` in the phone's browser. The port is never
open to the internet.

## One address for the phone and the desktop

```bash
./desk.sh remote
```

installs Tailscale on the server, signs it in (a login link prints
once) and proxies the dashboard to `https://SERVER.TAILNET.ts.net/?t=…`.
With the Tailscale app signed in on the phone and the desktop, that one
bookmark works on both, no tunnel, no port open to the internet.
`./desk.sh url` prints it again.

## Add keys (prompts, paste-friendly)

```bash
./desk.sh keys
```

Asks for each key in turn; enter keeps what is there, blank skips. For
the Kalshi private key, paste the PEM as it comes (several lines is
fine) or type the path of a file you uploaded. Keys land in `.env` with
mode 600 and the desk restarts if it is running.

Where the keys come from, all doable in the phone browser:

- **Kalshi**: kalshi.com > account > API keys > create (Ed25519); enable
  perpetuals on the account; move the trading amount to the perps
  balance. No withdrawal permission exists on Kalshi keys.
- **Alpaca** (optional, stocks): app.alpaca.markets > Paper trading >
  API keys. Paper keys are enough for every test in the queue.
- **Discord webhook** (optional): a channel > Integrations > Webhooks.
  Fills, exits, halts and the daily digest arrive there.

## Go live

```bash
./desk.sh status      # preflight: every line must be [ok]
./desk.sh arm         # perp.live: true, CRYPTOBOT_ARM_LIVE=yes, restart
./desk.sh status      # the dashboard's real toggle is now unlocked
```

`./desk.sh disarm` returns to paper. The allocator starts the real book
at half its evidence weight and grows it with live fills; manual
allocation is on the dashboard.

## Every day

```bash
./desk.sh status      # containers, arming, keys, preflight, research counts
./desk.sh digest      # today's digest
./desk.sh logs        # follow the log (ctrl-c to stop)
./desk.sh update      # pull the latest code, rebuild, restart
```
