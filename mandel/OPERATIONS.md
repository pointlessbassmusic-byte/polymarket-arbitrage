# Operating Mandel across a Linode server, a PC and an iPhone

The user's setup: a Linode Ubuntu server, a Windows PC (PowerShell, Python),
an iPhone, all tied to the same GitHub repositories and Claude Code
sessions. This document is Mandel's recommendation for running itself on
that setup with the least friction and the least waste.

## The one rule

**The repository is the only memory.** Mandel's state (`mandel/state/`),
knowledge (`mandel/knowledge/`), and the signal map (`mandel/viz/`) are
committed files. Any machine that has pulled `main` has all of Mandel. No
machine holds anything the others cannot get with `git pull`.

## Roles for each machine

| Machine | Role | Why |
|---|---|---|
| Linode (Ubuntu) | Mandel's home: scheduled cycles, the live signal map, child sessions via Claude Code CLI | always on, stable IP, can serve the map over HTTPS |
| Claude Code cloud sessions (like this one) | heavy research and multi-agent workflows | parallel agents, fresh containers, nothing to clean up |
| PC (PowerShell) | reviewing, approving, editing the knowledge files, running tests | a real screen for reading the map and the ledger |
| iPhone | watching the map, nudging a session, approving a proposal | Claude app follows the cloud session; a terminal app (Termius, Blink) reaches the Linode |

## Linode: the minimal install

```bash
# as a non-root user with sudo
sudo apt update && sudo apt install -y git python3 python3-venv nginx
git clone https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git ~/mandel
cd ~/mandel && git checkout main
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python -m pytest tests/test_mandel_*.py -q          # the engine's own tests
python -m mandel status                              # ledger integrity and counts
python -m mandel graph                               # rebuild viz/graph.json and viz/index.html
```

Install Claude Code on the server so Mandel and the children can run there
from any device over SSH: `curl -fsSL https://claude.ai/install.sh | bash`
(or `npm install -g @anthropic-ai/claude-code`), then `claude` inside the
repo. From the iPhone, SSH in with Termius or Blink and run the same
command; the session is the same whichever screen you hold.

### Serve the signal map

The map is one static file. Serve `mandel/viz/index.html` with nginx and it
updates every time `python -m mandel graph` runs:

```nginx
server {
    listen 80;
    server_name mandel.example.com;          # or the Linode IP
    root /home/USER/mandel/mandel/viz;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```

Put it behind HTTPS with `certbot --nginx` and, because the map reveals
what Mandel knows, behind basic auth (`htpasswd`) or Tailscale.

### Schedule a daily cycle

A systemd timer (cron works too) that pulls, rebuilds the map, re-verifies
the ledger, and pushes any state changes:

```ini
# /etc/systemd/system/mandel-cycle.service
[Unit]
Description=Mandel daily maintenance cycle
[Service]
Type=oneshot
User=USER
WorkingDirectory=/home/USER/mandel
ExecStart=/bin/bash -lc 'git pull --ff-only && . .venv/bin/activate && python -m mandel verify && python -m mandel social-fetch && python -m mandel options-fetch && python -m mandel options-fetch --smile && python -m mandel book-snapshot && python -m mandel experiment-run all && python -m mandel theories --render && python -m mandel ingest && python -m mandel graph && git add mandel/state mandel/viz mandel/archive mandel/theories && git -c user.name=Mandel -c user.email=mandel@localhost commit -qm "Mandel daily cycle" || true; git push'
```
```ini
# /etc/systemd/system/mandel-cycle.timer
[Unit]
Description=Run the Mandel cycle every morning
[Timer]
OnCalendar=*-*-* 06:40:00
Persistent=true
[Install]
WantedBy=timers.target
```
`sudo systemctl enable --now mandel-cycle.timer`.

Weekly (Sunday), refresh the slower-moving histories the daily job does not touch: `python -m mandel unlock-fetch all` (Yahoo OHLC histories, Ken French and AQR factors, FOMC calendar, Deribit funding/settlement/futures, CBOE VIX futures) followed by `python -m mandel experiment-run all`. A second timer (`OnCalendar=Sun *-*-* 07:30:00`) running the same service with these two commands is enough. The daily cycle is
maintenance only: it never changes trading parameters. Anything that
changes behaviour goes through a proposal and the gate, run by a Claude
Code session (on the Linode or in the cloud) that can read the evidence.

The equivalent inside Claude Code: a scheduled Routine that opens a fresh
session on the repo with the prompt "Run Mandel's maintenance cycle per
mandel/MANDEL.md section 3; do not change trading parameters; report what
changed". Mandel can create that Routine when the user asks for it.

## PC (PowerShell)

```powershell
git clone https://github.com/pointlessbassmusic-byte/polymarket-arbitrage.git
cd polymarket-arbitrage
py -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py -m pytest tests\test_mandel_*.py -q
py -m mandel status
py -m mandel graph; start .\mandel\viz\index.html     # opens the map locally
```

Everything Mandel does is `py -m mandel <command>`; `py -m mandel --help`
lists them. The commands that matter day to day:

- `status`, `verify`: is the ledger intact, what is open.
- `insights --tag adopt`, `insights --status validated`: what Mandel believes.
- `proposals`, `proposal-show ID`: what is being tested and what passed.
- `forecasts`: the scoreboard. Whoever has the lowest Brier score and a
  positive skill versus the market is actually predicting.
- `children`, `child-show NAME`: what each child has reported and been told.

## Secrets and safety

- API keys never go in the repo. `config.yaml` carries placeholders; real
  keys live in environment variables on the Linode only (`/etc/mandel.env`,
  mode 600, loaded by the service that trades).
