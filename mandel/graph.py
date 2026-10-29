"""
Concept graph: how Mandel's knowledge connects.
================================================

Builds a layered graph from the substrate (the knowledge files, children,
data streams) through concepts and operating principles to the decision
centres (the engine's components), and back. It is the data behind the
"signal map" visualisation.

Layers
------
0 substrate   every knowledge file (src:NN / adj:AN), each child, the market
              data streams and forecast resolutions: everything observed
1 concept     a curated lexicon of ideas, included when a file mentions it
2 principle   Mandel's operating principles from MANDEL.md
3 centre      the engine components that take or record decisions

Edges
-----
provenance  source -> concept           weight = mentions (positive)
cooccur     concept <-> concept         computed positive PMI across files;
                                        strongly negative PMI between common
                                        concepts is emitted as sign -1
skeptical   source -> concept           the concept appears in the file's
                                        "holds loosely or rejects" section (sign -1)
supports    concept -> principle,       curated keyword links
            principle -> centre
tension     concept <-> concept         parsed from SYNTHESIS.md "Tensions" bullets (sign -1)
flow        centre -> centre            the improvement loop

Everything here is derived from files; nothing is invented. Co-occurrence
is a real but weak statistic with few documents, and the visualisation says so.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from mandel.paths import KNOWLEDGE_ROOT, MANDEL_ROOT

# --------------------------------------------------------------------------
# Lexicon: concept id -> (label, group, regex patterns)
# --------------------------------------------------------------------------
LEXICON: dict[str, tuple[str, str, list[str]]] = {
    "information":     ("Information as physical", "information", [r"\binformation (is|as) physical", r"\blandauer", r"\bit from bit", r"\bbits?\b.*\b(cost|erase|physical)"]),
    "entropy":         ("Entropy", "information", [r"\bentrop(y|ies)\b", r"\bsecond law\b"]),
    "shannon":         ("Shannon information", "information", [r"\bshannon\b", r"\bsurprisal\b", r"\bkl[- ]divergence\b", r"\bmutual information\b"]),
    "compression":     ("Compression / MDL", "information", [r"\bkolmogorov\b", r"\bminimum description length\b", r"\bmdl\b", r"\bsolomonoff\b", r"\bcompress(ion|ible)\b"]),
    "noisy_channel":   ("Noisy channel / redundancy", "information", [r"\bnoisy channel\b", r"\bredundan(cy|t)\b", r"\berror[- ]correct"]),
    "anticipation":    ("Anticipatory signals", "prediction", [r"\bprecogniti(on|ve)\b", r"\bpresentiment\b", r"\banticipatory\b", r"\bretrocausal"]),
    "idealism":        ("Mind / idealism framing", "framing", [r"\bidealis(m|t)\b", r"\bconsciousness\b", r"\bmind[- ]body\b"]),
    "forking_paths":   ("Forking paths / p-hacking", "validation", [r"\bforking paths?\b", r"\bp-hack", r"\bgarden of forking\b", r"\bpost[- ]hoc\b", r"\bmultiple comparisons?\b"]),
    "replication":     ("Replication & pre-registration", "validation", [r"\breplicat(e|ion|ions)\b", r"\bpre-?regist(er|ered|ration)\b"]),
    "rsi":             ("Recursive self-improvement", "learning", [r"\brecursive self-?improvement\b", r"\bself-?improv", r"\bseed ai\b", r"\bintelligence explosion\b", r"\bgödel machine\b", r"\bgodel machine\b", r"\bself[- ]modif"]),
    "feedback_loop":   ("Feedback loops", "learning", [r"\bfeedback loops?\b", r"\bcompounding\b", r"\bcloses? the loop\b"]),
    "evaluation_bottleneck": ("Evaluation is the bottleneck", "validation", [r"\bevaluation (is|as) the (bottleneck|hard part)\b", r"\bverif(y|ication) (is|as) the bottleneck\b", r"\bbottleneck\b", r"\bevaluation[- ]cascade\b", r"\bvalidated hit[- ]rate\b", r"\bskill rises\b", r"\bstepping[- ]stones?\b", r"\bskill[- ]rises\b", r"\bvalidated[- ]hit[- ]rate\b"]),
    "gradient_descent":("Gradient descent", "learning", [r"\bgradient descent\b", r"\bloss (function|landscape|surface)\b", r"\bstochastic gradient\b"]),
    "backprop":        ("Backpropagation", "learning", [r"\bback-?propagat", r"\bchain rule\b"]),
    "overfitting":     ("Overfitting & generalisation", "validation", [r"\boverfit", r"\bgeneralis", r"\bgeneraliz", r"\bregulari[sz]", r"\bvalidation (set|split)\b", r"\bheld-?out\b", r"\bout[- ]of[- ]sample\b"]),
    "representation":  ("Representations / embeddings", "learning", [r"\bembedding", r"\brepresentation", r"\bfeature(s)? learn", r"\blatent\b"]),
    "attention":       ("Attention / transformers", "learning", [r"\battention\b", r"\btransformer", r"\bgpt\b"]),
    "linear_algebra":  ("Linear algebra", "mathematics", [r"\bmatri(x|ces)\b", r"\beigen", r"\bsvd\b", r"\bsingular value", r"\bvector space", r"\bprojection\b", r"\brank\b"]),
    "affine_ifs":      ("Affine maps & IFS", "fractal", [r"\baffine\b", r"\biterated function system", r"\bifs\b", r"\bbarnsley\b", r"\bhutchinson\b", r"\bchaos game\b", r"\bcontraction mapping\b"]),
    "attractor":       ("Attractors & fixed points", "fractal", [r"\battractor", r"\bfixed[- ]point", r"\bconverge(s|nce)? to\b"]),
    "fractal_dimension":("Fractal dimension / roughness", "fractal", [r"\bfractal dimension\b", r"\bbox[- ]counting\b", r"\bhausdorff\b", r"\broughness\b", r"\bscaling exponent\b", r"\bself-?similar"]),
    "mandelbrot_set":  ("Mandelbrot & Julia sets", "fractal", [r"\bmandelbrot set\b", r"\bjulia set", r"\bz\^?2 ?\+ ?c\b", r"\bparameter space\b", r"\bexternal rays?\b", r"\bhyperbolic component"]),
    "renormalization": ("Renormalisation / universality", "fractal", [r"\brenormali[sz]", r"\buniversalit", r"\bbaby mandelbrot", r"\bscale[- ]invarian"]),
    "multifractal":    ("Multifractal time / fat tails", "markets", [r"\bmultifractal", r"\bfat[- ]tail", r"\bheavy[- ]tail", r"\bl[ée]vy\b", r"\bhurst\b", r"\bvolatility clustering\b", r"\btrading time\b"]),
    "markov":          ("Markov chains", "prediction", [r"\bmarkov\b", r"\bmemoryless", r"\bstationary distribution\b", r"\btransition (matrix|probabilit)"]),
    "monte_carlo":     ("Monte Carlo / bootstrap", "validation", [r"\bmonte carlo\b", r"\bbootstrap", r"\bresampl", r"\bsimulat(e|ion|ed)\b"]),
    "law_large_numbers":("Law of large numbers", "prediction", [r"\blaw of large numbers\b", r"\bergodic", r"\bconverge(s)? in probability\b"]),
    "bayes":           ("Bayesian updating / priors", "prediction", [r"\bbayes", r"\bprior(s)?\b", r"\bposterior\b", r"\bupdat(e|ing) (on|with) evidence\b"]),
    "proper_scoring":  ("Proper scoring rules", "validation", [r"\bbrier\b", r"\blog[- ]?loss\b", r"\bproper scoring\b", r"\bscoring rule"]),
    "calibration":     ("Calibration", "validation", [r"\bcalibrat", r"\breliability diagram\b", r"\boverconfiden"]),
    "kelly":           ("Kelly / bet sizing", "markets", [r"\bkelly\b", r"\bbet siz", r"\bposition siz", r"\bgrowth rate\b"]),
    "edge_vs_market":  ("Edge vs the market price", "markets", [r"\bbeat(s|ing)? the market\b", r"\bmarket[- ]implied\b", r"\bmispric", r"\barbitrage\b", r"\bedge\b"]),
    "backtest":        ("Backtesting discipline", "validation", [r"\bbacktest", r"\bwalk[- ]forward\b", r"\bpaper[- ]trad", r"\bsharpe\b", r"\bdeflated\b"]),
    "lookahead":       ("Look-ahead & leakage", "validation", [r"\blook-?ahead\b", r"\bleak(age|s|ing)?\b", r"\bsurvivorship\b", r"\bpoint[- ]in[- ]time\b"]),
    "fees_slippage":   ("Fees, slippage, liquidity", "markets", [r"\bslippage\b", r"\bfees?\b", r"\bliquidity\b", r"\btransaction cost"]),
    "prediction_market":("Prediction markets", "markets", [r"\bprediction market", r"\bpolymarket\b", r"\bkalshi\b", r"\bmetaculus\b", r"\bsuperforecast"]),
    "risk":            ("Risk limits & kill switch", "markets", [r"\bdrawdown\b", r"\bkill switch\b", r"\brisk (limit|management)\b", r"\bposition limit"]),
    "memory":          ("Memory / knowledge base", "substrate", [r"\bsecond brain\b", r"\bknowledge base\b", r"\bmemory\b", r"\bobsidian\b", r"\bnotion\b", r"\bretriev(al|e)\b", r"\bmemoryful\b", r"\bstateless\b", r"\bitemi[sz]ed context\b"]),
    "provenance":      ("Provenance & audit", "substrate", [r"\bprovenance\b", r"\baudit", r"\bledger\b", r"\bhash", r"\btamper"]),
    "agent_tools":     ("Agents, tools, MCP", "substrate", [r"\bmcp\b", r"\bagentic\b", r"\btool[- ]use\b", r"\bclaude code\b", r"\bsubagent"]),
    "cost_budget":     ("Resource cost & budgets", "substrate", [r"\btoken(s)? (cost|budget)\b", r"\bbudget", r"\bcost of (information|acquiring)\b", r"\bfrugal", r"\bresource (use|waste)\b"]),
    # market variables (the learning program's inputs and the strategy literature around them, 2026-10-20)
    "volume":          ("Volume & liquidity", "variables", [r"\bvolume\b", r"\bturnover\b", r"\bdollar volume\b", r"\billiquid", r"\bamihud\b", r"\bvwap\b"]),
    "implied_vol":     ("Implied volatility & skew", "variables", [r"\bimplied vol", r"\bvolatility smirk\b", r"\bskew\b", r"\bvix\b", r"\bdvol\b", r"\bterm structure\b"]),
    "vrp":             ("Variance risk premium", "variables", [r"\bvariance risk premium\b", r"\bvolatility risk premium\b", r"\bvrp\b", r"\bimplied[- ](minus|over)[- ]reali[sz]ed\b", r"\bvariance[- ]risk[- ]premium\b", r"\bvolatility[- ]risk[- ]premium\b", r"\bimplied[- ]move\b.*\breali[sz]ed\b", r"\bgvz\b", r"\bovx\b", r"\brvx\b", r"\bshort[- ]straddle\b", r"\bput[- ]?writ(e|ing)\b"]),
    "option_flow":     ("Dealer gamma & option flow", "variables", [r"\bgamma\b", r"\bvanna\b", r"\bcharm\b", r"\bopex\b", r"\b0dte\b", r"\bput[- ]call\b", r"\bopen interest\b", r"\bpinning\b"]),
    "short_interest":  ("Short interest & lending", "variables", [r"\bshort interest\b", r"\bdays[- ]to[- ]cover\b", r"\bshort volume\b", r"\bshort[- ]sale\b", r"\bborrow (fee|cost|rate)", r"\bsecurities lending\b", r"\bshort squeeze", r"\breg ?sho\b"]),
    "earnings":        ("Earnings & corporate events", "variables", [r"\bearnings\b", r"\bpead\b", r"\bannouncement (premium|drift|return)", r"\bbuybacks?\b", r"\bshare issuance\b", r"\bindex (inclusion|addition|deletion)", r"\binsider (buying|trading|filings?)"]),
    "size":            ("Size & market cap", "variables", [r"\bmarket cap", r"\bsize (effect|premium|factor)", r"\bsmall[- ]caps?\b", r"\bshares outstanding\b"]),
    "intraday":        ("Intraday & overnight patterns", "variables", [r"\bintraday\b", r"\bovernight\b", r"\btime[- ]of[- ]day\b", r"\bopening range\b", r"\bclos(e|ing) auction\b", r"\bhalf[- ]hour\b"]),
    "calendar":        ("Calendar & macro events", "variables", [r"\bfomc\b", r"\bturn[- ]of[- ](the[- ])?month\b", r"\bpre[- ]holiday\b", r"\bmonth[- ]end\b", r"\bcpi\b", r"\bpayrolls?\b", r"\bseasonal(ity)?\b", r"\bday[- ]of[- ](the[- ])?week\b", r"\bweekday\b", r"\bweekend\b", r"\bsanta[- ]claus\b", r"\bpresidential[- ]cycle\b", r"\bquarter[- ]end\b", r"\bwindow[- ]dressing\b", r"\bauction[- ]cycle\b", r"\bholiday\b", r"\bcalendar[- ]effects?\b", r"\bexpir(y|ation)[- ]day\b"]),
    "lead_lag":        ("Cross-asset lead-lag", "variables", [r"\blead[- ]lag\b", r"\bcross[- ]asset\b", r"\beconomic links?\b", r"\bspill-?overs?\b", r"\bleading indicator"]),
    "momentum":        ("Momentum & reversal", "variables", [r"\bmomentum\b", r"\breversal\b", r"\btrend[- ]following\b", r"\bmean[- ]revers"]),
    "carry":           ("Carry, basis & funding", "variables", [r"\bcarry\b", r"\bbasis\b", r"\bfunding rates?\b", r"\broll yield\b", r"\bcontango\b", r"\bbackwardation\b"]),
    "positioning":     ("Positioning & flows", "variables", [r"\bcommitments of traders\b", r"\bcot\b", r"\bhedging pressure\b", r"\b(fund|etf) flows?\b", r"\brebalanc", r"\bliquidations?\b", r"\bptr\b", r"\bcongress", r"\binsider", r"\b13f\b"]),
    "vol_regime":      ("Volatility regimes & timing", "variables", [r"\bvolatility[- ]managed\b", r"\bvolatility timing\b", r"\bregime[- ]switch", r"\breali[sz]ed (vol|skew|kurt)", r"\bhar[- ]rv\b"]),
    "anomaly_decay":   ("Anomaly decay after publication", "validation", [r"\bpost[- ]publication\b", r"\banomal(y|ies) (decay|disappear)", r"\bdecay(ed|s)?\b", r"\barbitraged away\b", r"\bno longer (works|pays)\b"]),
    "reference_price": ("Reference-price edge", "markets", [r"\breference[- ](price|class)\b", r"\bsharper (public )?source\b", r"\bleads? the (book|market|price|venue)\b",
                                                        r"\bnowcast", r"\bfed[- ]?funds\b", r"\bclosing line\b", r"\bsportsbook\b", r"\bcross[- ]venue\b",
                                                        r"\b(leads?|lags?|follows?)\b[^.]{0,60}\b(polymarket|kalshi|coinbase|kraken|deribit|cme)\b",
                                                        r"\bderibit\b[^.]{0,60}\bdigital", r"\bdigital\b[^.]{0,60}\bderibit\b", r"\b(price discovery|lead[- ]lag)\b",
                                                        r"\bnon-member\b"]),
    "adverse_selection": ("Adverse selection & markouts", "markets", [r"\badverse(ly)? select", r"\bmarkouts?\b", r"\bqueue position\b", r"\bmaker fills?\b"]),
    "option_structure": ("Option structures", "variables", [r"\bcondor\b", r"\bbutterfly\b", r"\bstraddle\b", r"\bstrangle\b", r"\bguts\b", r"\bbackspread\b", r"\bratio[- ]spread\b", r"\bcollar\b", r"\bprotective[- ]put\b", r"\bcovered[- ]call\b", r"\bbuy[- ]?write\b", r"\bcalendar[- ]spread\b", r"\bbox[- ]spread\b", r"\bconversion\b", r"\bsynthetic\b", r"\bjade[- ]lizard\b", r"\bcredit[- ]spread\b", r"\bvertical\b", r"\bladder\b", r"\bstrip\b", r"\bstrap\b", r"\b(put|call)[- ]spread\b", r"\biron[- ]condor\b", r"\brisk[- ]reversal\b"]),
    "arbitrage_bounds": ("Parity & arbitrage bounds", "markets", [r"\bparity\b", r"\barbitrage[- ]bounds?\b", r"\bbox[- ]rate\b", r"\bimplied (usd |borrow(ing)? )?rate\b", r"\bearly[- ]exercise\b", r"\bfinancing rate\b", r"\bno[- ]arbitrage\b", r"\bexecutable\b"]),
    "relative_value":  ("Relative value & convergence", "markets", [r"\bpairs?[- ]trad", r"\bcointegrat", r"\bpremium[- /]discount\b", r"\bnav\b", r"\bcross[- ]listed\b", r"\bratio\b.*\brevert", r"\bspread\b.*\brevert", r"\bconverge(nce|s)?\b", r"\bdistance\b.*\bpairs?\b", r"\bgold[- ]silver ratio\b"]),
    "factor_tilt":     ("Factor tilts", "variables", [r"\bprofitability\b", r"\brmw\b", r"\bbetting[- ]against[- ]beta\b", r"\bbab\b", r"\besg\b", r"\bsin (stocks?|premium)\b", r"\bquality (factor|tilt)\b", r"\bvalue (factor|tilt|premium)\b", r"\blow[- ]vol(atility)? (anomaly|tilt|factor)\b", r"\bfama[- ]french\b", r"\bpiotroski\b", r"\bfactor (tilt|premium|exposure)\b"]),
    "onchain_flow":    ("On-chain & stablecoin flows", "variables", [r"\bsopr\b", r"\bnetflows?\b", r"\bexchange (in|out)?flows?\b", r"\bstablecoin\b", r"\bon[- ]chain\b", r"\bmint(ing|s)?\b", r"\bsupply (change|growth)\b", r"\bwhale\b"]),
    "sentiment":       ("Sentiment & retail flow", "variables", [r"\bsentiment\b", r"\bbullish[- ]ratio\b", r"\bfear[- ](&|and)?[- ]?greed\b", r"\btrending\b", r"\bretail[- ](order[- ])?(imbalance|flow)\b", r"\blexicon\b", r"\bstocktwits\b", r"\breddit\b", r"\bmentions?\b", r"\bcontrarian\b"]),
}

CONCEPT_GROUP_LABELS = {
    "information": "Information", "prediction": "Prediction", "framing": "Framing", "validation": "Validation",
    "learning": "Learning", "mathematics": "Mathematics", "fractal": "Fractals", "markets": "Markets", "substrate": "Substrate",
    "variables": "Market variables",
}

# Principles from MANDEL.md section 2, with the concepts that feed them and the centres they govern.
PRINCIPLES: list[tuple[str, str, list[str], list[str]]] = [
    ("p01", "Provenance is mandatory", ["provenance", "memory", "noisy_channel"], ["store", "ledger"]),
    ("p02", "Pre-register before you measure", ["replication", "forking_paths", "rsi"], ["proposals", "ledger"]),
    ("p03", "Only out-of-sample results count", ["overfitting", "lookahead", "backtest", "anomaly_decay"], ["gate"]),
    ("p04", "Score with proper scoring rules", ["proper_scoring", "calibration", "shannon", "edge_vs_market", "reference_price"], ["forecasts", "gate"]),
    ("p05", "Deflate for the search", ["monte_carlo", "backtest", "forking_paths", "law_large_numbers", "anomaly_decay"], ["gate"]),
    ("p06", "Information has a cost; budget it", ["information", "entropy", "cost_budget", "fees_slippage", "adverse_selection"], ["cycles"]),
    ("p07", "Redundancy for reliability", ["noisy_channel", "replication", "bayes"], ["store", "children"]),
    ("p08", "Never delete; tombstone", ["provenance", "information", "memory"], ["ledger", "store"]),
    ("p09", "Point-in-time discipline", ["lookahead", "markov", "backtest"], ["gate", "forecasts"]),
    ("p10", "Entropy is the default", ["entropy", "calibration", "memory"], ["cycles", "store"]),
    ("p11", "Hold framings loosely, mechanisms tightly", ["anticipation", "idealism", "mandelbrot_set", "renormalization", "bayes"], ["store"]),
    ("p12", "The children's claims are candidates", ["noisy_channel", "agent_tools", "calibration"], ["children", "store"]),
    ("p13", "No live-money change without the gate and the user", ["risk", "kelly", "edge_vs_market", "prediction_market"], ["gate", "proposals"]),
]

PRINCIPLE_SHORT = {
    "p01": "Provenance", "p02": "Pre-register", "p03": "Out-of-sample only", "p04": "Proper scoring",
    "p05": "Deflate the search", "p06": "Budget information", "p07": "Redundancy", "p08": "Tombstone, never delete",
    "p09": "Point-in-time", "p10": "Entropy is default", "p11": "Framings loosely", "p12": "Children = candidates",
    "p13": "No live money w/o gate",
}

CENTRES: list[tuple[str, str, str]] = [
    ("store", "Insight store", "mandel/store.py"),
    ("proposals", "Proposal book", "mandel/proposals.py"),
    ("gate", "Validation gate", "mandel/validation/gate.py"),
    ("ledger", "Ledger", "mandel/ledger.py"),
    ("forecasts", "Forecast book", "mandel/forecasts.py"),
    ("children", "Children protocol", "mandel/children.py"),
    ("cycles", "Cycle log", "mandel/cycles.py"),
]

# The improvement loop, as flow edges between centres.
FLOW: list[tuple[str, str, str]] = [
    ("store", "proposals", "insights suggest hypotheses"),
    ("proposals", "gate", "pre-registered criteria + evidence"),
    ("gate", "ledger", "accept / reject recorded"),
    ("gate", "store", "validated or retired insights"),
    ("forecasts", "gate", "out-of-sample scores"),
    ("children", "store", "reports become candidate insights"),
    ("children", "forecasts", "children's forecasts are scored"),
    ("store", "children", "validated insights become guidance"),
    ("ledger", "cycles", "cost and gains per cycle"),
    ("cycles", "proposals", "budget shapes what is tried next"),
]

_FILE_RX = re.compile(r"^(?P<num>\d{2}|A\d+)-(?P<slug>.+)\.md$")


@dataclass
class Node:
    id: str
    label: str
    layer: int
    kind: str
    size: float = 1.0
    group: str = ""
    detail: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Edge:
    s: str
    t: str
    type: str
    sign: int = 1
    w: float = 1.0
    label: str = ""


def _compile() -> dict[str, list[re.Pattern]]:
    """One alternation pattern per concept (a list of one, so callers iterate as before): the 272 lexicon patterns run as
    58 scans of each document instead of 272, which took 14 of the map's 16 build seconds (efficiency review 2026-10-26)."""
    return {cid: [re.compile("|".join(f"(?:{p})" for p in pats), re.I)] for cid, (_, _, pats) in LEXICON.items()}


