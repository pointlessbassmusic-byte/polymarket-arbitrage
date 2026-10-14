# A Multifractal Model of Asset Returns (MMAR), and its estimable successor

- **Authors / kind:** Benoit Mandelbrot, Adlai Fisher, Laurent Calvet. Cowles Foundation Discussion Paper 1164, September 1997 (paper). Read together with Calvet & Fisher, "Regime-Switching and the Estimation of Multifractal Processes" (2002, the Markov-switching multifractal, MSM) and Segnon & Lux, "Multifractal Models in Finance: Their Origin, Properties, and Applications" (Kiel Working Paper 1860, 2013).
- **Links:** https://cowles.yale.edu/sites/default/files/2022-08/d1164.pdf (scanned) · companion DM/USD paper DP 1166 https://cowles.yale.edu/sites/default/files/2022-08/d1166.pdf · MSM https://archive.nyu.edu/bitstream/2451/26508/2/02-64.pdf · survey https://www.kielinstitut.de/fileadmin/Dateiverwaltung/IfW-Publications/fis-import/1d3c070d-ffc2-4240-8a44-afb68d936acc-KWP_1860.pdf
- **Date researched:** 2026-10-14. **How much was read:** the 1997 PDF is a scan with no extractable text, so the model is reconstructed from the survey's section 3.2.1.1 (read in full), the MSM paper's abstract, introduction and model section (read), and general knowledge of the companion DM/USD paper. Numbers attributed to the DM/USD study below are from memory of that companion paper and are marked as such.
- **Selected as A4 because:** this is the namesake's own model of markets. It turns "fractal markets" from a slogan into a falsifiable scaling test, and its history (unestimable original, estimable successor) is itself a lesson for Mandel.

## What it says

