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

    def as_dict(self) -> dict:
        return {
            "tau": round(self.tau, 6), "youden_j": round(self.j, 6), "method": self.method,
            "confusion": {"tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn},
            "n": self.n, "score_range": [round(x, 6) for x in self.score_range], "notes": self.notes,
        }


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
