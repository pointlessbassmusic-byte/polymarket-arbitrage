"""Synthetic checks for the selection-bias diagnostics in cryptobot.stats."""

import math
import random
import statistics
from statistics import NormalDist

import pytest

from cryptobot.backtest import Candle, PoolMeta
from cryptobot.perp_study import DAILY_FEATURES, collect
from cryptobot.research import Barrier, candidate_rules
from cryptobot import stats as S

DAY = 86400


def _noise_matrix(t, n, seed, mu=0.0):
    rng = random.Random(seed)
    return [[rng.gauss(mu, 1.0) for _ in range(t)] for _ in range(n)]


class TestSharpeTests:
    def test_psr_matches_the_closed_form_on_sample_moments(self):
        rng = random.Random(1)
        xs = [rng.gauss(0.1, 1.0) for _ in range(400)]
        mo = S.moments(xs)
        sr = mo["mean"] / mo["sd"]
        z = (sr - 0.0) * math.sqrt(len(xs) - 1) / math.sqrt(
            1 - mo["skew"] * sr + (mo["kurt"] - 1) / 4 * sr * sr)
        assert S.psr(xs, 0.0) == pytest.approx(NormalDist().cdf(z), abs=1e-12)

    def test_psr_of_iid_normal_with_known_sr(self):
        # skew ~ 0 and kurtosis ~ 3, so PSR(0) ~ Phi(SR sqrt(T-1)) and
        # PSR at the true SR sits near one half.
        rng = random.Random(2)
        true_sr = 0.05
        xs = [rng.gauss(true_sr, 1.0) for _ in range(5000)]
        sr = S.sharpe(xs)
        assert sr == pytest.approx(true_sr, abs=0.03)
        assert S.psr(xs, 0.0) == pytest.approx(NormalDist().cdf(sr * math.sqrt(len(xs) - 1)), abs=0.02)
        assert 0.1 < S.psr(xs, true_sr) < 0.9

    def test_min_trl_is_the_length_at_which_psr_crosses_the_confidence(self):
        rng = random.Random(3)
        xs = [rng.gauss(0.3, 1.0) for _ in range(300)]
        assert S.sharpe(xs) > 0.1
        n = S.min_trl(xs, 0.0, alpha=0.05)
        mo = S.moments(xs)
        sr = mo["mean"] / mo["sd"]
        z = (sr - 0.0) * math.sqrt(n - 1) / math.sqrt(1 - mo["skew"] * sr + (mo["kurt"] - 1) / 4 * sr ** 2)
        assert NormalDist().cdf(z) == pytest.approx(0.95, abs=1e-9)
        assert S.min_trl(xs, sr) == math.inf            # cannot beat itself
        assert S.min_trl(xs, 0.5 * sr) > n              # a higher bar needs more data

    def test_expected_max_sr_grows_with_the_number_of_trials(self):
        vals = [S.expected_max_sr(n, 1.0) for n in (1, 2, 5, 10, 100, 1000, 10000)]
        assert vals[0] == 0.0
        assert all(b > a for a, b in zip(vals, vals[1:]))
        # paper's snippet: N=1000, var=1 -> about 3.26
        assert S.expected_max_sr(1000, 1.0) == pytest.approx(3.26, abs=0.02)
        assert S.expected_max_sr(100, 0.25) == pytest.approx(0.5 * S.expected_max_sr(100, 1.0))

    def test_dsr_deflates_psr(self):
        rng = random.Random(4)
        xs = [rng.gauss(0.1, 1.0) for _ in range(300)]
        assert S.dsr(xs, 1, 0.01) == pytest.approx(S.psr(xs, 0.0))
        assert S.dsr(xs, 500, 0.01) < S.dsr(xs, 5, 0.01) < S.psr(xs, 0.0)


class TestNEff:
    def test_uncorrelated_columns_count_in_full(self):
        cols = _noise_matrix(600, 12, seed=5)
        ne = S.n_eff_from_corr(cols, power_iters=0)
        assert ne["pr_method"] == "exact"
        assert ne["n_eff_a3"] == pytest.approx(12, abs=0.5)
        assert ne["n_eff_pr"] == pytest.approx(12, abs=0.6)

    def test_identical_columns_count_once(self):
        base = _noise_matrix(300, 1, seed=6)[0]
        cols = [list(base) for _ in range(8)] + [[2 * x + 1 for x in base]]
        ne = S.n_eff_from_corr(cols)
        assert ne["rho"] == pytest.approx(1.0)
        assert ne["n_eff_a3"] == pytest.approx(1.0)
        assert ne["n_eff_pr"] == pytest.approx(1.0, abs=1e-6)
        assert ne["top_share"] == pytest.approx(1.0, abs=1e-6)

    def test_hutchinson_agrees_with_the_exact_participation_ratio(self):
        rng = random.Random(7)
        common = [rng.gauss(0, 1) for _ in range(500)]
        cols = [[0.7 * c + rng.gauss(0, 1) for c in common] for _ in range(30)]
        exact = S.n_eff_from_corr(cols, exact_limit=100, power_iters=0)
        est = S.n_eff_from_corr(cols, exact_limit=5, probes=64, power_iters=5)
        assert est["pr_method"].startswith("hutchinson")
        assert est["n_eff_pr"] == pytest.approx(exact["n_eff_pr"], rel=0.25)
        assert 1.5 < exact["n_eff_pr"] < 30
        assert 0.2 < est["top_share"] < 0.8

    def test_constant_columns_are_ignored(self):
        cols = _noise_matrix(200, 4, seed=8) + [[0.0] * 200]
        assert S.n_eff_from_corr(cols, power_iters=0)["m"] == 4


