from cryptobot import crossvenue_recorder as C


def test_fee_rounding_and_locked_edge():
    # Kalshi rounds its fee up to the cent per order: 10 contracts at 0.50 -> 0.175 -> 0.18
    assert C.kalshi_fee(0.50, 10) == 0.18
    assert abs(C.pm_fee(0.50, 10) - 0.17375) < 1e-9
    # Kalshi YES ask 0.40, Polymarket YES bid 0.50: YES there + NO here costs 0.40 + 0.50 = 0.90 before fees
    a, b = C.edges(k_bid=0.39, k_ask=0.40, p_bid=0.50, p_ask=0.52)
    fees = (C.kalshi_fee(0.40) + C.pm_fee(0.50)) / 10
    assert abs(a - (0.10 - fees)) < 1e-9
    assert b < 0                                   # 0.52 + (1 - 0.39) > 1


def test_match_maps_polymarket_slugs_to_kalshi_tickers():
    ms = [{"slug": "cpc-btc-above-day-2026-10-14-75750"}, {"slug": "cpc-btc-above-hr-2026-10-14-1600z-91800"},
          {"slug": "cpc-btc-above-wk-2026-10-16-64000"}, {"slug": "cpc-btc-updown-15m-2026-10-14-1530z"},
          {"slug": "cpc-btc-range-day-2026-10-14-75750"}]
    got = {p["slug"]: p["ticker"] for p in C.match(ms)}
    assert got["cpc-btc-above-day-2026-10-14-75750"] == "KXBTCD-26OCT1417-T75749.99"
    assert got["cpc-btc-above-hr-2026-10-14-1600z-91800"] == "KXBTCD-26OCT1412-T91799.99"     # 16:00 UTC = 12:00 EDT
    assert got["cpc-btc-above-wk-2026-10-16-64000"] == "KXBTCD-26OCT1617-T63999.99"
    assert got["cpc-btc-updown-15m-2026-10-14-1530z"] == "KXBTC15M-26OCT141145-45"            # window 15:30-15:45 UTC
    assert "cpc-btc-range-day-2026-10-14-75750" not in got
