# T-744: the minimum-size live execution test of the calendar sleeve

Decided by the user on 2026-11-03 after the funding summary. Pre-registered the same day
(`mandel/theories/register_live_2026_11_03.py`, ledger `theory.preregistered` T-744) before any real order exists.

## What it is

The paper test T-559 cannot pass its execution criterion: Alpaca paper runs no auctions, so its fills are 15:44 and
09:33 prints, not the closing and opening auction prints the rules (T-549, T-332, T-59, T-345) are defined on. This arm
places the same rules as real market-on-close and market-on-open orders for **one share** per symbol:

| rule | order | size | at risk |
|---|---|---|---|
| overnight QQQM (every session) | MOC buy 15:40 ET, MOO sell 08:30 ET next session | 1 share | ~$290 |
| IBS < 0.2 on SPYM (read 15:40 ET) | MOC buy, MOC sell next close | 1 share | ~$90 |
| turn-of-month SPYM (days -4..+3, T-345 skip) | MOC buy, MOC sell next close | 1 share | ~$90 |

At most about $400 is in the market on any night. Expected P&L at this size is noise and is **not** a criterion; the
test buys execution evidence. The paper arm continues unchanged for the return criterion (250 sessions).

## Pass criterion (registered, cannot change)

At 60 sessions with a fill: mean |fill − official print| ≤ 1.5 bp per side, 95% upper bound ≤ 2.5 bp, and ≥ 95% of
auction orders filled. The tracker reports `fill_gap_bp_mean`, `fill_gap_bp_upper95`, `fill_gap_n` from the live journal.

## Guards (code, tested in tests/test_mandel_live.py)

- Real orders need `--live` **and** `MANDEL_ALPACA_LIVE=I-UNDERSTAND` in the environment. The installer never writes
  the switch; the user types it. Without it the client is read-only and `submit` refuses.
- Fixed size `MANDEL_LIVE_SHARES` (1); a buy is skipped and journalled when cash does not cover it: nothing is borrowed.
- Loss halt `MANDEL_LIVE_MAX_LOSS_USD` (40), on the MARKED loss (realised round trips, including today's fills read from
  the broker, plus the unrealised P&L of what is held): a `HALT` file is written and no further BUY is placed until the
  user removes it; every sell a rule calls for still goes out, so a halt never strands a position. `KILL` stops every
  order phase at once (then the user closes any position by hand).
- A phase places nothing, and journals why (`live.skipped`), when a sleeve order is still open (a second run inside the
  window would double the position), when the account holds more than the fixed size of a sleeve symbol (not the
  sleeve's position: nothing is touched), or when the clock is outside Alpaca's acceptance window for that auction order
  (`cls` 15:30-15:50 ET, `opg` 07:00-09:28 ET; after 19:00 ET Alpaca would queue the order for the next day's auction).
  An account that reports itself blocked places nothing (`live.blocked`).
- Own state directory and journal (`~/mandel-live-state`), own systemd units, own branch `live/journal`. The options
  sleeve never runs live.
- Every order phase journals a `live.armed` row (switch, size, cap, realised and unrealised P&L, held, open orders)
  before acting; `import_linode` mirrors armed and halted rows into Mandel's ledger as the box's report (`actor="box"`,
  with what the row attests). The ledger never claims a human act it did not witness: a branch anyone with push could
  write is not evidence of the user's hand, only the env file on the box is.
- Unfilled auction orders end `canceled` (after the auction) or `rejected` (outside the window) on Alpaca; the tracker
  counts both, with `expired`, as unfilled for criterion (b).
- Re-running the installer on an armed install refuses to move the code unless `PIN=<commit>` is given, and the new
  commit's tests must pass before the running checkout moves; timers are enabled only after the keys were exercised.

## Procedure for the user (Linode)

1. Create a **live** Alpaca account (margin account, the default) and fund it with about **$1,000**: the sleeve uses at
   most ~$400; the rest is a settlement buffer so nightly round trips never trip a good-faith violation. Create live API
   keys (key id starts with `AK`). Never reuse the paper keys.
2. Install, pinned to the commit that carries this file:
   ```
   curl -fsSL "https://raw.githubusercontent.com/pointlessbassmusic-byte/polymarket-arbitrage/claude/mandel-genesis/deploy/live/install.sh?v=1" | PIN=<commit> bash
   ```
   It asks for the live keys once (stored in `/etc/mandel-live.env`, mode 600), installs the timers, and runs a
   read-only status and dry runs of both order phases against the live account. Nothing can be placed yet.
3. Read the dry-run output (equity, cash, the orders it would send). Then arm it with the one line it prints:
   ```
   echo MANDEL_ALPACA_LIVE=I-UNDERSTAND | sudo tee -a /etc/mandel-live.env
   ```
   The first real orders go at the next 15:40 ET close.
4. Disarm at any time: remove that line, or `touch ~/mandel-live-state/KILL`.

Known gap: a nightly journal push that fails (no deploy key, network) is silent; the tracker then shows the live row
stale. Check `journalctl -u mandel-live-journal` if the row stops moving.

Mandel's part is done when the code is pushed and T-744 is registered. Mandel does not and cannot arm it.
