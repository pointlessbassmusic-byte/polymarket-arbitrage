import json
import time

import pytest

from cryptobot import execlog as X
from cryptobot.execution.perp_exchange import Fill, PerpExecConfig, PerpExecutor
from cryptobot.models import Side, Signal, SignalType
from cryptobot.perp_bot import CHAIN, PerpBot, PerpBotConfig, ReplayClient, slot_risk
from cryptobot.protections import ProtectionConfig


def test_slippage_sign_is_adverse_positive():
    assert X.slippage_bps("short", 0.100, 0.099) == pytest.approx(100.0)   # sold lower: cost
    assert X.slippage_bps("short", 0.100, 0.101) == pytest.approx(-100.0)  # sold higher: gain
    assert X.slippage_bps("close", 0.100, 0.101) == pytest.approx(100.0)   # covered higher: cost


def test_log_writes_jsonl_and_summarises(tmp_path):
    log = X.ExecutionLog(tmp_path / "execution.jsonl")
    log.fill(book="real", coin="DOGE", side="short", contracts=2, qty=10_000, intended=0.10, filled=0.0995,
             notional=995.0, fee_modelled=0.50, fee_actual=0.52, order_id="o1")
    log.fill(book="real", coin="kSHIB", side="close", contracts=1, qty=10_000, intended=0.005, filled=0.00502,
             notional=50.2, fee_modelled=0.20, fee_actual=None)
    log.funding(book="real", coin="DOGE", rate_hourly=1e-5, hours=1.0, notional=995.0, usd=0.00995)
    log.margin(balance={"total_usd_balance": 1000.0, "available_margin": 50.0})
    log.skip(book="real", coin="kPEPE", stage="sizing", reason="too small", size=300.0)
    rows = X.load(tmp_path / "execution.jsonl")
    assert [r["kind"] for r in rows] == ["fill", "fill", "funding", "margin", "skip"]
    s = X.summary(rows)
    assert s["fills"] == 2 and s["slippage_bps_by_coin"]["DOGE"] == [pytest.approx(50.0)]
    assert s["fee_actual"] == pytest.approx(0.52) and s["fee_modelled_matched"] == pytest.approx(0.50)
    assert s["funding_usd_by_coin"]["DOGE"] == pytest.approx(0.00995)
    assert s["margin_peak"] == pytest.approx(0.95) and s["margin_over_90"] == 1 and s["skips"] == 1
    text = X.render(s)
    assert "DOGE: slippage mean +50.0 bp" in text and "charged $0.52 vs modelled $0.50" in text
    assert "peak usage 95%" in text
    assert X.digest_line(tmp_path / "execution.jsonl", 0.0).startswith("execution: 2 real fills")


def test_disabled_log_is_a_no_op():
    log = X.ExecutionLog(None)
    assert log.record("fill", x=1) is None and not log.enabled
    assert X.digest_line(None, 0.0) == ""


class _Exec(PerpExecutor):
    """Armed executor that fills 1% worse than asked and reports a fee."""
    def __init__(self):
        super().__init__(PerpExecConfig())
        self._armed = True

    async def open_short(self, coin, notional, mid):
        return Fill(coin, "short", notional / mid, mid * 0.99, order_id="o1", fee_usd=0.41)

    async def close(self, coin, qty, mid):
        return Fill(coin, "close", qty, mid * 1.01, order_id="o2", fee_usd=0.42)

    async def balance(self):
        return {"total_usd_balance": 1000.0, "available_margin": 400.0}


@pytest.mark.asyncio
async def test_real_fills_funding_and_margin_are_logged(tmp_path, monkeypatch):
    cfg = PerpBotConfig(coins=("DOGE",), state_dir=tmp_path, contract_units={"DOGE": 5000.0},
                        taker_fee=0.0005, min_fee_per_lot=0.20)
    risk = slot_risk({}, 3000.0, 1)
    client = ReplayClient({})
    bot = PerpBot(cfg, risk, risk, ProtectionConfig(), PerpExecConfig(), client=client, executor=_Exec())
    bot.mode = "real"
    sig = Signal(ts=time.time(), type=SignalType.BOUNCE_SHORT, key=f"{CHAIN}:DOGE", chain=CHAIN,
                 symbol="DOGE", side=Side.SHORT, price_usd=0.10, confidence=0.35,
                 expected_move=0.20, stop_loss_pct=0.10, take_profit_pct=0.20, reason="t",
                 risk_reward=2.0, liquidity_usd=5e6)
    await bot._consider(bot.books["real"], sig)
    client.mids = {"DOGE": 0.098}
    client.funding = {"DOGE": 1e-5}
    await bot.monitor()                                # funding accrual + margin snapshot
    client.mids = {"DOGE": 0.115}                      # stop breached -> close at 1% worse
    await bot.monitor()
    rows = X.load(tmp_path / "execution.jsonl")
    kinds = [r["kind"] for r in rows]
    assert kinds.count("fill") == 2 and "funding" in kinds and "margin" in kinds
    opened = next(r for r in rows if r["kind"] == "fill" and r["side"] == "short")
    assert opened["slippage_bps"] == pytest.approx(100.0) and opened["fee_actual"] == 0.41
    assert opened["contracts"] == pytest.approx(6.0)                 # $3,000 slot / $500 contract
    assert opened["fee_modelled"] == pytest.approx(max(opened["notional"] * 0.0005, 6 * 0.20))
    closed = next(r for r in rows if r["kind"] == "fill" and r["side"] == "close")
    assert closed["slippage_bps"] == pytest.approx(100.0)
    assert next(r for r in rows if r["kind"] == "margin")["usage"] == pytest.approx(0.6)
    # the paper book never writes to the execution log
    assert all(r.get("book") in (None, "real") for r in rows)


@pytest.mark.asyncio
async def test_dry_run_fills_are_not_logged(tmp_path, monkeypatch):
    monkeypatch.delenv("CRYPTOBOT_ARM_LIVE", raising=False)
    cfg = PerpBotConfig(coins=("DOGE",), state_dir=tmp_path)
    risk = slot_risk({}, 1000.0, 1)
    bot = PerpBot(cfg, risk, risk, ProtectionConfig(), PerpExecConfig(),
                  client=ReplayClient({}), executor=PerpExecutor(PerpExecConfig()))
    sig = Signal(ts=time.time(), type=SignalType.BOUNCE_SHORT, key=f"{CHAIN}:DOGE", chain=CHAIN,
                 symbol="DOGE", side=Side.SHORT, price_usd=0.10, confidence=0.35,
                 expected_move=0.20, stop_loss_pct=0.10, take_profit_pct=0.20, reason="t",
                 risk_reward=2.0, liquidity_usd=5e6)
    await bot._consider(bot.books["sim"], sig)
    assert not (tmp_path / "execution.jsonl").exists()