def _section(text: str, heading_rx: str) -> str:
    parts = re.split(rf"^##\s+{heading_rx}.*$", text, flags=re.I | re.M)
    if len(parts) < 2:
        return ""
    return parts[1].split("\n## ")[0]


def _first_line_value(text: str, key: str) -> str:
    m = re.search(rf"\*\*{key}[^*]*\*\*:?\s*(.+)", text, re.I)
    return m.group(1).strip() if m else ""


def _display_path(f: Path, repo_root: Path, knowledge_root: Path) -> str:
    for base in (repo_root, knowledge_root):
        try:
            return str(f.relative_to(base))
        except ValueError:
            continue
    return f.name


def _count_mentions(text: str, rxs: Iterable[re.Pattern]) -> int:
    return sum(1 for rx in rxs for _ in rx.finditer(text))


def _excerpt(text: str, rxs: Iterable[re.Pattern], width: int = 230, lines: Optional[list[str]] = None) -> str:
    """First bullet or sentence in the file that mentions the concept, trimmed."""
    for line in (text.splitlines() if lines is None else lines):
        if not line.strip() or line.startswith("#"):
            continue
        if any(r.search(line) for r in rxs):
            body = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line).strip()
            body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
            return body if len(body) <= width else body[:width].rsplit(" ", 1)[0] + " …"
    return ""


