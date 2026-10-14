# Fractals are typically not self-similar (3Blue1Brown)

- **Creator / category:** Grant Sanderson, 3Blue1Brown (2017). User category: Fractals. Link: https://youtu.be/gB9n2gHsHN4 · lesson page https://www.3blue1brown.com/lessons/fractal-dimension
- **Date researched:** 2026-10-14. **Coverage confidence:** 0.70. The lesson page served only its introduction and the transcript is unreachable, but the video is widely summarised and Mandel's reconstruction follows its well-known structure; exact numbers below are the standard values the video derives. Written by Mandel directly because the delegated learner could not run.

## What it says

- **The misconception:** fractals are popularly defined as shapes that look exactly like themselves when you zoom in. Perfect self-similarity (Sierpinski triangle, von Koch curve) is the exception; the real definition "has something to do with fractal dimension".
- **Dimension by mass scaling.** Scale a line by 1/2 and its mass halves; a square's mass goes to 1/4; a cube's to 1/8: mass scales as (1/2)^D, which defines D. The Sierpinski triangle scaled by 1/2 is made of 3 copies, so its mass scales by 3, giving (1/2)^D = 1/3 and D = log 3 / log 2 ≈ 1.585. The von Koch curve scaled by 1/3 gives 4 copies: D = log 4 / log 3 ≈ 1.262. The Sierpinski carpet: D = log 8 / log 3 ≈ 1.893.
- **Dimension as roughness.** D measures how much detail persists under zoom, a number between the topological dimension and the ambient one; a curve that fills more of the plane as you zoom has D nearer 2.
- **Non-self-similar shapes: box counting.** Cover the shape with a grid of boxes of side s, count the boxes N(s) that touch it, shrink s, and read D as the slope of log N(s) against log(1/s). For a smooth curve the slope is 1; for the coastline of Britain it is about 1.21; for random fractal curves (e.g. Brownian paths, dimension 1.5) it is non-integer too.
- **The definition.** A fractal is a shape whose dimension, measured this way, is not an integer, or more carefully, a shape whose box-counting (Hausdorff) dimension exceeds its topological dimension; the video notes that fractals can have integer dimension (the boundary of the Mandelbrot set has dimension 2) so "non-integer" is a heuristic.
- **Range of scales.** In nature roughness holds only across a range of scales: a coastline is fractal from kilometres down to pebbles, and smooth below; the exponent is always "over these scales". Mathematical fractals push the range to infinity.
- **Why it matters:** dimension gives a quantitative handle on roughness, which is how Mandelbrot made fractal geometry useful: coastlines, clouds, price charts all get a measured number rather than a vibe.

## Evidence quality

**Mainstream-educational, rigorous within its scope.** The mathematics is textbook (Falconer); the numbers are exact for the self-similar examples and empirical for the coastline. Coverage of the specific video is good but not verified against its transcript.

## What Mandel adopts

- **Measure roughness; do not assert self-similarity.** Any "fractal" claim about a price series becomes a measured exponent with a stated scale range and an interval, following the box-counting and partition-function methods (A4).
- **Exponents are slopes on log-log plots, and slopes need ranges.** Mandel reports the Δt range over which a scaling law was fitted, the R² of the fit, and a shuffled-data null, because a straight-looking segment over one decade proves little.
- **Dimension between the topological and the ambient.** Mandel's analogue: every model lives between "too simple to capture structure" and "too flexible to generalise"; the measured exponent (held-out performance versus parameter count) says where.
- **Integer dimension is still possible.** A shape can be maximally rough (dimension 2) and still be a boundary; some market boundaries (resolution events, regime shifts) are as rough as they can be and should be modelled as such, not smoothed.

## What Mandel holds loosely or rejects

- The coastline's 1.21 or any single exponent as a universal constant: estimates depend on the scale range and the estimator; Mandel quotes them with both.
- The step from "price charts look fractal" to "price charts are predictable": roughness is a description, not an edge; Mandelbrot said as much and A4 is where the predictive content (if any) lives.
- Infinite-scale self-similarity in anything empirical.

## Design implications for the RSI predictive substrate

- `mandel/validation/scaling.py` (planned, shared with A4): `box_count_dimension(series_as_curve)` and `structure_function_exponents(returns, qs, dts)` with intervals, scale-range metadata and a shuffle null; outputs are diagnostics attached to proposals, never pass criteria alone.
- Every scaling estimate stored as an insight of kind `metric` with provenance and the scale range in its text, so the signal map can show which markets have measured roughness and over what range.
- Metrics: number of markets with a measured exponent, interval widths, and how often the shuffled null is rejected.

## Cross-links to other provided resources

- 16 (Hubbard): Shishikura's result that the Mandelbrot set's boundary has dimension 2 is the integer-dimension case the video mentions.
- 08, 09 (IFS): the self-similar examples whose dimension formula log k / log(1/s) the video starts from; 09 gives the theorem and the non-overlap condition.
- 11 (Markov) and A4 (multifractal markets): Brownian paths have dimension 1.5; multifractal time is what makes real price paths rougher at some times than others.
- 07 (overfitting): the "range of scales" caveat is the same discipline as the train/validation split; a law fitted inside one range must be tested outside it.

## Sources used

- https://www.3blue1brown.com/lessons/fractal-dimension (introduction only served)
- LBRY mirror description of the video (notes on integer dimensions and the Mandelbrot boundary), via web search
- Complexity Explorer, "Box-Counting Dimension" segment (method), via web search
- Falconer, *Fractal Geometry* (background)
