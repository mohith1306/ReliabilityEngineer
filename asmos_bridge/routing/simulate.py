"""A cheap, faithful simulation of BRE's sequential routing policy -- used to tune tau.

Tuning tau on independent (memory, incident) *pairs* is the wrong model: the router does not score every
memory against every incident. It consults the SINGLE best-matching memory, in a sequence, with ownership
evolving as verified outcomes accumulate. Session 0009 first tuned on pairs and got "never route" for a corpus on
which the end-to-end harness then showed routing WINS (13 reuses, 4 refuted, net saving). The proxy was wrong.

So this simulates the real policy. It replays the exact decision rule of `TransactiveRouter` (same signature
cosine, same ASMOS trust/ownership/routing math, same class-B half updates, same "a memory that lost on this incident
is excluded from the retry") over an ordering of labelled incidents, and counts what would have happened:

    incident served from memory, memory right   -> saves one Bob diagnosis          (+save)
    incident served from memory, memory WRONG   -> a remediation is applied and
                                                   rolled back                        (-waste)
                                                   then Bob investigates, as the baseline would have

`label` is the ground truth the test suite would deliver: memory M is right for incident Q iff they share a group
(the same failure scenario). tau is then chosen to maximise mean net saving over MANY orderings -- so it does not
depend on the accident of one corpus order.

The simulator is validated against the end-to-end harness, not trusted on its own: `scripts/tune_tau.py` reports its
agreement with the latest measured comparison artifact.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence

from asmos_bridge.memory.store import cosine
from asmos_bridge.ownership.trust import ownership_score, routing_score, trust

HALF = 0.5  # class-B claims move reputation by half (asmos_bridge/ownership/reputation.py)
MAX_MEMORY_ATTEMPTS = 2  # BRE_MAX_ATTEMPTS defaults to 3: at most two memory attempts, the last attempt is Bob


@dataclass(frozen=True)
class Item:
    id: str
    topic: str
    group: str                 # the failure scenario: a memory is right for an incident iff groups match
    signature: tuple[str, ...]


@dataclass
class SimResult:
    tau: float
    served: int = 0
    refuted: int = 0
    utility: float = 0.0
    routed_ids: tuple[str, ...] = ()

    @property
    def precision(self) -> Optional[float]:
        return (self.served - self.refuted) / self.served if self.served else None


def simulate(order: Sequence[Item], tau: float, *, save: float, waste: float, frozen: bool = False) -> SimResult:
    """One ordering, one tau. `served` counts memory-served attempts (right or wrong)."""
    memory: dict[tuple[str, str], tuple[str, ...]] = {}   # (topic, group) -> signature of the incident that taught it
    counts: dict[tuple[str, str], list[float]] = {}       # (source, topic) -> [verified_correct, verified_total]
    res = SimResult(tau)
    routed: list[str] = []

    def cell(source: str, topic: str) -> list[float]:
        return counts.setdefault((source, topic), [0.0, 0.0])

    def ownership_of(topic: str) -> float:
        if frozen:
            return ownership_score(trust(0, 0), 0.0)
        mem_c, mem_t = cell("memory", topic)
        total_c = sum(c for (s, t), (c, _) in counts.items() if t == topic)
        share = (mem_c / total_c) if total_c > 0 else 0.0
        return ownership_score(trust(mem_c, mem_t), share)

    for q in order:
        tried: set[str] = set()
        answered = False
        for _attempt in range(MAX_MEMORY_ATTEMPTS):               # attempts 1..cap-1 may be memory; the last is Bob
            entries = [(g, sig) for (t, g), sig in memory.items() if t == q.topic and g not in tried]
            if not entries:
                break
            sim, best_group = max(((cosine(q.signature, sig), g) for g, sig in entries), key=lambda p: p[0])
            if routing_score(sim, ownership_of(q.topic)) < tau:
                break
            res.served += 1
            routed.append(q.id)
            if best_group == q.group:                              # the tests would pass: reuse confirmed
                res.utility += save
                cell("memory", q.topic)[0] += HALF
                cell("memory", q.topic)[1] += HALF
                answered = True                                    # answered from memory: nothing new is learned
                break
            res.refuted += 1                                       # the tests refute it, the patch is rolled back
            res.utility -= waste
            cell("memory", q.topic)[1] += HALF
            tried.add(best_group)                                  # the loser is excluded from the retry
        if answered:
            continue
        # a full Bob investigation (first sight, below tau, or the retry after refuted reuse)
        cell("bob", q.topic)[0] += HALF
        cell("bob", q.topic)[1] += HALF
        memory[(q.topic, q.group)] = q.signature                   # a verified diagnosis becomes memory (supersedes)
    res.routed_ids = tuple(routed)
    return res


def orderings(items: Sequence[Item], n: int) -> list[list[Item]]:
    """Ordering 0 is the given order; the rest are seeded shuffles (same scheme as the harness)."""
    out = [list(items)]
    for seed in range(1, n):
        shuffled = list(items)
        random.Random(seed).shuffle(shuffled)
        out.append(shuffled)
    return out


@dataclass(frozen=True)
class TuneResult:
    tau: float
    mean_utility: float
    curve: list[dict]
    never_route_utility: float = 0.0
    n_orderings: int = 0
    note: str = ""


def tune_by_simulation(items: Sequence[Item], *, save: float, waste: float, n_orderings: int = 50,
                       grid: Optional[Sequence[float]] = None) -> TuneResult:
    """Pick tau maximising mean net saving over many orderings. Ties break toward the STRICTER (higher) tau."""
    if grid is None:
        # every distinct cold-start-scaled similarity is a natural breakpoint; add a "never" sentinel
        cold = ownership_score(trust(0, 0), 0.0)
        sims = sorted({round(cosine(a.signature, b.signature), 4) for a in items for b in items if a.id != b.id})
        grid = sorted({round(s * cold - 1e-6, 4) for s in sims if s > 0} | {round(cold + 0.01, 4)})
    ords = orderings(items, n_orderings)
    curve = []
    for tau in grid:
        runs = [simulate(o, tau, save=save, waste=waste) for o in ords]
        curve.append({"tau": tau, "mean_utility": round(statistics.fmean(r.utility for r in runs), 2),
                      "mean_served": round(statistics.fmean(r.served for r in runs), 2),
                      "mean_refuted": round(statistics.fmean(r.refuted for r in runs), 2)})
    best = max(curve, key=lambda c: (c["mean_utility"], c["tau"]))
    never = next((c for c in curve if c["mean_served"] == 0), None)
    note = ""
    if best["mean_utility"] <= 0:
        note = "no threshold beats always running a full investigation on this data: the best policy is never to route"
    return TuneResult(best["tau"], best["mean_utility"], curve, never["mean_utility"] if never else 0.0,
                      len(ords), note)
