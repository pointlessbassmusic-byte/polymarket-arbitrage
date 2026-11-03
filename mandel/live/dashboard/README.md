# Consolidated dashboard — paper trading and test progress

Dashboard artifact (Dashboard type): https://claude.ai/artifact/YW11NMqwusSM59jktjYmSW

`index.html` is the page stored at `files/index.html` in the artifact's store.
`data/*.json` are the thirteen dataset files the page reads, each uploaded as
an asset of the artifact and named by a `datasets/<id>` document whose
`source.url` is the asset's `/_blob/<id>` url.

| dataset id | file | built from |
|---|---|---|
| paper_sessions | paper_sessions.json | paper journal (`mandel/state/live`), one row per session |
| paper_fills | paper_fills.json | paper journal fills + `print.official` rows |
| paper_round_trips | paper_round_trips.json | `tracker.calendar_progress` round trips (paper and official-print shadow) |
| wide_orders | wide_orders.json | widened-sleeve journal on the capture box |
| children_forward_tests | children_forward_tests.json | tracker rows + Monday intake (children's figures unverified) |
| registry_status | registry_status.json | `mandel/state/registry` status counts |
| registry_by_kind | registry_by_kind.json | registry kind x status counts |
| registry_timeline | registry_timeline.json | ledger: cumulative preregistrations and verdicts per day |
| capture_health | capture_health.json | capture archive: steps run / failed per night |
| capture_families | capture_families.json | capture archive: latest day per family |
| strategies | strategies.json | `python -m mandel.live.tracker` |
| alerts | alerts.json | `mandel.live.evidence_graph` alerts |
| next_tests | next_tests.json | `mandel.live.evidence_graph` next-test ranking |

## Refreshing

1. `python -m mandel.live.import_linode` (fetches the box's status and the paper journal, rebuilds the
   tracker and the evidence graph), then `python -m mandel.live.dashboard_export` rebuilds every file here.
2. Upload each changed file as an asset of the artifact (Artifact publish with
   `asset: true`); the result gives the new `/_blob/...` url.
3. Update the matching `datasets/<id>` document: `source.url`, `source.name`
   and `updated.{at,by}`, pinned with `if_version`.
4. The page itself changes only when `index.html` changes: write it as
   `files/index.html` (`{"text": ...}`) pinned with `if_version`.

Numbers are facts from the repo's own records; nothing on the page is a
forecast. The official-print columns fill from 2026-11-03, when the runner's
reconcile first records `print.official` rows.
