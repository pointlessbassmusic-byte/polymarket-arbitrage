"""
Options engine: pricing, Greeks, implied volatility and multi-leg payoffs, numpy only.
=====================================================================================

``bs`` prices European options under Black-Scholes-Merton with a continuous yield (dividends, or the
funding / interest-rate carry for crypto). ``payoff`` evaluates any multi-leg position at expiry and
reports max profit, max loss and breakevens on a grid. Strategy templates (``strategies.py``) turn a
rule like "short call OTM 5%" into concrete legs given spot, IV and time, so a backtest can price a
whole strategy from an underlying series and a volatility index. Model-priced results are labelled
as such everywhere: they test the logic of a strategy, not the market's actual option prices.
"""
