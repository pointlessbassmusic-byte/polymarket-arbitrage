"""Registry of every strategy hypothesis tested here, including failures.

Negative results are the part most research loses: a killed idea goes
into a log nobody reads and gets re-tested from scratch later. This keeps
them in one machine-readable file (`hypotheses.yaml`) with the data,
regime and command each verdict came from.

  python -m cryptobot.hypotheses                     # summary by verdict
  python -m cryptobot.hypotheses --verdict alive     # what is still standing
  python -m cryptobot.hypotheses --similar "short new listings on dex"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("hypotheses.yaml")
REQUIRED = ("id", "title", "source", "claim", "test", "data", "result", "verdict",
            "regime", "rerun")
VERDICTS = ("alive", "adopted", "killed", "inconclusive")
_STOP = {"the", "a", "an", "and", "or", "of", "on", "in", "to", "for", "with", "at",
         "by", "is", "it", "as", "from", "when", "than", "be", "its", "that"}


def load(path: Path = PATH) -> list[dict]:
    rows = yaml.safe_load(path.read_text()) or []
    validate(rows)
    return rows


def validate(rows: list[dict]) -> None:
    seen = set()
    for r in rows:
        missing = [k for k in REQUIRED if not str(r.get(k, "")).strip()]
        if missing:
            raise ValueError(f"{r.get('id', '?')}: missing {missing}")
        if r["verdict"] not in VERDICTS:
            raise ValueError(f"{r['id']}: verdict {r['verdict']!r} not in {VERDICTS}")
        if r["id"] in seen:
            raise ValueError(f"duplicate id {r['id']}")
        seen.add(r["id"])
        if r["verdict"] == "alive":
            _check_alive_evidence(r)


def _check_alive_evidence(r: dict) -> None:
    """An 'alive' verdict must say how big the search behind it was.
    See PREREGISTER.md."""
    has_diag = all(k in r for k in ("trials_run", "n_eff", "pbo", "dsr"))
    prereg = bool(r.get("preregistered")) and "psr" in r
    pending = r.get("diagnostics") == "pending" and "trials_run" in r
    if not (has_diag or prereg or pending):
        raise ValueError(f"{r['id']}: 'alive' needs trials_run/n_eff/pbo/dsr, or "
                         f"preregistered: true with psr, or diagnostics: pending with trials_run")
    if has_diag and (float(r["dsr"]) < 0.95 or float(r["pbo"]) > 0.5):
        raise ValueError(f"{r['id']}: 'alive' with DSR {r['dsr']} / PBO {r['pbo']} fails the "
                         f"verdict rule (DSR >= 0.95, PBO <= 0.5); use 'inconclusive'")


STUB = """- id: {id}
  title: ""
  source: ""
  claim: ""
  test: ""
  success: ""
  data: ""
  result: "PRE-REGISTERED {date}; not yet run"
  verdict: inconclusive
  regime: ""
  rerun: ""
  preregistered: true
  trials_run: 1
"""


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1}


def similar(rows: list[dict], text: str, k: int = 5) -> list[tuple[float, dict]]:
    """Rank registered hypotheses by word overlap with `text` (Jaccard on
    title + claim). Crude on purpose: it only has to surface the obvious
    "we already tried this" before a test is rerun."""
    q = _words(text)
    out = []
    for r in rows:
        w = _words(r["title"] + " " + r["claim"])
        if q and w:
            out.append((len(q & w) / len(q | w), r))
    out.sort(key=lambda t: t[0], reverse=True)
    return [t for t in out[:k] if t[0] > 0]


def render(rows: list[dict]) -> str:
    out = []
    for v in VERDICTS:
        g = [r for r in rows if r["verdict"] == v]
        if not g:
            continue
        out.append(f"\n{v.upper()} ({len(g)})")
        for r in g:
            out.append(f"  {r['id']:32s} {r['title']}")
            out.append(f"  {'':32s} -> {r['result']}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verdict", choices=VERDICTS)
    ap.add_argument("--similar", metavar="TEXT")
    ap.add_argument("--new", metavar="ID", help="print a pre-registration stub (see PREREGISTER.md)")
    args = ap.parse_args()
    if args.new:
        import datetime as dt
        print(STUB.format(id=args.new, date=dt.date.today().isoformat()))
        return 0
    rows = load()
    if args.similar:
        hits = similar(rows, args.similar)
        if not hits:
            print("nothing similar registered")
        for score, r in hits:
            print(f"{score:.2f}  [{r['verdict']}] {r['id']}: {r['title']}\n"
                  f"      {r['result']}\n      regime: {r['regime']}\n      rerun: {r['rerun']}")
        return 0
    if args.verdict:
        rows = [r for r in rows if r["verdict"] == args.verdict]
    print(f"{len(rows)} hypotheses" + render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