def build_graph(knowledge_root: Path = KNOWLEDGE_ROOT, mandel_root: Path = MANDEL_ROOT,
                children: Optional[list[dict]] = None, theories: Optional[list[dict]] = None,
                child_ledger: Optional[list[dict]] = None) -> dict:
    """``theories`` (the registry's rows) and ``child_ledger`` (the children's pre-registered tests with verdicts) add the
    evidence overlay: what Mandel's and the children's own tests say about each concept. A child's ``text`` (its reports
    and guidance) links the child to the concepts it reports on."""
    rx = _compile()
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    # ---- layer 3: centres and the loop --------------------------------
    for cid, label, path in CENTRES:
        nodes[f"c:{cid}"] = Node(f"c:{cid}", label, 3, "centre", size=3.0, detail=path, meta={"module": path})
    for a, b, label in FLOW:
        edges.append(Edge(f"c:{a}", f"c:{b}", "flow", 1, 1.0, label))

    # ---- layer 2: principles ------------------------------------------
    for pid, label, concepts, centres in PRINCIPLES:
        nodes[f"p:{pid}"] = Node(f"p:{pid}", label, 2, "principle", size=2.2, detail="MANDEL.md section 2",
                                 meta={"short": PRINCIPLE_SHORT.get(pid, label)})
        for c in centres:
            edges.append(Edge(f"p:{pid}", f"c:{c}", "supports", 1, 1.0, "governs"))

    # ---- layer 0 + 1: files and concepts ------------------------------
    files = sorted((knowledge_root / "sources").glob("*.md")) + sorted((knowledge_root / "adjacent").glob("*.md"))
    doc_concepts: dict[str, dict[str, int]] = {}
    skeptical_hits: dict[str, set[str]] = {}
    excerpts: dict[str, list[dict]] = {}
    for f in files:
        m = _FILE_RX.match(f.name)
        if not m:
            continue
        num = m.group("num")
        sid = f"src:{num}" if not num.startswith("A") else f"adj:{num}"
        text = f.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip() if text else f.name
        quality = _first_line_value(text, "Rating") or _first_line_value(text, "Evidence quality")
        cov = re.search(r"coverage confidence[^0-9]*([01]?\.\d+)", text, re.I)
        nodes[sid] = Node(sid, title[:60], 0, "source", size=2.0,
                          group="adjacent" if sid.startswith("adj") else "provided",
                          detail=f.name,
                          meta={"file": _display_path(f, mandel_root.parent, knowledge_root), "coverage": float(cov.group(1)) if cov else None,
                                "quality": quality[:80], "words": len(text.split())})
        counts = {cid: _count_mentions(text, r) for cid, r in rx.items()}
        counts = {k: v for k, v in counts.items() if v > 0}
        doc_concepts[sid] = counts
        skept = _section(text, r"what mandel holds loosely")
        adopt = _section(text, r"what mandel adopts")
        # a concept is "held loosely" by this file when the sceptical section mentions it
        # at least as often as the adopting section does
        skeptical_hits[sid] = {cid for cid, r in rx.items()
                               if _count_mentions(skept, r) > 0 and _count_mentions(skept, r) >= _count_mentions(adopt, r)}
        lines = text.splitlines()
        for cid in counts:
            excerpts.setdefault(cid, [])
            if len(excerpts[cid]) < 8:
                ex = _excerpt(text, rx[cid], lines=lines)
                if ex:
                    excerpts[cid].append({"src": sid, "text": ex})

    all_concepts = {c for d in doc_concepts.values() for c in d}
    for cid in sorted(all_concepts):
        label, group, _ = LEXICON[cid]
        total = sum(d.get(cid, 0) for d in doc_concepts.values())
        ndocs = sum(1 for d in doc_concepts.values() if cid in d)
        nodes[f"k:{cid}"] = Node(f"k:{cid}", label, 1, "concept", size=1.2 + math.log1p(total) * 0.5, group=group,
                                 detail=CONCEPT_GROUP_LABELS.get(group, group),
                                 meta={"mentions": total, "documents": ndocs, "excerpts": excerpts.get(cid, [])})
    # concepts referenced by principles but not (yet) in any file still appear, faintly
    for _, _, concepts, _ in PRINCIPLES:
        for cid in concepts:
            if f"k:{cid}" not in nodes:
                label, group, _ = LEXICON[cid]
                nodes[f"k:{cid}"] = Node(f"k:{cid}", label, 1, "concept", size=1.0, group=group,
                                         detail=CONCEPT_GROUP_LABELS.get(group, group), meta={"mentions": 0, "documents": 0})

    for sid, counts in doc_concepts.items():
        for cid, n in counts.items():
            sign = -1 if cid in skeptical_hits.get(sid, set()) else 1
            etype = "skeptical" if sign < 0 else "provenance"
            edges.append(Edge(sid, f"k:{cid}", etype, sign, float(min(6, 1 + math.log1p(n))),
                              f"{n} mention{'s' if n != 1 else ''}" + (" (held loosely)" if sign < 0 else "")))

    # principle <- concept
    for pid, _, concepts, _ in PRINCIPLES:
        for cid in concepts:
            edges.append(Edge(f"k:{cid}", f"p:{pid}", "supports", 1, 1.0, "feeds"))

    # ---- co-occurrence (PMI) between concepts across documents --------
    N = len(doc_concepts)
    if N >= 3:
        df = {c: sum(1 for d in doc_concepts.values() if c in d) for c in all_concepts}
        cl = sorted(all_concepts)
        for i, a in enumerate(cl):
            for b in cl[i + 1:]:
                both = sum(1 for d in doc_concepts.values() if a in d and b in d)
                pa, pb, pab = df[a] / N, df[b] / N, both / N
                if pab > 0:
                    pmi = math.log(pab / (pa * pb))
                    if pmi > 0.25 and both >= 2:
                        edges.append(Edge(f"k:{a}", f"k:{b}", "cooccur", 1, float(min(4, 0.5 + pmi)),
                                          f"co-occur in {both}/{N} files, PMI {pmi:+.2f}"))
                elif df[a] >= max(3, N // 3) and df[b] >= max(3, N // 3):
                    # both common, never together: inverse association
                    edges.append(Edge(f"k:{a}", f"k:{b}", "cooccur", -1, 1.0,
                                      f"never co-occur despite {df[a]} and {df[b]} files (inverse)"))

    # ---- tensions from SYNTHESIS.md -----------------------------------
    synth = knowledge_root / "SYNTHESIS.md"
    if synth.exists():
        text = synth.read_text(encoding="utf-8")
        sec = _section(text, r"tensions")
        for line in sec.splitlines():
            if not re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line):
                continue
            hits = [cid for cid, r in rx.items() if _count_mentions(line, r) > 0]
            for i, a in enumerate(hits[:4]):
                for b in hits[i + 1:4]:
                    edges.append(Edge(f"k:{a}", f"k:{b}", "tension", -1, 1.5, line.strip().lstrip("-*0123456789.) ")[:140]))

    # ---- children and streams in the substrate layer ------------------
    for ch in children or []:
        nid = f"child:{ch['name']}"
        nodes[nid] = Node(nid, ch["name"], 0, "child", size=2.0, group="children", detail=ch.get("domain", ""),
                          meta={k: ch.get(k) for k in ("status", "report_count", "guidance_count")})
        edges.append(Edge(nid, "c:children", "flow", 1, 1.0, "reports"))
    for sid, label, detail in (("stream:markets", "Market data streams", "Polymarket / Kalshi order books"),
                               ("stream:resolutions", "Forecast resolutions", "questions resolving to 0/1")):
        nodes[sid] = Node(sid, label, 0, "stream", size=1.8, group="streams", detail=detail)
    edges.append(Edge("stream:markets", "k:prediction_market", "provenance", 1, 1.5, "observed"))
    edges.append(Edge("stream:markets", "k:edge_vs_market", "provenance", 1, 1.5, "observed"))
    edges.append(Edge("stream:resolutions", "c:forecasts", "flow", 1, 1.5, "resolve"))

    # ---- evidence overlay: Mandel's verdicts, the children's reports and their research ledger ----
    for ch in children or []:
        text = ch.get("text") or ""
        for cid, r in rx.items():
            n = _count_mentions(text, r)
            if n and f"k:{cid}" in nodes:
                edges.append(Edge(f"child:{ch['name']}", f"k:{cid}", "evidence", 1, float(min(6, 1 + math.log1p(n))),
                                  f"the child's reports mention it {n} time{'s' if n != 1 else ''}"))
    _verdict_overlay(nodes, edges, rx, theories, "stream:theories", "Mandel's tested theories",
                     "pre-registered theories and their verdicts (theories/registry.json)",
                     lambda t: f"{t.get('slug', '')} {t.get('claim', '')} {t.get('notes', '')}", lambda t: t.get("status", ""),   # notes carry the readings
                     ("supported",), ("not_supported",))
    _verdict_overlay(nodes, edges, rx, child_ledger, "stream:child-ledger", "Children's research ledger",
                     "the children's pre-registered tests (child repo docs/research_ledger.json)",
                     lambda t: f"{t.get('test', '')} {t.get('result', '')}", lambda t: str(t.get("verdict", "")).upper(),
                     ("PASS",), ("FAIL",))

    # ---- edges whose endpoints are missing are dropped ----------------
    edges = [e for e in edges if e.s in nodes and e.t in nodes]

    return {
        "generated_for": "Mandel signal map",
        "theories_unmatched": sorted(t.get("id") for t in (theories or []) if not any(_count_mentions(f"{t.get('slug', '')} {t.get('claim', '')} {t.get('notes', '')}", r) for r in rx.values())),
        "stats": {"nodes": len(nodes), "edges": len(edges), "documents": N,
                  "layers": {"substrate": sum(1 for n in nodes.values() if n.layer == 0),
                             "concepts": sum(1 for n in nodes.values() if n.layer == 1),
                             "principles": sum(1 for n in nodes.values() if n.layer == 2),
                             "centres": sum(1 for n in nodes.values() if n.layer == 3)}},
        "nodes": [asdict(n) for n in nodes.values()],
        "edges": [asdict(e) for e in edges],
    }