class TestCSCV:
    def test_pure_noise_gives_pbo_near_one_half(self):
        # One matrix's PBO is a noisy number: its 252 splits reuse the same
        # 10 blocks, so a single seed lands anywhere in roughly 0.1..0.9.
        # The mean across seeds is what should sit at one half.
        pbos, spear = [], []
        for seed in range(11, 23):
            cv = S.cscv_pbo(_noise_matrix(400, 25, seed), n_blocks=10, metric="sharpe")
            assert cv["n_splits"] == 252
            pbos.append(cv["pbo"])
            spear.append(cv["spearman_mean"])
        assert 0.38 <= statistics.mean(pbos) <= 0.62
        assert abs(statistics.mean(spear)) < 0.08

    def test_planted_edge_is_found_and_survives(self):
        cols = _noise_matrix(500, 40, seed=12)
        rng = random.Random(13)
        cols[17] = [rng.gauss(0.35, 1.0) for _ in range(500)]
        cv = S.cscv_pbo(cols, n_blocks=8, metric="sharpe", named=17)
        assert cv["pbo"] <= 0.05
        assert cv["named"]["is_best_share"] >= 0.9
        assert cv["named"]["oos_rel_median"] > 0.9
        assert cv["prob_loss_oos"] <= 0.05
        var_sr = statistics.pvariance([S.sharpe(c) for c in cols])
        assert S.dsr(cols[17], 40, var_sr) > 0.99

    def test_metric_options_and_purge(self):
        cols = _noise_matrix(400, 10, seed=14)
        for metric in ("mean", "per_signal", "sharpe"):
            cv = S.cscv_pbo(cols, n_blocks=4, metric=metric, purge=5)
            assert cv["n_splits"] == 6
            assert 0.0 <= cv["pbo"] <= 1.0
        with pytest.raises(ValueError):
            S.cscv_pbo(cols, n_blocks=4, purge=60)         # > half a 100-row block
        with pytest.raises(ValueError):
            S.cscv_pbo(cols, n_blocks=5)

    def test_purge_removes_the_rows_next_to_oos_blocks(self):
        # Two blocks, IS = block 0: with purge p the IS metric 'mean' is the
        # mean of block 0 minus its last p rows.
        col = [float(i) for i in range(20)]
        other = [0.0] * 20
        cv = S.cscv_pbo([col, other], n_blocks=2, metric="mean", purge=3)
        split = next(s for s in cv["splits"] if s["is_blocks"] == (0,))
        assert split["best"] == 0
        # OOS metric of the best is the mean of block 1 = 14.5 (no purge OOS)
        assert split["best_oos"] == pytest.approx(statistics.mean(col[10:]))

    def test_spearman_and_ranks(self):
        assert S.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
        assert S.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
        assert S._rank_avg([5, 1, 5, 2]) == [3.5, 1.0, 3.5, 2.0]


class TestCPCV:
    def test_purge_and_embargo_leave_no_label_overlap(self):
        start = 1_600_000_000
        ts = [start + DAY * i for i in range(600)]
        h, emb = 14, 6
        groups, splits = S.cpcv_splits(ts, n_groups=6, n_test=2, purge_days=h, embargo_days=emb)
        assert len(groups) == 6 and len(splits) == 15
        for sp in splits:
            test = set(sp["test"])
            train = sp["train"]
            assert train and not test & set(train)
            for t in train:
                for u in sp["test"]:
                    # label windows [t, t+h] and [u, u+h] must not touch
                    assert t + h * DAY < u or t > u + h * DAY, (t, u)
                    if t > u:
                        assert t > u + (h + emb) * DAY
        # the whole timeline is a test day in exactly C(5,1)=5 splits
        counts = {t: 0 for t in ts}
        for sp in splits:
            for t in sp["test"]:
                counts[t] += 1
        assert set(counts.values()) == {5}

    def test_paths_cover_every_day_once(self):
        pools = _trending_pools(seed=21, n_coins=3, days=400)
        rows = collect(pools, Barrier(0.10, 0.05), 5, "short")
        rule = (("move_1d", 2), ("move_3d", 0))
        cp = S.cpcv_paths(rows, rule, lambda y: 0.001, n_groups=6, n_test=2, purge_days=5)
        assert cp["n_splits"] == 15 and cp["n_paths"] == 5
        t = len({r["ts"] for r in rows})
        for p in cp["paths"]:
            assert p["days"] == t
            assert math.isfinite(p["sharpe"])
        assert 0.0 <= cp["frac_paths_pos_net"] <= 1.0
        assert cp["embargo_days"] == math.ceil(0.01 * t)
        for s in cp["splits"]:
            assert s["n_train"] > 0


