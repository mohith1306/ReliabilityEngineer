# ASMOS Integration — replaces ARCHITECTURE.md section 8

Source project: `C:\Users\csdee\PESU\CDSAML\ASMOS` (installable package `asmos`,
Python >= 3.11). Read `README.md`, `CONTRACT.md` and `docs/paper/paper.md` there before
building against it.

---

## 1. What ASMOS actually is

**Adaptive Semantic Memory Operating System** — a shared semantic-memory substrate for
teams of LLM agents, plus an ownership layer that decides *which agent to ask* for a given
query. Ownership is learned online from **verification-gated reputation**: a verified claim
raises an agent's ownership of a topic, a refuted claim lowers it, and queries route to the
learned owner with a confidence-gated fallback to global search.

It is **not** a retrieval-relevance ranker, and section 8 of ARCHITECTURE.md was wrong to
model it as one. See [ERRATA A1](ERRATA.md).

### The mechanism, in four equations

```
1. reputation_update(claim_class, verification_status)
      class A (objective)  verified -> full update    refuted -> full negative
      class B (derived)    verified -> half update    refuted -> half negative
      class C (subjective) never moves reputation

2. Trust(a,T) = (alpha + verified_correct) / (alpha + beta + verified_total)
      alpha=7, beta=3  ->  cold-start 0.70, and the prior decays as evidence accumulates

3. Ownership(a,T) = 0.6 * Trust(a,T) + 0.4 * ContributionShare(a,T)

4. RoutingScore(a,q) = Sim(q,T) * Ownership(a,T)
      best score < tau  ->  GLOBAL_SEARCH (cold start / no confident owner)
      best score >= tau ->  ROUTE to top-k owners
```

`tau` is tuned on real query distributions, not hardcoded (default 0.35; the frozen
headline value is 0.351492, and it is embedder-specific).

### Two invariants BRE inherits

- **Invariant 3 — reputation moves only after verification, never on generation.**
  Producing a diagnosis changes nothing. A verified or refuted outcome changes everything.
- **Invariant 8 — every computed score stores its components.** A routing decision records
  similarity, ownership, tau and action; a risk level records its factor breakdown. A bare
  scalar is unauditable.

Both are already non-negotiables in [CLAUDE.md](../../CLAUDE.md) section 4.

---

## 2. What ASMOS has already demonstrated

Numbers from the ASMOS README, each citing a stamped artifact in that repo. Quoted here so
BRE's claims inherit the right level of confidence — and the right caveats.

| Result | Number |
|---|---|
| Routing cost reduction vs global search, at equal accuracy | **-23.84% +/- 0.15** LLM tokens per query |
| Cause is ownership *evolution*, not the prior (single-variable ablation) | +39.14 +/- 0.43 tokens/query, never inverts |
| Adaptation under drift / refutation / new topic | **0 retrains**, vs 1-6 for a supervised classifier |
| Cross-model replication (MiniLM / MPNet / BGE) | 0 retrains in every completed cell |
| Convergence sample-efficiency | **honest FLAT null** — 0 of 12 win cells |

**Carry the caveats too.** ASMOS is roughly 80-85% of its frozen spec; every LLM number
uses a single model at N=5; ownership asymmetry did **not** emerge organically in its corpus
study (the corpus was deliberately constructed); and the convergence hypothesis returned a
null. Overstating any of this in a demo is the fastest way to lose a technical judge.

---

## 3. The bridge that already exists

`src/asmos/prototypes/git_ownership.py` in the ASMOS repo runs the entire mechanism over a
real git history:

- **topics** = top-level source directories
- **claim** = a commit, authored by an agent, touching a topic
- **verified** = merged to main
- **refuted** = a detected `git revert`
- it builds Checkpoints, calls `set_verification`, feeds `OwnershipRuntime`, and returns a
  live `TransactiveRouter`

That is BRE's integration shape, already written and already pointed at git. It is marked
"not part of the paper's evidence chain, makes no research claim" — and it has **no committed
results**. Turning it into a measured result on incident data is available work, and it is
the shortest path from ASMOS's research artifact to BRE's product claim.

---

## 4. The mapping onto BRE

| ASMOS concept | BRE concept |
|---|---|
| Topic `T` | A component / subsystem of the target repository |
| Agent `a` | A **source of diagnosis** — IBM Bob, a specific human from git blame, a prior incident, a static analyzer |
| Checkpoint | A root-cause hypothesis with its evidence set |
| Claim class A / B / C | A = reproduced failure, B = inferred cause, C = speculation. Only A and B move reputation |
| **Verification** | **The test suite.** Deterministic, not LLM-judged |
| Refutation | Verification failed, or the fix was reverted / rolled back |
| `Sim(q,T)` | Incident-to-component similarity |
| `Ownership(a,T)` | How often this source has been *verifiably right* about this component |
| `tau` fallback | No confident owner, so fall back to full investigation — expensive but correct |
| Ownership evolution | The system gets cheaper per incident as it learns who is right where |

