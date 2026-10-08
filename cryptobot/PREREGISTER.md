# Pre-registering a rule

The Deflated Sharpe result (README, "How credible is the bounce-short?")
is the cost of searching first and counting later. From now on a rule is
written down before it is run, and the registry enforces the record.

Copy this block into `cryptobot/hypotheses.yaml` **before** running the
test, with `result: "PRE-REGISTERED <date>; not yet run"` and
`verdict: inconclusive`. Fill `result` and the verdict after the run,
without changing `claim`, `test` or `success` (if you must change them,
that is a new entry and `trials_run` goes up by one).

```yaml
- id: <short-kebab-id>
  title: "<one line>"
  source: "<paper / repo / own idea, with URL>"
  claim: "<the rule, exactly: signal, universe, horizon, exits, sizing>"
  test: "<data, period, cost model, walk-forward or CPCV, what is compared to what>"
  success: "<the number that decides, written before running: e.g. net Sharpe > 0 with PSR >= 0.95 over 2021-2026 AND positive net in the post-publication window>"
  data: "<cached files or endpoints>"
  result: "PRE-REGISTERED 2026-10-09; not yet run"
  verdict: inconclusive
  regime: "<what regime the evidence covers>"
  rerun: "python -m cryptobot.<module> ..."
  preregistered: true
  trials_run: 1          # raise it for every variant you end up trying
```

Rules the registry enforces (`cryptobot/hypotheses.py validate`):

- `alive` needs either `preregistered: true` with `psr` recorded, or the
  search diagnostics `trials_run`, `n_eff`, `pbo`, `dsr` (from
  `python -m cryptobot.stats`), or `diagnostics: pending` with
  `trials_run` (allowed only for entries that predate the rule; they
  stay flagged until the diagnostics are run).
- `alive` with diagnostics needs DSR >= 0.95 at N_eff, PBO <= 0.5 and
  >= 80% of CPCV paths positive; otherwise `inconclusive`.
- `python -m cryptobot.hypotheses --new <id>` prints the stub.
- `python -m cryptobot.hypotheses --similar "<idea>"` first, every time.

What counts as one trial: every (signal definition, parameter value,
horizon, exit geometry, side, universe) combination whose result you
looked at. Looking at a result and discarding it is a trial.