def _trending_pools(seed, n_coins, days):
    rng = random.Random(seed)
    pools = {}
    for k in range(n_coins):
        px = 1.0 + k
        closes, highs, lows = [], [], []
        for _ in range(days):
            px *= math.exp(rng.gauss(0.0, 0.05))
            closes.append(px)
            highs.append(px * (1 + abs(rng.gauss(0, 0.03))))
            lows.append(px * (1 - abs(rng.gauss(0, 0.03))))
        meta = PoolMeta(chain="hyperliquid", pair_address=f"C{k}", symbol=f"C{k}",
                        token_address="", liquidity_usd=0.0, fdv_usd=None)
        pools[f"C{k}"] = (meta, [Candle(ts=1_600_000_000 + DAY * i, open=c, high=highs[i],
                                        low=lows[i], close=c, volume_usd=1000 + rng.random())
                                 for i, c in enumerate(closes)])
    return pools


class TestTrialMatrix:
    def test_columns_match_the_slow_candidate_rules_path(self):
        pools = _trending_pools(seed=31, n_coins=4, days=300)
        geoms = [(0.10, 0.05, 5)]
        tm = S.trial_matrix(pools, {}, geoms, ("short",), min_signal_days=1, flat_cost=0.004)
        assert tm.nominal == 21 * 9
        assert tm.n == len(tm.names) == len(tm.data) == len(tm.signal_days)
        rows = collect(pools, Barrier(0.10, 0.05), 5, "short")
        idx = {t: i for i, t in enumerate(tm.timestamps)}
        for name, pred in candidate_rules(rows, 3, DAILY_FEATURES):
            full = f"short +10/-5 5d {name}"
            if full not in tm.names:
                continue
            col = tm.data[tm.index(full)]
            acc, cnt = [0.0] * tm.t, [0] * tm.t
            for r in rows:
                if pred(r):
                    acc[idx[r["ts"]]] += r["pnl"] - 0.004
                    cnt[idx[r["ts"]]] += 1
            want = [acc[i] / cnt[i] if cnt[i] else 0.0 for i in range(tm.t)]
            assert list(col) == pytest.approx(want)
            assert tm.signal_days[tm.index(full)] == sum(1 for c in cnt if c)

    def test_min_signal_days_filter_and_rule_series_agree(self):
        pools = _trending_pools(seed=32, n_coins=3, days=300)
        geoms = [(0.10, 0.05, 5)]
        strict = S.trial_matrix(pools, {}, geoms, ("short",), min_signal_days=40, flat_cost=0.0)
        loose = S.trial_matrix(pools, {}, geoms, ("short",), min_signal_days=1, flat_cost=0.0)
        assert strict.n < loose.n and strict.nominal == loose.nominal
        rule = loose.meta[0]["rule"]
        rows = collect(pools, Barrier(0.10, 0.05), 5, "short")
        rs = S.rule_series(rows, rule, lambda y: 0.0)
        assert list(loose.data[0]) == pytest.approx(rs["rule"])
        assert rs["n_trades"] == loose.trades[0]
        assert list(loose.uncond[loose.meta[0]["set"]]) == pytest.approx(rs["uncond"])
        assert list(S.lift_columns(loose, "same_day")[0]) == pytest.approx(rs["lift"])
        assert list(S.lift_columns(loose, "always")[0]) == pytest.approx(rs["lift_always"])
        assert sum(loose.fired[0]) == rs["signal_days"]
        assert S.block_sums([1, 2, 3, 4, 5], 2) == [3, 7]

    def test_names_are_canonical(self):
        rule = (("move_3d", 0), ("move_1d", 2))
        assert S.rule_label(rule) == "move_1d[2] & move_3d[0]"
        assert S.column_name("short", 0.2, 0.1, 14, rule) == "short +20/-10 14d move_1d[2] & move_3d[0]"
