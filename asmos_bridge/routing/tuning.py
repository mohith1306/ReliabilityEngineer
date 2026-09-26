"""Tune tau from data -- never hardcode it.

tau is embedder- and corpus-specific (ASMOS's own frozen 0.351492 is for all-MiniLM-L6-v2). BRE's
similarity is a keyword cosine, so ASMOS's number does not transfer; this module derives tau from
labelled routing situations and the run is stamped as an artifact.

Input: (score, applicable) pairs, where `score` is the RoutingScore memory would get for some
incident and `applicable` is whether that memory's diagnosis is actually the right one for it.
Method: choose the threshold maximising Youden's J = TPR - FPR (ties broken toward the HIGHER tau,
because a wrongly reused diagnosis costs a failed attempt while a missed reuse costs only tokens).

Honest limits, reported in the artifact rather than buried: similarity cannot separate an incident
that merely *looks* like a past one from one that *is* one. Those "hard negatives" are exactly what
verification and the trust update exist to catch; tuning tau does not pretend to.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TuningResult:
    tau: float
    j: float
    tp: int
    fp: int
    fn: int
    tn: int
    n: int
    method: str = "youden_j_max_tie_high"
    score_range: tuple[float, float] = (0.0, 0.0)
    notes: list[str] = field(default_factory=list)
    utility: float | None = None       # expected net saving at this tau, in the caller's cost units
    never_route: bool = False          # the best policy on this data is to always fall back to a full investigation

    def as_dict(self) -> dict:
        d = {
            "tau": round(self.tau, 6), "youden_j": round(self.j, 6), "method": self.method,
            "confusion": {"tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn},
            "n": self.n, "score_range": [round(x, 6) for x in self.score_range], "notes": self.notes,
        }
        if self.utility is not None:
            d["expected_net_utility"] = round(self.utility, 2)
            d["never_route"] = self.never_route
        return d


def tune_tau_utility(labelled: list[tuple[float, bool]], *, save: float, waste: float) -> TuningResult:
    """Choose tau to maximise expected NET saving:  tp * save  -  fp * waste.

    Youden's J weighs a false reuse and a missed reuse equally; they are not equal. A correct reuse saves
    one diagnosis (`save`); a wrong one wastes a whole remediation attempt (`waste`). Reuse therefore only
    pays when precision exceeds waste / (save + waste). Where similarity cannot deliver that precision
    (look-alikes that share a failure signature with true matches), the honest optimum is NEVER to route
    -- always investigate -- and this reports that instead of forcing a threshold.

    Ties break toward the stricter tau. `save`/`waste` are whatever units the caller supplies (BRE passes
    nominal token costs and labels them as such).
    """
    pos = [s for s, ok in labelled if ok]
    neg = [s for s, ok in labelled if not ok]
    if not pos or not neg:
        raise ValueError("tuning needs both applicable and non-applicable examples")

    scores = sorted({s for s, _ in labelled})
    never = scores[-1] + 1e-6
    candidates = [scores[0] - 1e-9] + [(a + b) / 2 for a, b in zip(scores, scores[1:])] + [never]

    best = None
    for tau in candidates:
        tp = sum(1 for s in pos if s >= tau)
        fp = sum(1 for s in neg if s >= tau)
        u = tp * save - fp * waste
        key = (u, tau)
        if best is None or key > best[0]:
            best = (key, tau, tp, fp)
    _, tau, tp, fp = best
    fn, tn = len(pos) - tp, len(neg) - fp
    utility = tp * save - fp * waste
    never_route = tp == 0 and fp == 0
    notes = [f"break-even precision for reuse is {waste / (save + waste):.2f} (waste {waste:g} / (save {save:g} + waste {waste:g}))"]
    if never_route:
        notes.append("no threshold clears break-even precision on this data: the best policy is to always run a "
                     "full investigation. Routing would cost more than it saves.")
    elif fp:
        notes.append(f"{fp} non-applicable pair(s) still score >= tau: similarity cannot reject them; verification "
                     "and the trust update must")
    return TuningResult(tau, tp / len(pos) - fp / len(neg), tp, fp, fn, tn, len(labelled),
                        method="expected_net_utility_max_tie_high", score_range=(scores[0], scores[-1]),
                        notes=notes, utility=utility, never_route=never_route)


def tune_tau(labelled: list[tuple[float, bool]]) -> TuningResult:
    pos = [s for s, ok in labelled if ok]
    neg = [s for s, ok in labelled if not ok]
    if not pos or not neg:
        raise ValueError("tuning needs both applicable and non-applicable examples")

    scores = sorted({s for s, _ in labelled})
    # candidate thresholds: midpoints between adjacent distinct scores (+ the extremes)
    candidates = [scores[0] - 1e-9] + [(a + b) / 2 for a, b in zip(scores, scores[1:])] + [scores[-1] + 1e-9]

    best = None
    for tau in candidates:
        tp = sum(1 for s in pos if s >= tau)
        fn = len(pos) - tp
        fp = sum(1 for s in neg if s >= tau)
        tn = len(neg) - fp
        j = tp / len(pos) - fp / len(neg)
        key = (j, tau)  # max J, then the higher tau
        if best is None or key > best[0]:
            best = (key, tau, tp, fp, fn, tn)
    _, tau, tp, fp, fn, tn = best
    notes = []
    if fp:
        notes.append(f"{fp} non-applicable example(s) still score >= tau: similarity alone cannot reject "
                     "them; verification and the trust update must")
    if fn:
        notes.append(f"{fn} applicable example(s) score < tau and will fall back to a full investigation")
    return TuningResult(tau, tp / len(pos) - fp / len(neg), tp, fp, fn, tn, len(labelled),
                        score_range=(scores[0], scores[-1]), notes=notes)
