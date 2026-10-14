"""
Point-in-time data layer.
=========================

Every observation Mandel stores carries two timestamps: ``observed_at`` (when
the world produced it) and ``available_at`` (when Mandel could have known
it). A backtest or a forecast may use a row only if ``available_at`` is at
or before the decision time. This is the buildable form of "the substrate
holds all that was, is and will be": the past is reconstructible exactly as
it was knowable at any instant, and the future is the set of forecasts not
yet resolved.

Modules
-------
- ``store``        the observation store (gzip JSONL bundles via the archive, plus
                   in-memory frames) and the point-in-time filter
- ``polymarket``   fetchers for resolved markets (Gamma) and price histories (CLOB)
- ``kalshi``       fetchers for settled markets and candlesticks
"""