def _verdict_overlay(nodes, edges, rx, rows, sid, label, detail, text_of, status_of, good, bad):
    """One substrate node for a body of tests; an evidence edge to every concept the tests touch, positive when more of
    them passed than failed, negative otherwise, with the tally in the label and on the concept."""
    if not rows:
        return
    nodes[sid] = Node(sid, label, 0, "stream", size=2.2, group="streams", detail=detail, meta={"rows": len(rows)})
    texts = [(text_of(t), status_of(t) or "unknown") for t in rows]     # built once, not once per concept
    for cid, r in rx.items():
        k = f"k:{cid}"
        if k not in nodes:
            continue
        tally: dict[str, int] = {}
        for text, st in texts:
            if _count_mentions(text, r):
                tally[st] = tally.get(st, 0) + 1
        if not tally:
            continue
        g, b = sum(tally.get(x, 0) for x in good), sum(tally.get(x, 0) for x in bad)
        tested = g + b
        nodes[k].meta.setdefault("verdicts", {})[label] = tally
        desc = ", ".join(f"{v} {s.replace('_', ' ').lower()}" for s, v in sorted(tally.items(), key=lambda x: -x[1]))
        edges.append(Edge(sid, k, "evidence", 1 if g >= b and tested else -1, float(min(6, 1 + math.log1p(sum(tally.values())))),
                          f"{desc} ({g} of {tested} decided passed)" if tested else desc))


def write_graph(out_path: Optional[Path] = None, graph: Optional[dict] = None, **kw) -> Path:
    g = graph if graph is not None else build_graph(**kw)
    out = Path(out_path) if out_path else MANDEL_ROOT / "viz" / "graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, ensure_ascii=False, indent=0), encoding="utf-8")
    return out


TEMPLATE_PATH = MANDEL_ROOT / "viz" / "template.html"
HTML_PATH = MANDEL_ROOT / "viz" / "index.html"
PLACEHOLDER = "/*__GRAPH_JSON__*/"


def write_html(graph: Optional[dict] = None, template: Path = TEMPLATE_PATH, out: Path = HTML_PATH) -> Path:
    """Embed the graph JSON into the visualisation template."""
    g = graph if graph is not None else build_graph()
    tpl = Path(template).read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise ValueError(f"template lacks {PLACEHOLDER}")
    payload = json.dumps(g, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    Path(out).write_text(tpl.replace(PLACEHOLDER, payload), encoding="utf-8")
    return Path(out)
