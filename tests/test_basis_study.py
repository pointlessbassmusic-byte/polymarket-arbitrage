import pytest

from cryptobot import basis_study as B

D = B.DAY


class TestPriceTrades:
    def test_hedged_move_has_zero_basis(self):
        spots = {"A": {0: 1.0, 10 * D: 2.0}}
        perps = {"A": {0: 1.0, 10 * D: 2.0}}
        rows = B.price_trades([{"coin": "A", "entry": D, "exit": 11 * D, "funding": 0.01}],
                              spots, perps)
        assert rows[0]["basis"] == pytest.approx(0.0)
        assert rows[0]["move"] == pytest.approx(1.0) and rows[0]["days"] == 10

    def test_perp_outrunning_spot_costs_the_short(self):
        spots = {"A": {0: 1.0, 5 * D: 1.10}}
        perps = {"A": {0: 1.0, 5 * D: 1.13}}
        rows = B.price_trades([{"coin": "A", "entry": D, "exit": 6 * D, "funding": 0.0}],
                              spots, perps)
        assert rows[0]["basis"] == pytest.approx(-0.03)

    def test_uses_closes_at_the_entry_and_exit_instants(self):
        spots = {"A": {0: 1.0, D: 50.0, 4 * D: 1.0}}
        perps = {"A": {0: 1.0, D: 50.0, 4 * D: 1.0}}
        rows = B.price_trades([{"coin": "A", "entry": D, "exit": 5 * D, "funding": 0.0}],
                              spots, perps)
        assert rows[0]["move"] == pytest.approx(0.0)       # day-1 spike is inside the hold

    def test_missing_prices_drop_the_trade(self):
        assert B.price_trades([{"coin": "A", "entry": D, "exit": 3 * D, "funding": 0.0}],
                              {"A": {0: 1.0}}, {"A": {0: 1.0, 2 * D: 1.0}}) == []


class TestCollisions:
    def test_flags_two_assets_sharing_a_ticker(self):
        spots = {"LIT": {0: 0.12, D: 0.13}, "A": {0: 1.001, D: 0.999}}
        perps = {"LIT": {0: 3.9, D: 3.7}, "A": {0: 1.0, D: 1.0}}
        bad = B.collisions(spots, perps)
        assert set(bad) == {"LIT"} and bad["LIT"] < 0.05

    def test_k_coins_are_compared_per_thousand(self):
        assert B.collisions({"kPEPE": {0: 1e-5}}, {"kPEPE": {0: 0.01}}) == {}


class TestSummary:
    def test_net_charges_fees_on_every_trade(self):
        rows = [{"funding": 0.02, "basis": 0.0}, {"funding": 0.005, "basis": -0.001}]
        s = B.summary(rows, round_trip=0.008)
        assert s["net_mean"] == pytest.approx((0.012 + -0.004) / 2)
        assert s["net_positive"] == 1
