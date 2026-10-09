import io
import json

from cryptobot import taxlots as TL


def test_lots_from_real_book_and_venue_fees(tmp_path):
    (tmp_path / "cryptobot_real_portfolio.json").write_text(json.dumps({"closed": [
        {"symbol": "DOGE", "side": "short", "entry_price": 0.10, "exit_price": 0.08, "size_usd": 1000.0,
         "opened_at": 1_760_000_000, "closed_at": 1_760_500_000, "costs_usd": 1.2, "funding_usd": 0.3,
         "pnl_usd": 199.1, "exit_reason": "take_profit"},
        {"symbol": "kSHIB", "side": "short", "entry_price": 0.005, "exit_price": 0.0055, "size_usd": 50.0,
         "opened_at": 1_700_000_000, "closed_at": 1_700_100_000, "costs_usd": 0.5, "funding_usd": 0.0,
         "pnl_usd": -5.5, "exit_reason": "stop_loss"}]}))
    (tmp_path / "execution.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"ts": 1_760_000_100, "kind": "fill", "book": "real", "coin": "DOGE", "side": "short", "fee_actual": 0.41},
        {"ts": 1_760_500_100, "kind": "fill", "book": "real", "coin": "DOGE", "side": "close", "fee_actual": 0.33},
        {"ts": 1_760_000_200, "kind": "fill", "book": "sim", "coin": "DOGE", "side": "short", "fee_actual": 9.9}]))
    rows = TL.lots(tmp_path, venue="kalshi")
    assert [r["coin"] for r in rows] == ["kSHIB", "DOGE"]                       # sorted by close time
    doge = rows[1]
    assert doge["quantity"] == 10_000.0 and doge["proceeds_usd"] == 1000.0 and doge["cost_basis_usd"] == 800.0
    assert doge["fees_venue_usd"] == 0.74 and doge["net_pnl_usd"] == 199.1 and doge["venue"] == "kalshi"
    assert rows[0]["fees_venue_usd"] == ""                                       # no venue fee logged
    assert TL.lots(tmp_path, year=2025) and all(r["closed_utc"].startswith("2025") for r in TL.lots(tmp_path, year=2025))
    buf = io.StringIO()
    TL.write_csv(rows, buf)
    assert buf.getvalue().splitlines()[0] == ",".join(TL.FIELDS)