- `trading_mode: dry_run` stays the default everywhere. The only machine
  that may hold live keys is the Linode, and only after a proposal has
  passed the gate and the user has said yes.
- The ledger is a hash chain with a head anchor (`mandel/state/ledger.head`).
  `python -m mandel verify` reports an edited, inserted or truncated line
  and any proposal whose file status disagrees with the ledger. It cannot
  detect a full rewrite of both files; git history is the anchor for that,
  so keep `mandel/state` committed and compare heads across commits when
  in doubt (`verify --anchor <hash>`). Run it in the daily cycle.

## Suggested next steps for the setup

1. Merge the `claude/mandel-genesis` branch to `main` once the architecture
   phase lands, so every machine pulls the same Mandel.
2. Install Claude Code on the Linode and run `claude` in the repo once from
   the PC and once from the iPhone to confirm both paths work.
3. Decide where the signal map is served (Linode behind auth, or the
   claude.ai artifact link, or both).
4. Ask Mandel to create the daily Routine, or install the systemd timer.

## Paper sleeves (T-559, T-560), added 2026-10-20

`mandel.live.runner` trades the Alpaca PAPER account. Live money needs both `--live` and
`MANDEL_ALPACA_LIVE=I-UNDERSTAND` in the environment; Mandel never sets either. Keys:
`ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` in the environment of the machine that runs it (the
Linode), never in the repository. A file `mandel/state/paper/KILL` stops every order-placing phase.

Cron on the Linode, in New York time (`CRON_TZ=America/New_York`), weekdays:

```
30 8  * * 1-5  cd /opt/mandel && python3 -m mandel.live.runner open
25 15 * * 1-5  cd /opt/mandel && python3 -m mandel.live.runner options
44 15 * * 1-5  cd /opt/mandel && python3 -m mandel.live.runner close
20 16 * * 1-5  cd /opt/mandel && python3 -m mandel.live.runner reconcile
```

Closing-auction orders must reach Alpaca by 15:50 ET and opening-auction orders by 09:28 ET. Run each phase
with `--dry-run` once by hand first; `status` prints equity, positions and the open spread.

### Paper strategy tracker

`python -m mandel.live.tracker --journal <copy of the Linode's paper journal>` rebuilds
`state/tracker/strategies.json` (one row per paper, live or forward test, Mandel's and the children's) and appends the
day to `state/tracker/history.jsonl` / `history.json`. Those two files feed the "Paper Strategy Tracker" dashboard
(https://claude.ai/artifact/YW11NMqwusSM59jktjYmSW): Mandel re-uploads them after each refresh. The children's rows come
from `state/children/forward_tests.json`, their own figures; update its counts and `as_of` when a child reports again.

Sleeve capital: the runner trades a fixed `MANDEL_PAPER_CAPITAL` (default 5000; set it in /etc/mandel-paper.env to
change), never the account's equity, and the calendar slot never borrows (capped by cash plus its own SPLG/QQQM). The
first install landed on a paper account shared with the crypto child's QQQ/XLF pilots; a dedicated Alpaca paper account
keeps the two forward records apart.

### Evidence graph

`python -m mandel.live.evidence_graph` (after the tracker) maps every tracked strategy to the signals it reads, the
data streams behind them, its venue, account and risk factors, and writes `state/tracker/{evidence_graph,alerts,
dependencies,next_tests}.json` for the dashboard: stale streams with everything downstream (strategies and blocked
theories), shared accounts and factor exposure against caps, conflicting measured results, tests at their decision
point, and a value-of-information ranking of what to test next. It recommends only; `checkpoint_size` (quarter Kelly
shrunk by the deflated Sharpe, capped) is applied only at a pre-registered decision point. Wiring for a new strategy
goes in `WIRING` in mandel/live/evidence_graph.py.

### Linode capture box, HMM shadows, widened sleeves

`deploy/capture/install.sh` (one command on the Linode, beside the paper runner) installs a second pinned checkout
`~/mandel-capture` with its data outside it (`~/mandel-capture-data`, via `MANDEL_ARCHIVE_ROOT` / `MANDEL_DATA_ROOT`):

- `mandel.live.capture daily` (18:30 ET) runs the daily fetches (CBOE chains + surfaces, Deribit books, VIX/FRED/DVOL
  histories, social, Polymarket books) and `score` (T-542's parity share on the box's captures); `weekly` (Sunday) the
  slower histories and the Cboe PUT index. Raw Cboe chains stay on the box.
- `mandel.live.shadow record` (16:35 ET) writes the frozen HMMs' readings for T-565 / T-566 (`shadow_params.json`,
  fitted through 2026-09-30, never refitted). Nothing is traded.
- `mandel.live.wide` runs T-567 (pre-holiday IWM, 12:46 and 15:46 ET runs that act only near that session's close) and
  T-568 (GLD/TLT/USO put spreads, 15:27 ET) on its own keys (`/etc/mandel-wide.env`; a second Alpaca paper account is
  recommended), capital `MANDEL_WIDE_CAPITAL` (5,000), state `~/mandel-capture-data/wide`, KILL file there.
- 19:30 ET: `deploy/capture/push_status.sh` pushes status.json, scores.json, shadow.jsonl and the widened journal (no raw
  data) to branch `capture/status`. Mandel copies status.json to `state/tracker/capture_status.json` before running the
  evidence graph, which then reads stream freshness from the box.
The paper runner's journal push now runs `deploy/paper/push_journal.sh` (the earlier inline command was mangled by
systemd's `$` and `%` expansion); re-running deploy/paper/install.sh installs it without changing the runner's code.
