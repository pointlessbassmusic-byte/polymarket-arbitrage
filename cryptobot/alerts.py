"""Push notifications for the things a human must hear about.

One webhook URL (`CRYPTOBOT_ALERT_WEBHOOK`), posted as JSON with both a
Discord-style `content` and a Slack-style `text` field so either kind
of incoming webhook renders it. Only the real book and safety events
alert; the paper book's decisions stay in the journal. Sends are
fire-and-forget: a failing webhook never blocks or breaks trading.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx

from .book import Decision

logger = logging.getLogger(__name__)

ENV = "CRYPTOBOT_ALERT_WEBHOOK"


def wants(decision: Decision) -> bool:
    """Which journal entries deserve a push."""
    if decision.stage == "reconcile":
        return True
    if decision.book != "real":
        return False
    return decision.action in ("opened", "closed", "mismatch") or decision.stage == "execution"


def format_decision(desk: str, d: Decision) -> str:
    head = f"[{desk}] {d.action.upper()} {d.symbol}"
    if d.action == "opened":
        return f"{head}: ${d.size_usd:,.2f} @ {d.price_usd:.6g} — {d.reason}"
    if d.action == "closed":
        pnl = f" P&L {d.pnl_usd:+,.2f}" if d.pnl_usd is not None else ""
        return f"{head}: ${d.size_usd:,.2f} @ {d.price_usd:.6g}{pnl} — {d.reason}"
    return f"{head} ({d.stage}): {d.reason}"


class Alerter:
    def __init__(self, url: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        self.url = url if url is not None else os.environ.get(ENV, "")
        self._c = client or httpx.AsyncClient(timeout=10)
        self.sent = 0
        self.failed = 0
        self._tasks: set[asyncio.Task] = set()

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    async def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        try:
            r = await self._c.post(self.url, json={"content": text[:1900], "text": text[:3000]})
            r.raise_for_status()
            self.sent += 1
            return True
        except Exception as exc:
            self.failed += 1
            # The webhook URL is the secret; httpx error messages embed it.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("alert webhook failed: %s%s", type(exc).__name__,
                           f" (HTTP {status})" if status else "")
            return False

    def fire(self, text: str) -> None:
        """Schedule a send without awaiting it (from sync code paths)."""
        if not self.enabled:
            return
        try:
            task = asyncio.get_running_loop().create_task(self.send(text))
        except RuntimeError:                       # no loop: nothing to schedule on
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def hook(self, desk: str):
        """A DecisionJournal on_record callback for one desk."""
        def _on(d: Decision) -> None:
            if wants(d):
                self.fire(format_decision(desk, d))
        return _on

    async def close(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._c.aclose()
