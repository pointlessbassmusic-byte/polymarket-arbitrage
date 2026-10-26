# Efficiency review, 2026-10-26

Rerun from scratch: the earlier review's findings (workflow wipr8ufa2) were lost with a container restart. Method:
measure every command an operator or a harness run pays for, fix what dominates, leave what is already cheap.

## Measured

| Path | Before | After | Note |
|---|---|---|---|
| `python -m mandel graph` (signal map build) | 35 s | 4.5 s | 14 of 16 s were `_count_mentions` running the lexicon's 272 patterns as 272 scans of every document; now one alternation per concept (58 scans), the verdict overlay builds each theory's text once, `cmd_graph` no longer builds the graph twice |
| full test suite, 3,031 tests | 14 min 09 s | 4 min 46 s | `pytest -n 4` (pytest-xdist); no test shares state, all pass in parallel. Per-test fidelity kept: the slow tests run whole harness sets on fake archives at the production bootstrap count (2,000 reps), which is what makes a planted effect pass and a null fail with the real statistics |
| `python -m mandel --help` | 1.8 s | — | fine; the 30 s seen once was a cold import cache during a concurrent suite run |
| `import mandel.experiments.run` (70 batch modules) | 1.5 s warm | — | pandas/pyarrow (6.6 s cold) and scipy come in through `batch12_ml` and `batch13_flow`; a lazy import would help only cold starts |
| `python -m mandel.live.import_linode` | 4.5 s | — | 0.9 s of it is 15 git subprocesses; the tracker and evidence graph rebuild in 0.4 s |
| archive index load (3,563 bundles, 4.6 MB) | 0.13 s | — | `archive.get` is a dict lookup |
| ledger sync (6,800 records, 5.6 MB) | 0.06 s | — | |
| registry load / save (2.1 MB) | 1.3 s / 0.03 s | — | load time is mostly imports |
| Kraken group: 114 monthly 1-minute bundles into one grid | 80 s | — | gzip JSONL at level 9; acceptable for a once-per-run load and `_CACHE` shares it across the four harnesses |

## Not changed, on purpose

- Bootstrap reps in tests (see above).
- Archive compression level: level 9 gzip costs on write (once) and little on read.
- `panel_cache` already replaced the 13 GB per-harness daily loads (2026-10-21).

## Correctness note

The map's mention counts changed where a span matched two overlapping patterns of one concept: it counted twice
before and once now. 23 of 1,534 edge labels and 7 of 120 node sizes moved by 1-4 mentions; nodes, edges and
documents are identical. Test pinned (`test_lexicon_compiles_to_one_scan_per_concept_and_counts_a_span_once`).
