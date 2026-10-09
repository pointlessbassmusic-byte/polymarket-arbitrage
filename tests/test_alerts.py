import asyncio

import pytest

from cryptobot import alerts
from cryptobot.book import Decision, DecisionJournal


class FakeHttp:
    def __init__(self, fail=False):
        self.posts = []
        self.fail = fail

    async def post(self, url, json):
        self.posts.append((url, json))
        class R:
            def raise_for_status(_):
                if self.fail:
                    raise RuntimeError("500")
        return R()

    async def aclose(self):
        pass


def dec(**kw):
    base = dict(ts=1.0, book="real", symbol="DOGE", chain="hyperliquid", signal_type="bounce_short",
                action="opened", reason="r", size_usd=500.0, price_usd=0.1)
    return Decision(**{**base, **kw})


def test_wants_only_real_and_safety_events():
    assert alerts.wants(dec())
    assert alerts.wants(dec(action="closed", pnl_usd=3.0))
    assert alerts.wants(dec(action="halted", stage="execution"))
    assert alerts.wants(dec(book="sim", action="mismatch", stage="reconcile"))
    assert not alerts.wants(dec(book="sim"))
    assert not alerts.wants(dec(action="skipped", stage="cooldown"))


@pytest.mark.asyncio
async def test_journal_hook_posts_discord_and_slack_fields():
    http = FakeHttp()
    a = alerts.Alerter(url="https://hooks.example/x", client=http)
    j = DecisionJournal()
    j.on_record.append(a.hook("bounce"))
    j.record(dec(action="closed", pnl_usd=-12.5, reason="stop_loss"))
    j.record(dec(book="sim"))
    await a.close()
    assert len(http.posts) == 1
    body = http.posts[0][1]
    assert body["content"] == body["text"]
    assert body["content"].startswith("[bounce] CLOSED DOGE") and "P&L -12.50" in body["content"]
    assert a.sent == 1


@pytest.mark.asyncio
async def test_webhook_failure_is_counted_not_raised():
    a = alerts.Alerter(url="https://hooks.example/x", client=FakeHttp(fail=True))
    assert await a.send("hi") is False and a.failed == 1


def test_disabled_without_url(monkeypatch):
    monkeypatch.delenv(alerts.ENV, raising=False)
    a = alerts.Alerter(client=FakeHttp())
    assert not a.enabled
    a.fire("x")          # no loop, no url: silently nothing
