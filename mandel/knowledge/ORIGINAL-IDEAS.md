# Mandel's own ideas (v0, 2026-10-14)

The user asked Mandel not to copy but to create. These are design ideas that
go beyond the sources. Each is stated so it can be built and tested; each
names the resource it grew out of and what would show it is wrong. They are
candidates, not validated knowledge.

## 1. The substrate is bitemporal: "all that was, is and will be" as data

The user's framing is that the informational substrate holds everything that
has happened, is happening and will happen. The honest, buildable form of
that is a *bitemporal* store: every datum carries two timestamps, the moment
the world made it true (`valid_at`) and the moment Mandel could have known it
(`available_at`). "The past" is then reconstructible exactly as it was
knowable at any instant, which is what point-in-time backtesting needs. "The
future" is the set of pre-registered forecasts about events not yet
resolved; resolution moves each one from "will be" to "was" and scores it.
A forecast is a grain of sand Mandel has already isolated.

Grew out of: 01 (information is physical, conservation), 11 (Markov state),
AI Pathways 13 (look-ahead bias), MANDEL.md principle 9.
Falsified if: bitemporal reconstruction never changes a backtest result
compared with the naive version (then it is bookkeeping, not protection).

## 2. Mandel forecasts its own proposals: the idea market

Every improvement proposal gets a probability, assigned by Mandel before
pre-registration, that it will pass the gate. That probability is recorded in
the forecast book under source `mandel:self`, and scored like any other
forecast when the gate decides. Mandel therefore has a measured track record
of knowing what will work, and it is on the same scoreboard as the children
and the market. Over time, rejected proposals form a searchable memory of
negative results, and the base rate of success per idea class becomes a
prior for new ideas. The scoreboard will tell us whether Mandel is getting
better at choosing what to try, which is the only kind of recursive
self-improvement a session-bound model can honestly claim.

Grew out of: 04 (RSI needs a validation loop), 02 (what a field looks like
when it only keeps positive results), Tetlock-style calibration.
Falsified if: Mandel's Brier score on its own proposals does not fall over
the first fifty proposals, or is no better than the base rate.

## 3. Scale-consistent edge: a multifractal test for whether an edge is real

Mandelbrot's point about markets is that the same roughness shows up at many
scales. Turn that into a validation rule: an edge (skill versus the market
price, or excess return) is believed only if it is present at several
resolutions at once: per question, per category, per week, per month, per
platform. A spurious edge found by searching usually lives at one scale and
vanishes at the others; a structural edge survives coarse-graining. The gate
gains a criterion: minimum number of scales (of those with enough data) at
which the sign of the edge agrees.

Grew out of: 15 (dimension as scaling exponent), 16 (renormalisation, baby
Mandelbrot sets), Mandelbrot's multifractal model, 14 (overfit backtests).
Falsified if: edges that pass the multi-scale test fail out of sample as
often as edges that pass only the single-scale test.

## 4. Information budget as a currency: bits per token

Resource frugality needs a unit. For each learning action (reading a source,
running a child's report through the store, running a backtest), record the
tokens and wall-clock spent, and later the information it produced: the
reduction in log loss on resolved forecasts attributable to insights from
that action, or the count of insights it fed that were later validated.
Allocate the next cycle's budget toward the sources and children with the
highest validated bits per token. Reading everything is not frugal; reading
what has paid is.

Grew out of: 01 (Landauer: information costs energy; no free demon), the
user's constraint of minimal waste, MANDEL.md principle 6.
Falsified if: bits-per-token rankings are unstable across cycles (then the
signal is too noisy to allocate on and a simpler round-robin is better).

## 5. Disagreement among the children is itself a signal

When several children forecast the same question, pool them with a
log-opinion pool weighted by each child's track record, and record the
dispersion. High dispersion with a confident market is where either the
market or the children are wrong, and both cases are worth a proposal. Low
dispersion that disagrees with the market is the strongest candidate for a
trade. Extremise the pooled forecast only as far as the pool's own
calibration history justifies.

Grew out of: Tetlock (aggregation and extremising), 01 (Shannon: redundancy
across independent channels), the children as parallel evaluators.
Falsified if: the pooled forecast's Brier score is not better than the best
single child's over a hundred resolved questions.

## 6. The signal map is an instrument, not a picture

The concept graph (`python -m mandel graph`) shows how sources, concepts,
principles and decision centres connect, with co-occurrence computed from the
files and tensions parsed from the synthesis. Make it an instrument: once
proposals carry the insights they depend on, edge weights become *measured*
(how often an insight's use coincided with a passed gate), and edges that
never carry a validated signal fade. The map then shows where knowledge
flows into decisions and where it only looks like it does.

Grew out of: the user's request for a living map; 05 (what a network learns
is visible in which connections carry signal); principle 10 (entropy is the
default).
Falsified if: after fifty proposals, edge usage is uniform (then the map
carries no information about which knowledge matters).

## 7. Renormalise the loop: the same cycle at four scales

Run the identical cycle shape (observe, hypothesise, pre-register, measure,
gate, record) at four scales with budgets that shrink by a fixed factor each
level down: Mandel itself (quarterly), a child (weekly), a strategy inside a
child (daily), a single forecast (per question). Each level's accepted
proposals are the next level up's observations. This is where the fractal
framing is structural rather than decorative: the self-similarity is in the
process, not in the data.

Grew out of: 16 (renormalisation and baby Mandelbrot sets), 04 (nested
feedback loops), 08/09 (iterated maps converge to an attractor).
Falsified if: the levels need different procedures in practice (then the
self-similarity was imposed, and the design should drop it).