### The one place BRE is strictly stronger than ASMOS

ASMOS's own stated limitation is that its QA-ladder grading is **LLM-judged**. BRE's
verification signal is a **test suite exit code**. That is a harder, cheaper, and
non-circular ground truth than the research setting had. If ASMOS's mechanism works on a
noisy LLM-judged signal, a deterministic signal is a favourable change of regime — and it
removes the "you graded yourself" objection entirely.

This is the single most defensible technical point in the whole project. Lead with it.

---

## 5. Integration posture — vendored bridge, not a dependency

BRE does **not** `pip install asmos`. Reasons:

1. ASMOS pulls `chromadb`, `scikit-learn`, `numpy`, and optionally a ~2GB torch stack for
   the sentence-transformer embedder. That is a heavy, slow, fragile dependency for a
   hackathon demo that must start reliably in front of judges.
2. ASMOS is a research artifact organised "for reviewers and reproducers, not for product
   use" — its own README says so. Its API is frozen for reproducibility, not for consumers.
3. A demo that dies on a model download is a lost demo.

Instead, `asmos_bridge/` re-implements the **math** — which is a few pure functions, all
readable in `src/asmos/ownership/trust.py` — against BRE's own storage, and keeps the
interfaces shaped so the real package can be swapped in behind them later.

What gets re-implemented (small, pure, testable):

```
asmos_bridge/ownership/trust.py       Beta-prior trust, ownership score, routing score
asmos_bridge/ownership/reputation.py  claim-class-gated reputation updates
asmos_bridge/ownership/ledger.py      per-(source, topic) verified counts
asmos_bridge/routing/router.py        tau-gated routing decision with audit components
asmos_bridge/memory/checkpoint.py     the memory record, shaped to ASMOS CONTRACT.md v1.2
```

**Attribution matters.** These are ASMOS's equations, and the ASMOS repo is the citation.
Every module in `asmos_bridge/` names the file it derives from. If ASMOS's paper numbers are
quoted in a demo, they are quoted as ASMOS results, not as BRE results.

**Parity is a test, not a hope.** `tests/unit/test_asmos_parity.py` asserts the bridge's
`trust()`, `ownership_score()` and `routing_decision()` return values identical to the
reference implementation on a fixed vector table lifted from the ASMOS tests. If the bridge
drifts, the test fails.

---

## 6. What this replaces in ARCHITECTURE.md section 8

The three interfaces the doc sketched are kept, with corrected semantics:

```python
class TaskAnalyzer:
    def analyze(self, incident) -> IncidentTask:
        """Classify the incident and identify candidate topics (components).
        Unchanged in spirit from section 8."""

class ContextRouter:
    def route(self, task) -> RoutingDecision:
        """NOT a file ranker. Returns which diagnosis source(s) to consult,
        with the components of the decision: per-topic similarity, per-source
        ownership, tau, and the action taken (ROUTE | GLOBAL_SEARCH)."""

class ContextRanker:
    def rank(self, task, candidates) -> list[ScoredContext]:
        """Ranks *evidence candidates* for the chosen route. This is the ordinary
        retrieval step, and it is honestly a RAG-shaped problem — ASMOS's own
        README says ASMOS does not win at span retrieval. Do not attribute this
        component's performance to ASMOS."""
```

Keeping `ContextRanker` honest matters: it is the part where a judge could reasonably ask
"isn't this just RAG?" The answer is yes for the ranker, and no for the router — and being
able to say which is which is what makes the claim credible.

---

## 7. Open questions this integration rests on

Both are live threads in the session ledger. Neither is answered yet, and the project
should not speak as though they are.

- **Does ownership asymmetry actually exist in a real repository's incident history?**
  ASMOS found it does **not** emerge organically in its constructed corpus. Code ownership
  intuitively *is* asymmetric — that is what git blame measures — but "intuitively" is not
  a result. `git_ownership.py` is the instrument to test it, and it has never been run to a
  committed result. **Run it against a real repo before building S8 on the assumption.**
  (Thread 0001#8.)

- **Are there enough incidents in a hackathon-scale demo for ownership to evolve at all?**
  Ownership starts at the 0.70 cold-start prior and moves on verified outcomes. With five
  incidents it will barely move, and the routing story degenerates to "always fall back to
  global search" — which is correct behaviour but an unconvincing demo. The corpus needs to
  be large enough that evolution is visible, which is why S3 requires >= 10 seeded incidents
  and why that stage is pulled early.