- **Subordination.** Returns follow a compound process r(t) = B_H[θ(t)]: a fractional Brownian motion with Hurst index H, evaluated not in clock time but in "trading time" θ(t), the cumulative distribution function of a multifractal measure. Trading time stretches when the market is active and compresses when it is quiet, so volatility clustering and fat tails both come from θ(t), while the Brownian part stays homogeneous. With H = 0.5 the process is a martingale, matching standard asset-pricing assumptions.
- **The multifractal measure** is built by a multiplicative cascade: split the interval, allocate random fractions of mass to the halves (binomial, lognormal, Poisson or gamma multipliers with mean preserved), repeat k times. In the limit the measure is multifractal: different moments scale with different exponents.
- **Scaling law.** For a multifractal process, E|X(t + Δt) − X(t)|^q = c(q) Δt^{τ(q)+1}. For Brownian motion τ(q) = q/2 − 1 (a straight line in q); for a multifractal, τ(q) is strictly concave. The scaling function of returns inherits that of trading time through τ_r(q) = τ_θ(qH), and the spectrum through f_r(α) = f_θ(α/H).
- **The test.** Compute the partition function S_q(T, Δt) = Σ_i |X(t_i + Δt) − X(t_i)|^q over a range of Δt and q; log S_q against log Δt should be linear in Δt for each q; the slopes give τ(q); concavity of the estimated τ(q) is the fingerprint of multifractality. The survey calls this "a new stylized fact".
- **What it explains:** fat tails without infinite variance (unlike Mandelbrot's 1963 stable-law proposal), volatility clustering, long memory in absolute returns, and moment scaling across horizons, all from one mechanism. The companion paper applied it to Deutschemark/US dollar rates from 1973 to 1996 and reported (from memory, unverified here) near-linear log-log scaling over roughly two hours to six months and an estimated H close to 0.5.
- **What went wrong with it (survey, section 3.2.1.1):** the grid-bound cascade makes θ(t) combinatorial and non-stationary (it lives on a bounded interval and is not causal), so the MMAR cannot be estimated by likelihood or used for forecasting in a standard way. Fitting τ(q) and f(α) is unreliable: Lux (2004) found that even randomised data produce nonlinear τ and f estimates, and Ossiander and Waymire (2000) showed slow convergence of their variance. "MMAR has not been pursued further in subsequent literature."
- **The successor (Calvet & Fisher 2001, 2002, 2004):** the Markov-switching multifractal. Volatility is a product of k Markov multipliers, each switching at its own frequency; switching probabilities follow γ_k = 1 − (1 − γ_1)^{b^{k−1}}, so frequencies form a geometric progression. With binomial multipliers the state space has 2^k states and only four parameters; the likelihood is in closed form via a Bayesian filter, so maximum likelihood works. On exchange rates it fits better than GARCH(1,1) in sample for all currencies and "substantially outperforms GARCH(1,1) at longer horizons": for the British pound the 50-day forecasting R² is 27.3% against −2.6% for GARCH(1,1). MS-GARCH fits better in sample but loses out of sample, which the authors read as overfitting.

## Evidence quality

**Rigorous** for the MSM (likelihood estimation, Monte Carlo finite-sample checks, in- and out-of-sample comparisons against named benchmarks, Vuong tests) and **mainstream-educational** for the MMAR itself, whose empirical support rested on scaling plots that later work showed to be weak discriminators. Mandel's own reading of the 1997 text is indirect.

## What Mandel adopts

- **Multifractality as a test, not a belief.** When Mandel claims structure in a price series, it runs the partition-function test over at least two decades of Δt, reports τ(q) with a bootstrap band, and compares against a shuffled-series null, because Lux showed the unshuffled plot alone proves little.
- **Prefer the estimable model.** The MSM is the version of Mandelbrot's idea that can be fitted, scored and forecast; Mandel implements the k-component volatility filter (k of 5 to 8 is tractable in numpy) as a volatility and regime feature, and tests it the same way as any other proposal.
- **One mechanism for several stylized facts beats one patch per fact.** Fat tails, clustering and long memory from a single cascade is the kind of parsimony Mandel should look for in its own models and in the children's.
- **Longer horizons are where structure shows.** The MSM's edge over GARCH grows from one day to fifty; Mandel's own multi-scale consistency test (ORIGINAL-IDEAS #3) should expect edges to be clearest at the coarser scales, not the finest.
- **The history is the lesson.** A beautiful model that cannot be estimated is a hypothesis without a gate. Every model Mandel adopts must come with its estimator and its out-of-sample score.

## What Mandel holds loosely or rejects

- Exact self-similarity or a fixed Hurst exponent for prediction-market prices: these series are bounded in [0, 1], event-driven and resolve, so scaling can only hold over limited ranges and must be measured, not assumed.
- Hurst or τ(q) estimates on short windows as trading signals: finite-sample bias and variance are large (survey section 2.4; Weron 2002 on confidence intervals), so they are diagnostics with intervals, never bare numbers.
- The "fractal markets" rhetoric (Peters) as settled science: the testable content is the scaling function and the MSM's forecasting record, nothing more.

## Design implications for the RSI predictive substrate

- `mandel/validation/scaling.py` (planned): `partition_function(x, qs, dts)`, `tau_q(...)` with bootstrap bands, `shuffle_null(...)`, and a `multifractality_report` that states whether concavity survives the null. Used as a diagnostic in the gate, never as a pass criterion on its own.
- `mandel/models/msm.py` (planned): binomial MSM with k components, closed-form filter and likelihood, `fit`, `forecast_variance(h)`; registered with a scorer (log score of realised variance at horizons 1, 5, 10, 50) so it can be gated.
- Forecast-book integration: MSM-implied uncertainty as a feature for sizing (ORIGINAL-IDEAS #4) and as the dispersion baseline for the children's disagreement signal (#5).
- Metrics: τ(q) concavity statistic with interval; MSM out-of-sample variance R² by horizon versus a GARCH(1,1) baseline; fraction of markets where multifractality survives the shuffled null.

## Cross-links

- 16 (Hubbard, Mandelbrot set) and 15 (3Blue1Brown, fractal dimension): the same author's roughness programme applied to time rather than to the plane; 15's lesson that dimension is a measured exponent is exactly the τ(q) attitude.
- 08, 09 (iterated function systems): the multiplicative cascade is an IFS on measures; 09's warning not to import IFS formulas into price modelling by analogy applies.
- 11 (Veritasium, Markov): the MSM is a Markov chain with 2^k states; the successor to Mandelbrot's model is Markov's idea.
- 12, 13, 14 (Claude trading videos): volatility regime features and horizon-dependent edges are what those workflows should be testing for.
- A5 (Halawi): the speed at which information decays into price is a scaling question; A1/A2: the MSM is a candidate "evolve-block" with a clean evaluator.

## Sources used

- Segnon & Lux (2013), Kiel WP 1860, sections 2.4 and 3.2.1.1 (text extracted from the PDF)
- Calvet & Fisher (2002), NYU Stern WP 02-64, abstract, introduction and section 2 (text extracted from the PDF)
- Mandelbrot, Fisher & Calvet (1997), Cowles DP 1164 (scanned; not readable here); Fisher, Calvet & Mandelbrot (1997), Cowles DP 1166 (companion, from memory)
- https://cowles.yale.edu/node/145456 (abstract)
