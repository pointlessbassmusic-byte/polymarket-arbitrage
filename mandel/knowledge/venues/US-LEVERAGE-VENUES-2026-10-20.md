# US-legal leveraged venues with bot APIs, as of 2026-10-20

Scope: a US-resident retail individual with $1k-$10k who wants API-driven futures, Treasuries, FX, ETFs and leveraged crypto.
Method: web research on 2026-10-20. Where a fact comes only from a secondary or competitor source, or I could not confirm it for 2026, the table says so ("unverified").
Several primary pages could not be fetched: IBKR commissions (403), CME spec pages (503), Coinbase futures page (403) and Bybit terms (503).

**The big change in 2026.** On 2026-05-29 the CFTC let Kalshi list a true BTC perpetual as a *futures* contract. It also gave Coinbase Financial Markets (CFM) a no-action position to route US customers to Deribit perps, treating them as "foreign futures". Onshore US perps now exist at Kalshi, Coinbase, Kraken/Bitnomial and (rolling out) Robinhood. Their leverage is about 3-10x, not 40x.
On 2026-06-18 CME sued the CFTC to vacate the Kalshi approval and the policy statement. I found no ruling, so that case is pending risk to all of the above.
Sources: [The Block](https://www.theblock.co/post/403040/cftc-opens-door-for-crypto-perpetual-future-contracts-in-us-as-coinbase-kalshi-move-forward), [Cahill](https://www.cahill.com/publications/client-alerts/2026-06-02-true-perpetuals-come-onshore), [Akin](https://www.akingump.com/en/insights/alerts/cftc-advances-framework-for-perpetual-contracts-and-247-markets), [CME suit (The Block)](https://www.theblock.co/post/405286/cme-sues-cftc-over-perpetual-futures-us-accusing-agency-suddenly-changing-course), [Crowdfund Insider](https://www.crowdfundinsider.com/2026/06/286519-cme-group-files-lawsuit-against-cftc-over-perpetual-futures-approvals-alleging-abrupt-regulatory-shift/).

---

## 1. CME micro futures through a broker with an API

Margins are NinjaTrader's table dated 2026-08-31 (overnight "Initial" is about the exchange margin; "Day" is the broker's intraday margin). They are representative of discount FCMs. IBKR, Schwab and tastytrade generally charge the full exchange margin, or close to it, intraday.
Source: [NinjaTrader margins](https://ninjatrader.com/pricing/margins/).

| Contract | Size | Day margin (NT) | Overnight initial | Rough notional (price assumed) | Implied overnight leverage |
|---|---|---|---|---|---|
| MES | $5 × S&P 500 | $50 | $2,863 | ~$33k (SPX ~6,600, assumed) | ~11x |
| MNQ | $2 × NDX | $100 | $4,647 | ~$48k (NDX ~24k, assumed) | ~10x |
| M2K | $5 × RTY | $50 | $1,226 | ~$12k (assumed) | ~10x |
| MYM | $0.50 × Dow | $50 | $1,699 | — | — |
| MGC | 10 oz gold | $200 | $2,473 | 10 × gold price | ~10-15x |
| MCL | 100 bbl crude | $100 | $885 | ~$6k (~$60 oil, assumed) | ~7x |
| M6E | €12,500 | $50 | $231 | ~$14.5k | ~60x (exchange margin; NFA spot caps do not apply to futures) |
| 10Y (Micro 10-Yr Yield) | $10 per bp | $50 | $330 | DV01 $10 (about 1/7 of ZN's risk) | — |
| 2YY / 5YY / 30Y | $10 per bp | $50 | $363 / $341 / $297 | — | — |
| MTN (Micro Ultra 10-Yr Note) | 1/10 of TN (~$10k face) | $50 | $280.50 | ~$10k | ~35x |
| MWN (Micro Ultra Bond) | 1/10 of UB | $50 | $566.50 | ~$12k | — |
| MBT (Micro BTC) | 0.1 BTC | $100 | $1,884 | — | ~3-4x (CME crypto margins are high) |
| MET (Micro ETH) | 0.1 ETH | $50 | $81 | — | — |

Notional figures are approximate because I did not fetch October 2026 index levels.
**The $50 day margins mean about 600x intraday leverage on MES. Treat them as a risk to manage, not a feature.**

### Brokers

| Broker | API for bots | Micro commission (per side, ex exchange/NFA fees) | Account min | US-legal | Source / confidence |
|---|---|---|---|---|---|
| Interactive Brokers | TWS API (socket), Client Portal / Web API (REST), FIX. Free. | ~$0.25/contract fixed for micros (2024 Benzinga; IBKR page 403 today); standard $0.85 fixed, tiered $0.25-0.85 | $0 | Yes | [Benzinga](https://www.benzinga.com/money/interactive-brokers-for-futures-trading). Micro rate unverified for 2026. Margins are close to exchange level (a third party reports ~$1.6k intraday / $2.3k overnight on MES; unverified). |
| Tradovate | REST + WebSocket API | $0.39 Free plan / $0.29 ($99/mo) / $0.09 (lifetime $1,499) | Any amount for an account. API reportedly needs ≥$1,000 equity plus a $25/mo add-on; real-time API market data needs a CME sub-vendor licence (~$290+/mo). Orders work without the data licence. | Yes | [Tradovate pricing](https://www.tradovate.com/pricing/) (official). API terms are from a vendor blog ([pickmytrade](https://blog.pickmytrade.trade/tradovate-api-access-without-1000-minimum-2026-options/)) and a [Tradovate forum](https://community.tradovate.com/t/is-cme-sub-vendor-requirement-for-api-access-is-290-per-month/6215), so unverified officially. MES day margin $50. |
| NinjaTrader | No documented broker REST API on its pricing page. Automation is via NinjaScript (C#) in the desktop app; NT owns Tradovate, whose API is the usual route. | $0.39 / $0.29 / $0.09 (same plan structure) | No minimum ("any amount > $0") | Yes | [NinjaTrader pricing](https://ninjatrader.com/pricing/) |
| TradeStation | REST API (v3) | Micros ~$0.50 down to $0.25/side by volume, plus a ~$0.10 clearing fee (competitor and vendor sources). Standard $1.75 → $0 by volume. | API key reportedly needs a $10,000 balance (vendor blog, unverified) | Yes | [MetroTrade](https://www.metrotrade.com/tradestation-vs-metrotrade-futures-broker-comparison/), [pickmytrade](https://blog.pickmytrade.io/tradestation-review-2026-best-broker-for-automated-traders/). Unverified. |
| Schwab / thinkorswim | Trader API (developer.schwab.com). **Futures order placement via the API is not documented**; all sources describe equities and options only. The legacy TDA API explicitly excluded futures. | $2.25/contract/side (official) | $0 for brokerage; futures needs approval and margin | Yes, but **not bot-usable for futures** as far as I could verify | [Schwab futures](https://international.schwab.com/investment-products/futures-trading), [TradersPost](https://docs.traderspost.io/docs/core-concepts/brokers/tdameritrade) |
| Webull (Webull Futures LLC, an FCM) | Webull OpenAPI/CLI lists US futures trading (CME/CBOT/NYMEX/COMEX/CBOE). Futures market data via API is a paid subscription. | ~$0.25/side micros, ~$1.25 standard (review sites) | Not verified | Yes | [Webull CLI docs](https://developer.webull.com/apis/docs/AI-friendly-Resources/cli/), [Webull futures API (HK docs)](https://developer.webull.hk/apis/docs/trade-api/futures), [Finder](https://finder.com/investments/futures-trading-platforms). Commission unverified officially. |
| Robinhood (Robinhood Derivatives) | **No public futures API.** Its public API is spot crypto only. | $0.75/contract/side, $0.50 with Gold, + NFA $0.02 + exchange fees | — | Yes (app only) | [RHD fee schedule](https://cdn.robinhood.com/assets/robinhood/legal/RHD_Fee_Schedule.pdf), [Robinhood support](https://robinhood.com/us/en/support/articles/before-trading-a-futures-contract) |
| tastytrade | Open API (REST + streamer); the order schema accepts "Future" and "Future Option". Dry-run endpoint available. | $0.85/contract micros (official pricing page; some sites say $0.75) | $0 | Yes | [tastytrade pricing](https://www.tastyworks.com/pricing), [developer docs](https://developer.tastytrade.com/open-api-spec/orders/) |
| AMP Futures (Rithmic / CQG / TT) | Rithmic R\|API (~$100/mo, 2020 figure), CQG API, many third-party platforms | ~$0.60/side base for micros, + $0.20-0.70 exchange/clearing, + Rithmic $25/mo + $0.10/contract routing (older data) | $100 deposit | Yes | [AMP FAQ](https://faq.ampfutures.com/hc/en-us/articles/30202873125399-What-fees-are-associated-with-trading-at-AMP), [Optimus forum, 2020](https://community.optimusfutures.com/t/new-rithmic-pricing-12-01-20/3889). Unverified for 2026. |
| Alpaca | **No futures yet.** Alpaca Derivatives LLC registered as an FCM on 2026-08-17 for prediction markets (Kalshi event contracts); it "has not yet commenced regulated business". | — | — | n/a | [Alpaca blog](https://alpaca.markets/blog/alpaca-registers-as-futures-commission-merchant-with-the-cftc-and-nfa-to-advance-launch-of-prediction-markets/) |

Other notes:
- Schwab launched near-24/7 crypto futures on thinkorswim in June 2026 ([Schwab PR](https://pressroom.aboutschwab.com/press-releases/press-release/2026/Schwab-Announces-Latest-Round-of-Enhancements-to-Retail-Trading-Experience/default.aspx)).
- Exchange plus NFA fees on CME micros add roughly $0.20-0.40/side on top of the commissions above. I did not verify an exact 2026 figure.

## 2. Treasury futures

Contract specifications are standard CME specs. cmegroup.com returned 503 today, so these come from long-standing specs that were not re-fetched. Margins are from the NinjaTrader table above.

| Contract | Face / unit | Tick (value) | Overnight initial margin | Approx notional | Notional ÷ $5k account | US-legal |
|---|---|---|---|---|---|---|
| ZT 2-Yr | $200,000 | 1/8 of 1/32 ($7.8125) | $1,320 | ~$205k | ~41x | Yes |
| ZF 5-Yr | $100,000 | 1/4 of 1/32 ($7.8125) | $1,375 | ~$108k | ~22x | Yes |
| ZN 10-Yr | $100,000 | 1/2 of 1/32 ($15.625) | $2,062.50 | ~$110k | ~22x | Yes |
| ZB Bond | $100,000 | 1/32 ($31.25) | $4,070 | ~$115k | ~23x | Yes |
| UB Ultra Bond | $100,000 | 1/32 ($31.25) | $5,665 | ~$120k | ~24x | Yes |
| 2YY/5YY/10Y/30Y Micro Yield | $10 per bp of yield, cash-settled to BrokerTec benchmarks (launched Aug 2021) | 0.1 bp = $1 | ~$300-365 | DV01 $10. A 10 bp move = $100. | DV01 is 0.2% of $5k | Yes |
| MTN Micro Ultra 10-Yr / MWN Micro Ultra Bond | 1/10 of TN / UB | — | $280.50 / $566.50 | ~$10-12k | ~2-2.5x | Yes |

Sources: [Mondo Visione, micro yield launch](https://mondovisione.com/news/cme-group-to-launch-micro-treasury-yield-futures-micro-2-year-5-year-10-year-202169/) and the [CME MTN page](https://www.cmegroup.com/markets/interest-rates/us-treasury/micro-ultra-10-year-us-treasury-note.html).
- I found no new micro Treasury product launched in 2026.
- Full-size ZN's DV01 is roughly $65-80, so one ZN is roughly 7-8 micro 10Y contracts' worth of rate risk. That figure is my estimate, not from a source.
- **For $5k, the micro yield futures (or MTN/MWN) are the only Treasury contracts sized sensibly.** One ZN uses ~41% of the account in margin.

## 3. Retail spot FX for US persons

| Venue | Max leverage (NFA) | Cost on EUR/USD | API | Constraints | US-legal | Source |
|---|---|---|---|---|---|---|
| NFA rule (all US RFEDs/FCMs) | 50:1 majors (2% deposit), 20:1 others (5%) | — | — | FIFO; no hedging (same-pair opposite positions) | — | [CFTC 2010 final rule summary](https://hedgefundlawblog.com/?p=3751), [Euromoney](https://www.euromoney.com/article/b12kht4m12njyr/fx-news-cftc-releases-final-rules-covering-retail-fx). I did not fetch the current NFA rulebook text (Financial Req. §12 / Rule 2-43). |
| OANDA US | Up to 50:1 | Standard: spread only. Core: spreads from 0.0 plus $0.70 per 10k units per leg (≈$14 round trip per 100k); core needs a $10k deposit/balance. Financing is charged daily at the rollover rate; I did not verify current rates. | v20 REST + streaming, personal access token. Available to all OANDA divisions except OANDA Global Markets and TMS. | FIFO applies; hedging not available (except ECP); no minimum deposit | Yes | [OANDA leverage FAQ](https://help.oanda.com/us/en/faqs/account-types-and-leverage-us.htm), [core pricing](https://help.oanda.com/us/en/faqs/spreads-commission.htm), [v20 auth](https://developer.oanda.com/rest-live-v20/authentication) |
| FOREX.com (GAIN Capital / StoneX, NFA 0339826) | 50:1 / 20:1 (NFA) | Raw-spread account reportedly 0.0 pips + $7 per $100k; date unverified | REST API (City Index/GAIN "ciapi"), granted on request via customer service; FIX for institutions | FIFO / no hedging (NFA) | Yes | [FOREX.com API](https://forex.com/en-us/premium-trader-tools/api-trading), [CompareForexBrokers](https://www.compareforexbrokers.com/us/forex-com-review/) (unverified) |
| Interactive Brokers (IdealPro) | 50:1 majors / 20:1 others for US clients | 0.2 bp of trade value, $2 minimum per order (≈$4 round trip per 100k); orders under ~$25k route to odd-lot IDEAL with wider spreads | TWS / Web API | FIFO; small orders are expensive because of the minimum | Yes | [ForexBrokers.com](https://www.forexbrokers.com/reviews/interactive-brokers), [IBKR PDF (older, $2.50 min)](https://www.interactivebrokers.com/download/newMark/PDFs/commissionsForex.pdf) |
| CME FX futures (M6E etc.) | Exchange margin (~60x on M6E) | Futures commission + about 1 tick spread | Any futures API above | No FIFO / hedging rule issue | Yes | Section 1 |

## 4. US-legal leveraged crypto derivatives

| Venue / product | Assets | Max leverage (US retail) | Fees / funding | API | US-legal | Source |
|---|---|---|---|---|---|---|
| Coinbase Financial Markets: US "perpetual-style" nano futures (5-year expiry, hourly funding) | BTC-PERP, ETH-PERP at launch (Jul 2025); now ~15 contracts incl. major alts | Up to 10x | From 0.02% per contract, min $0.15; funding accrues hourly, settles twice daily | Advanced Trade API, `/cfm/*` endpoints (incl. intraday margin settings) | Yes | [CryptoSlate](https://cryptoslate.com/coinbase-starts-cftc-regulated-perpetuals-for-us-traders-offering-10x-leverage-and-0-02-fees/), [MarketsMedia](https://www.marketsmedia.com/coinbase-brings-perpetual-futures-to-u-s), [CDP futures guide](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/futures) |
| Coinbase: US perpetual-style equity index futures | Equity indices (index names not found) | Not found | Not found | Presumably `/cfm` (unverified) | Yes (launched 2026-06-08 per reports) | [The Defiant](https://thedefiant.io/converge/cefi/coinbase-perpetual-equity-index-futures-june-8-yclimy) |
| Coinbase → Deribit perps as "foreign futures" (CFTC no-action, 2026-05-29) | BTC, ETH, SOL, DOGE, etc. (Coinbase had not chosen at announcement) | **Not published; unverified.** Rollout status as of Oct 2026 unverified. | — | — | Yes via CFM once live | [Decrypt](https://decrypt.co/369504/coinbase-first-us-exchange-allowed-offer-global-crypto-perps-trading) |
| Kalshi perpetuals ("Timeless"; `KalshiEX` DCM, cleared by Kalshi Klear) | BTC (BTCPERP, approved 2026-05-29) plus ~17 alts; gold and silver added 2026-09-10 | BTC 6x (help center); ETH 4.6x, SOL 3.0x, BNB 4.7x, gold 15.2x, silver 7.7x (API data via gaming.net, Sep 2026) | Funding every 8h, capped ±2% per window (metals daily). 3.25% interest on margin cash (≥$250 avg). Trading fee schedule not found. Min position ~$1-8. | Yes: `/trade-api/v2/margin/*` REST, plus WebSocket and FIX. Separate margin account; must apply for perps access. | Yes | [Kalshi help](https://help.kalshi.com/en/articles/14679970-what-are-perpetual-futures), [docs.kalshi.com/margin](https://docs.kalshi.com/margin), [gaming.net](https://www.gaming.net/kalshi-adds-gold-and-silver-perpetual-futures-with-round-the-clock-trading/) |
| Kraken Derivatives US (perps listed on Bitnomial; Payward bought Bitnomial for up to $550M) | BTC, ETH, SOL, XRP, XLM, XTZ, SHIB and more; USD only | **Not found** ("varies by asset"). Kraken US *spot margin* is 10x. | Exchange + NFA + clearing fees + flat per-contract commission; funding every 8h (00/08/16 UTC) | Kraken API (US derivatives coverage not verified) | Yes (launched ~2026-06-15) | [Kraken support](https://support.kraken.com/gb/articles/us-perpetual-futures), [The Block](https://www.theblock.co/post/400247/kraken-launches-regulated-crypto-spot-margin-trading-us-bitnomial-deal) |
| Bitnomial direct | Perps via self-certification since 2024-25; leveraged retail spot since Dec 2025 | Homepage advertises "up to 6x" on margin trades; perp leverage unverified | — | Yes (exchange API) | Yes | [Bitnomial](https://bitnomial.com/), [Bitnomial news](https://bitnomial.com/news/2025-12-04/leveraged-retail-spot-exchange) |
| Robinhood perps (Robinhood Derivatives + Bitstamp) | BTC, ETH, SOL, XRP, DOGE, ADA, LINK, HYPE | BTC/ETH 10x, others 3x | 0.01% promo through end-2026; PnL settles every 15 min | **No public API for derivatives** | Yes, announced 2026-09-29; rollout status conflicting | [The Block](https://theblock.co/news/business/2026-09-29-robinhood-perps-trading-417242), [crypto.news](https://crypto.news/robinhood-plans-10x-crypto-perps-for-u-s-traders/) |
| Robinhood micro crypto futures (CME-listed / Robinhood) | BTC, XRP, SOL micros | Exchange margin | $0.50-0.75/side + fees | No API | Yes | [The Block](https://www.theblock.co/post/360167/robinhood-launches-micro-futures-contracts-for-xrp-and-solana) |
| CME crypto futures (MBT 0.1 BTC, MET 0.1 ETH; near-24/7 since 2026) | BTC, ETH, SOL, XRP | ~3-4x on MBT (margin $1,884 overnight) | Broker commissions | Any CME futures API (IBKR, Tradovate, etc.) | Yes | Section 1 margins |
| Polymarket US (DCM) | No perps listed | — | — | — | US DCM does **not** list perps. Polymarket's international perps (20x, launched 2026-09-03) **block US users.** | [Decrypt](https://decrypt.co/377483/polymarket-crypto-perpetual-futures), [The Defiant](https://thedefiant.io/news/defi/polymarket-opens-perps-trading-to-the-public-with-20x-leverage) |

**Bottom line:** the most leverage a US retail customer can get legally on crypto perps is about 10x on BTC/ETH (Coinbase, Robinhood). Kalshi offers 6x on BTC and less on alts. CME crypto margins work out to about 3-4x. **No US-legal venue offers 40x on crypto.**

## 5. Offshore and on-chain high-leverage venues

| Venue | Max leverage | US-person status | US-legal for a US resident? | Source |
|---|---|---|---|---|
| Hyperliquid | Up to 40x (some sources say 50x on BTC/ETH); per-asset caps | Terms label US persons "Restricted Persons"; the front-end blocks US IPs. Trump said in Aug 2026 he wants it brought in "compliantly"; Payward/Bitnomial is working with the CFTC on US perps *linked to* Hyperliquid markets. Not live. | **No** | [The Block, 2026-09-04](https://theblock.co/news/regulation/2026-09-04-trump-wants-hyperliquid-enter-us-how-it-could-happen-413594), [Buildix](https://www.buildix.trade/blog/hyperliquid-max-leverage-btc-eth-sol-all-pairs-2026), [HL docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining). I could not fetch the terms text itself. |
| dYdX | ~20-50x depending on market (not verified for 2026) | Foundation disclaimer: not available to US persons. The US spot launch (Dec 2025, reported) excludes perps. | **No** (perps) | [The Block](https://www.theblock.co/post/377073/dydx-enter-us), [BYDFi](https://www.bydfi.com/en-za/cointalk/dydx-revenue-protocol-fees-analysis-2026) (secondary) |
| GMX | Up to 100x (marketing) | I could not retrieve the terms. Same legal analysis applies: an unregistered swap/futures venue offering leveraged retail commodity transactions. | **Treat as No** (ToS unverified) | [DEX Screener listing copy](https://dexscreener.com/arbitrum/0x1aeedd3727a6431b8f070c0afaa81cc74f273882) |
| Bybit | Up to 100x+ | US is on the "Service Restricted Countries" list (Service Agreement §11.3) | **No** | [The Block](https://www.theblock.co/post/298758/bybit-seems-to-open-up-registration-and-authentication-to-chinese-users-report), [Datawallet 2026](https://www.datawallet.com/fr/crypto/bybit-pays-%C3%A0-acc%C3%A8s-restreint) |
| Binance.com | Up to 125x | Does not serve US persons. CFTC sued it in 2023 for serving US users who got past geoblocking with VPNs. Binance.US (terms updated 2026-06-05) is spot only; I found no futures there. | **No** | [Binance.US ToU](https://www.binance.us/en/terms-of-use), [CFTC/Binance coverage](https://www.unlock-bc.com/99271/cftc-files-lawsuit-against-binance-and-ceo-cz-for-violating-trading-regulations) |
| OKX | Up to 100x | OKX US launched spot in 2025; its perps (incl. 2026 equity perps) are geofenced from US users | **No** (perps) | [Blockhead](https://www.blockhead.co/2026/03/25/okx-adds-24-7-equity-perpetuals-in-crowded-push-to-trade-stocks-on-crypto-rails/), [OKX CFTC comment](https://comments.cftc.gov/Handlers/PdfHandler.ashx?id=35636) |
| Bitget | Up to 125x | US on its restricted list; no US entity | **No** | [gncrypto](https://www.gncrypto.news/news/can-you-use-bitget-in-the-us/), [bestguide](https://bestguide.com/review/bitget/) (secondary) |
| Polymarket international perps | 20x crypto/indices/commodities, 10x stocks | Blocks US users; redirects them to polymarket.us | **No** | [Decrypt](https://decrypt.co/377483/polymarket-crypto-perpetual-futures) |

**All of these are off-limits to US residents.** Using a VPN breaks the venue's terms; funds can be frozen and accounts closed. A bot that gets around a geoblock is exactly the conduct the CFTC cited against Binance.
The 2026 change does **not** open these venues. What it does is let a US FCM route customers to an affiliated foreign board of trade under Part 30, as Coinbase does with Deribit. I found no CFTC action that made Hyperliquid, Bybit, Binance, OKX or Bitget legal for US persons.
This also matches the repo's own compliance rule: "never add code that evades geoblocking".

## 6. ETF and margin alternatives (stock brokers incl. Alpaca)

| Instrument / feature | Effective leverage | Cost | API | US-legal | Source |
|---|---|---|---|---|---|
| Reg-T margin (Alpaca, IBKR, etc.) | 2x overnight. 4x intraday now from $2,000 equity: FINRA Rule 4210 change, SEC approval 2026-04-14, effective 2026-06-04, PDT $25k minimum abolished, brokers have until 2027-10-20 to implement. | Margin interest | Alpaca REST. The PDT fields (`pattern_day_trader`, `daytrade_count`, …) were removed by 2026-07-06. | Yes | [Alpaca blog](https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/), [Schwab](https://advisorservices.schwab.com/story/sec-approves-scrapping-25000-day-trader-minimum), [Alpaca margin docs](https://docs.alpaca.markets/docs/margin-and-short-selling) |
| 2x/3x ETFs: SSO/UPRO (S&P), QLD/TQQQ (NDX), TMF (3x 20+yr Treasuries), UBT, UGL (2x gold), TYD (3x 7-10yr) | 2-3x daily exposure, compounding decay; can be margined (Alpaca maintenance 50% on 2x, 75% on 3x) | Expense ratio ~0.9-1% plus decay | Any stock API (Alpaca, IBKR, tastytrade, Schwab Trader API) | Yes | [Alpaca margin docs](https://docs.alpaca.markets/docs/margin-and-short-selling). ETF tickers and expense ratios from general knowledge; not re-verified today. |
| Portfolio margin | ~6-7x on diversified books | — | — | Yes, but usually needs **$100k-$125k+** equity at IBKR/Schwab/tastytrade (general knowledge; not re-verified for 2026). Not reachable for $1-10k. | — |
| Alpaca futures / FX | **None.** No futures (FCM registered Aug 2026 for event contracts only), no spot FX. Crypto spot only, no crypto leverage. | — | — | — | [Alpaca FCM post](https://alpaca.markets/blog/alpaca-registers-as-futures-commission-merchant-with-the-cftc-and-nfa-to-advance-launch-of-prediction-markets/) |

---

## What a $5k US account can actually do

1. **Futures via API.** The best fits are IBKR (free TWS/Web API, $0 minimum, ~$0.25 + fees per micro, near-exchange margins) and tastytrade (Open API, $0.85 per micro). Tradovate is cheaper per contract, but its API needs ≥$1k plus $25/mo, and live data needs a CME licence. Webull's OpenAPI also lists futures. **Schwab's and Robinhood's APIs do not support futures.**
   - At exchange margins, $5k holds about 1 MES or 1 MNQ overnight (~$2.9k / $4.6k), 1-2 MGC, several MCL/M2K, or many micro yield contracts.
   - Keep effective notional ≤ ~2-3x the account. The $50 day margins allow 100x+ intraday, which is the fastest way to lose the account.
2. **Treasuries.** Use micro yield futures (10Y, 2YY, 5YY, 30Y: $10/bp, ~$330 margin) or MTN/MWN. One ZN is ~$110k notional (22x the account), and one ZT is ~$200k.
3. **FX.** Use OANDA US v20 (no minimum, 50:1 cap, FIFO, no hedging; core pricing needs $10k) or FOREX.com's REST API by request. Micro FX futures (M6E, $231 margin) via a futures API avoid FIFO.
4. **Leveraged crypto, US-legal.** The options are Coinbase CFM nano perps (≤10x, API), Kalshi perps (BTC 6x, alts 3-5x, API under `/margin`, apply for access), Kraken US perps via Bitnomial (leverage unverified), and Robinhood perps (10x BTC/ETH, no API). The best API choices are Coinbase and Kalshi.
   - **40x (Hyperliquid) and 100x+ (Bybit, Binance, OKX, Bitget, GMX) are not legally available to a US resident.** Their terms exclude US persons, and getting past the geoblock breaks those terms and risks seizure of funds.
   - The onshore perp framework is itself under legal challenge (CME v. CFTC, filed 2026-06-18, unresolved as far as I found).
5. **ETFs.** Alpaca or IBKR give 2x Reg-T overnight and 4x intraday from $2k equity (since the 2026 PDT repeal), plus 2-3x ETFs (UPRO, TQQQ, TMF, UGL). Portfolio margin is out of reach at $5k. Alpaca has no futures or FX.

**Still unverified:** IBKR's current micro commission; Kraken and Bitnomial perp leverage; whether Coinbase's Deribit access has gone live and at what leverage; Kalshi perp trading fees; Robinhood perps rollout status; GMX and Hyperliquid terms text (fetched pages were empty or blocked); exact 2026 CME/NFA fee pass-throughs; October 2026 index levels (the notional figures are approximate).

## Mandel's leverage arithmetic for its supported edges (2026-10-20, in-sample, before estimation error)

Growth-optimal (full Kelly) leverage L* = mean / variance per period, from the archived return streams:

| Edge | mean / sd per period | full-Kelly L* | log growth per period at 1x / L* / 10x / 40x (bps) | share of periods losing >100% at 40x |
|---|---|---|---|---|
| Overnight QQQ (T-549) | +2.6 / 80 bp per night | 4.1x | +2.3 / +5.1 / -12.6 / -1,422 | 0.9% |
| IBS SPY (T-332) | +16 / 148 bp per trade | 7.4x | +15 / +59 / +47 / -5,002 | 3.6% |
| Turn-of-month SPY (T-59) | +9 / 117 bp per day | 6.6x | +8 / +29 / +14 / -3,399 | 2.2% |
| Memecoin bounce-short (T-556) | +255 / 1,239 bp per trade | 1.7x | +181 / +223 / -51,952 / ruin | 42% |
| Treasury month-end (T-574, net 2 bp) | +10 / 44 bp per event | (decayed since 2024) | — | 0% |

Half Kelly or less is the usable range once estimation error is counted. Leverage multiplies size, never the edge: on every
supported equity and crypto edge 40x is ruinous, and the US-legal caps (Kalshi 6x BTC, Coinbase 10x, Reg-T 2x, micro
futures ~10x overnight) are already above what these edges can use.
