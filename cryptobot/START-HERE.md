# Start to finish: from a Linode account to real money on Kalshi

What runs where: I write the code and push it to this GitHub branch.
Your Linode server pulls it and runs the desk in Docker. Your computer
and phone only ever type a few commands over SSH and open the dashboard
in a browser. Nothing is installed on your computer except a terminal
(already there) and, optionally, the Tailscale app.

Never send me passwords, the Kalshi private key, API tokens or the
dashboard token. I never need them; they go straight into the server.

## 0. On your computer

- **Mac:** open Terminal (Spotlight, type Terminal).
- **Windows 10/11:** open PowerShell or Windows Terminal. `ssh` is built in.
- Or install **Termius** on the desktop too (termius.com): the same
  hosts, keys and port-forwards you have on the phone sync to it, which
  is the smoothest way to switch between the two.

Test that SSH exists: type `ssh -V` and press enter; a version prints.

## 1. The Linode server

In cloud.linode.com, left menu **Linodes** (not Databases; the desk
keeps its state in files, no database is needed).

If you do not have one yet: **Create Linode**, image **Ubuntu 24.04 LTS**,
region near you, plan **Shared CPU, Linode 2 GB** (about $12 a month;
the 1 GB Nanode is tight for the Docker build), set a root password,
create. Wait for status Running.

From the Linode's page note two things:

- the **IP address** (IPv4, top of the page)
- the **root password** you set (or the SSH key you added)

That IP is the only thing I need from Linode, and only so the commands
below read right. You never need to send me the password.

## 2. First login

In the terminal (replace IP):

```bash
ssh root@IP
```

Type `yes` to the fingerprint question, then the root password (nothing
shows while typing). You are now on the server; the prompt changes.

Basic hygiene, once:

```bash
apt-get update && apt-get install -y ufw git python3 curl
ufw allow OpenSSH && ufw --force enable
```

## 3. A GitHub token so the server can read this repository

On your computer, in a browser: github.com > your avatar > **Settings**
> **Developer settings** (bottom left) > **Personal access tokens** >
**Fine-grained tokens** > **Generate new token**. Name it `linode`,
expiry 90 days, **Repository access: Only select repositories** >
`polymarket-arbitrage`, **Permissions > Repository permissions >
Contents: Read-only**. Generate, copy the token (starts with
`github_pat_`). It is shown once.

## 4. Put the desk on the server

On the server (paste the token in place of TOKEN):

```bash
git clone -b claude/crypto-arbitrage-volatility-bot-qic8gv https://TOKEN@github.com/pointlessbassmusic-byte/polymarket-arbitrage.git
cd polymarket-arbitrage
git remote set-url origin https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git
./deploy.sh
```

`deploy.sh` installs Docker, writes `.env` with a random dashboard
token, builds the image, builds the history seed from public data and
starts the desk in paper mode. The first run takes about ten minutes.
It ends by printing the dashboard URL. If it stops with a Docker
permission error, type `exit`, log in again and run `./deploy.sh`
again; it is safe to repeat.

For later updates (whenever I say I pushed something):

```bash
cd polymarket-arbitrage && ./desk.sh update
```

That pulls the branch, rebuilds and restarts. You need the token again
only if the repository is private and the pull asks; then re-run the
clone line's `remote set-url` with the token, pull, and set it back.

## 5. One dashboard address for desktop and phone

On the server:

```bash
./desk.sh remote
```

It installs Tailscale, prints a login link once (open it in any
browser, sign in with Google or Apple, approve the machine), then
proxies the dashboard and prints:

```
https://SERVERNAME.TAILNET.ts.net/?t=LONGTOKEN
```

On your computer and phone: install the Tailscale app
(tailscale.com/download), sign in with the same account, turn it on.
Open that URL on both; bookmark it on the desktop, add it to the phone's
home screen. `./desk.sh url` prints it again any time. The dashboard is
never open to the internet; only devices in your Tailscale account
reach it, and only with the token.

If you would rather not use Tailscale: `./desk.sh tunnel` prints the
SSH-tunnel alternative (`ssh -L 8080:localhost:8080 root@IP` on the
computer, then http://localhost:8080/?t=TOKEN).

## 6. Kalshi

In the Kalshi app or kalshi.com:

1. Identity verified.
2. **Perpetuals enabled**: look for a Perpetuals or Margin section. If
   it is missing, message Kalshi support and ask for perps access; it is
   rolled out per member and the desk's preflight checks it.
3. Move $100 to $250 into the **perps balance**. Leave the rest of your
   money out of this account.
4. **API key**: kalshi.com > Account (kalshi.com/account/profile) > API
   Keys > Create. Save the **Access Key ID** and download the
   **private key file**. The file is shown once. Kalshi keys cannot
   withdraw funds.

Get the key file to the server. On your computer (new terminal tab,
replace the file name and IP):

```bash
scp ~/Downloads/kalshi-private-key.key root@IP:/root/polymarket-arbitrage/kalshi.pem
```

(Windows PowerShell: `scp $HOME\Downloads\kalshi-private-key.key root@IP:/root/polymarket-arbitrage/kalshi.pem`.)

## 7. Keys into the desk

On the server:

```bash
./desk.sh keys
```

Paste the Access Key ID at the Kalshi prompt; at the private-key prompt
type `kalshi.pem` (the path of the file you copied) or paste the PEM.
Press enter at the Alpaca, Kraken and tastytrade prompts to skip them.
A Discord webhook (Discord > a channel > Edit > Integrations > Webhooks
> New) is optional and worth it: fills, exits, halts and the daily
digest arrive on the phone. Then:

```bash
rm kalshi.pem
```

The key is now inside `.env` (mode 600) and the file is not needed.

## 8. Preflight

```bash
./desk.sh status
```

Every preflight line must read `[ok]`. The ones that can fail:

| line | fix |
|---|---|
| Kalshi API key id + private key PEM | `./desk.sh keys` again |
| Kalshi perps enabled for this account | step 6.2 |
| perps balance >= need | step 6.3 |
| each live slot buys at least one contract | fund at least $100 |

Leave it in paper mode until every line is green; the dashboard shows
paper trades meanwhile.

## 9. Arm

```bash
./desk.sh arm
./desk.sh status
```

The dashboard's real toggle is now unlocked. The bounce-short reads the
daily candle after 00:00 UTC (8 pm ET); a first entry can take days.
`./desk.sh disarm` returns to paper at any time.

## Every day after that

Nothing on the server. The phone sees the dashboard bookmark and the
Discord alerts; the desktop the same bookmark. A halt (four stop-outs
in two hours, or real equity 25% below its peak) waits for a resume
press on the dashboard. When I push code: `./desk.sh update`.

## If something goes wrong

- `./desk.sh logs` follows the log (ctrl-c stops following).
- `docker compose ps` shows the container; `docker compose restart`
  restarts it.
- Lost the dashboard URL: `./desk.sh url`.
- Server rebooted: the container comes back by itself.
- Anything else: paste the last 30 lines of `./desk.sh logs` to me.
