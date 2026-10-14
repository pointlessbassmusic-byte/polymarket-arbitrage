# I Built an INSANELY Profitable Claude AI Trading Bot (Full Guide), by Trading with DaviddTech

- **Creator / category:** Trading with DaviddTech (a trading-education channel). User category: Trading modeling. Link: https://youtu.be/0rzXU-BlKCg
- **Date researched:** 2026-10-14. **Coverage confidence:** 0.30. Title and channel confirmed via oEmbed; the transcript, description and any companion post were not reachable, and web search returned only similar guides by other creators (Miles Deutscher's "Claude + MCP + exchange" architecture; an anonymous Notion paper-trading guide). The architecture below is what such guides share; the profitability claim in the title is treated as unverified by construction. Written by Mandel directly because the delegated learner could not run.

## What it says (reconstructed from the genre)

- A build guide for an LLM-driven trading bot: Claude as the decision layer; a connector (MCP server, exchange API or broker SDK) to fetch prices and place orders; a strategy layer (indicators, a prompt that asks Claude to decide long/short/flat with a rationale); a "context brain" of notes and rules Claude reads each run; a trade ledger for memory; alerts via Telegram or Discord; a backtest or paper-trading phase before going live.
- The pitch is that Claude can read market context, apply rules and adapt, and that the resulting bot was very profitable over the creator's test window.
- Typical demonstration: a dashboard or equity curve over days or weeks, screenshots of trades, and a walkthrough of the prompt and code.

## Evidence quality

**Promotional.** The title asserts profitability without the information needed to assess it (sample size, costs, out-of-sample period, number of variants tried). Guides in this genre are useful as architecture sketches and are not evidence of edge.

## What Mandel adopts

- **The architecture skeleton is fine as a child template:** data in, decision layer, risk gate that can veto, execution out, persistent ledger, alerts. Mandel's children can use it, with the gate and ledger owned by Mandel's engine rather than by the bot.
- **The genre's failure modes become Mandel's checklist** for any claimed result, including the children's: in-sample equity curves; no fee, slippage or spread model; survivorship (only the configuration that worked is shown); short windows in a single regime; look-ahead through indicators computed on closed candles but acted on earlier; undeclared number of prompt or parameter variants; paper-trading fills at mid price; no proper scoring of probabilities.
- **Prompt and code are parameters.** A Claude prompt that decides trades is a model with many free parameters; every edit is a trial that the deflated Sharpe ratio must count.

## What Mandel holds loosely or rejects

- The profitability claim, until a pre-registered, out-of-sample, cost-inclusive record exists.
- "Claude reads the market" as a mechanism: without a measured skill-versus-market score on resolved questions, it is a narrative.
- Live keys in a guide-built bot: Mandel's principle 13 applies; nothing from this genre reaches live money without the gate and the user.

## Design implications for the RSI predictive substrate

- A `claims_checklist` applied to every child report that asserts performance: window, regime count, costs modelled, out-of-sample flag, trials declared, scoring rule; missing items lower the report's channel reliability (01's noisy-channel idea).
- Child template repo layout mirroring the genre's good parts (decision, risk gate, execution, ledger, alerts) with Mandel's `ForecastBook` and `ProposalBook` as the ledger and gate.
- Metrics: fraction of child claims that arrive with the checklist complete; gap between claimed and gate-measured performance per child (the "demon accounting" of resource 01).

## Cross-links to other provided resources

- 12, 13 (AI Pathways): the sober version of the same workflow, with backtesting discipline and walk-forward testing; read those for method, this one for the failure modes.
- 04 (RSI): a bot that edits its own prompt from results is a tiny RSI loop with no gate; A1 (DGM) shows what the gate must look like.
- 11 (Markov): memorylessness is the null hypothesis such bots must beat.
- A5 (Halawi): the honest benchmark, the crowd or market price, that this genre never reports against.

## Sources used

- YouTube oEmbed metadata for 0rzXU-BlKCg (title, channel)
- Web search results for the genre: https://youmind.com/ar/landing/x-viral-articles/ai-crypto-trading-bot-claude (Miles Deutscher's architecture); an anonymous Notion paper-trading guide; neither is this video
