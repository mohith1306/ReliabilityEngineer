# ARCHITECTURE.md — Errata

`docs/ARCHITECTURE.md` is the vision document. It is kept intact because the vision is
sound. This file lists what is **wrong, stale, or internally contradictory** in it, so no
one builds from a bad line. Read this before treating the big doc as spec.

Each item: what the doc says, what is actually true, what to do.

---

## A. Substantive — these change what gets built

### A1. Section 8 mischaracterises ASMOS  *(the most important item here)*

**Doc says:** ASMOS is a "Context Engine" doing Task Analysis, Context Router, Context
Ranker, whose output is a relevance-ranked list of *files* (`auth/service.py 0.96`,
`auth/client.py 0.94`, ...).

**Actually true:** ASMOS routes **agents**, not files. Its output is a decision about
*who to ask*, from a learned per-(agent, topic) ownership score, updated only on verified
outcomes. Its own README states plainly that it does **not** beat RAG on span-retrieval QA
and "is not a QA-accuracy method" — so section 8 proposes using it for the one job its
authors measured it as not winning.

The mechanism the doc omits entirely is the one that matters:

```
Ownership(a,T) = 0.6 * Trust(a,T) + 0.4 * ContributionShare(a,T)
Trust(a,T)     = (alpha + verified_correct) / (alpha + beta + verified_total)
RoutingScore   = Sim(q,T) * Ownership(a,T)  ->  tau-gated, else GLOBAL_SEARCH
```

**Do:** treat [ASMOS_INTEGRATION.md](ASMOS_INTEGRATION.md) as the replacement for section 8.

---

### A2. Section 34 builds the write path before the safety gate

**Doc says:** Phase 4 = Bob adapter + remediation orchestration. Phase 5 = risk engine +
approval workflow.

**Contradicts:** section 5 (state machine), section 26 (MVP workflow) and section 24
("Approve explicitly, Execute safely") all put risk and approval *before* remediation.

**Do:** use the corrected order in [../stages/STAGES.md](../stages/STAGES.md). Risk and
approval (S5) precede remediation (S6).

---

### A3. Nothing in the data model can close a prediction

**Doc says:** section 30 lists Root Cause Accuracy, Verification Success Rate, Regression
Rate, Context Rediscovery Rate as success metrics. Section 9 says memory should hold
"confirmed root causes" and learn "only from verified outcomes."

**Actually true:** `DiagnosisDB` has no verification field. `RiskAssessmentDB` has no
record of whether the level was right in hindsight. There is no table linking a prediction
to its eventual outcome. As designed, **not one of section 30's accuracy metrics is
computable**, and the learning loop of section 9 has no input.

**Do:** [ADR-0003](../decisions/ADR-0003-outcome-ledger.md). This is stage S3 and it is
pulled ahead of Bob integration.

---

### A4. The reliability loop has no termination condition

**Doc says:** section 15 — verification failure, re-investigation, remediation,
verification, "this creates the autonomous reliability loop." Section 5 shows
`VERIFYING -> REINVESTIGATING -> INVESTIGATING`.

**Actually true:** no attempt counter, no cap, no cost ceiling. A system that runs a coding
agent against a repository and cannot decide to stop is a defect, not a feature.

**Do:** attempt counter on the incident, hard cap, and an explicit `ABANDONED` outcome.
Exit criterion on S7.

**Update (session 0003):** Bob Shell provides `--max-turns <n>` and `--max-cost <bobcoins>`
natively, so the per-call bound is enforced by Bob rather than simulated by us
(`bob/adapter.py`). BRE still owns the *cross-call* bound — the number of
reinvestigation cycles per incident — which Bob knows nothing about.

---

### A5. The state machine has no failure or abort paths

**Doc says:** sections 5 and 37 give a single happy path plus one re-investigation branch.

**Actually true** (`models/incident.py:28`): `VALID_TRANSITIONS` has no route out of
`INVESTIGATING` or `REMEDIATING` on failure — but `InvestigationStatus.FAILED` and
`RemediationStatus.FAILED` both exist, so those sub-states are unreachable from the
incident's point of view and the incident is stuck. There is also no `DETECTED -> CLOSED`,
so a false alarm or duplicate can never be closed. And `RemediationStatus.ROLLED_BACK`
exists with no corresponding incident state, though section 25 requires rollback.

**Do:** add `FAILED` / `ABANDONED` states, a `DETECTED -> CLOSED` edge, and a rollback path.

---

### A6. Approvals are unauthenticated

**Doc says:** section 12 — "Approval must be auditable." Section 24 lists explicit approval
for high-risk changes as a required control.

**Actually true:** `ApprovalDB.approved_by` is a free-text string
(`apps/api/database.py:103`) with no identity check anywhere, and the API has no auth at
all. Anyone who can reach the endpoint can approve a `CRITICAL` change as anyone.

**Do:** verified identity on approval records is an exit criterion of S5. Until then the
approval gate is decorative — do not describe it as a safety control in a demo.

---

### A7. No multi-repo, multi-agent, or tenancy model

**Doc says:** section 26 scopes the MVP to one repository, which is reasonable. But section
36's north star and the "huge scale" framing imply many repos, many teams, many agents.

**Actually true:** nothing in the schema or the API carries a tenant, an org, or an agent
identity. `incidents.repository` is a bare string. Retrofitting tenancy after the ledger
has data is expensive.

**Do:** carry `tenant_id` and `agent_id` from the first ledger write even while the MVP
runs single-tenant. Cheap now, painful later.

---

### A8. No cost or token accounting

**Doc says:** section 30 does not list cost. The ASMOS headline result BRE would inherit
*is* a cost result (-23.8% tokens).

**Actually true:** nothing measures tokens, wall time, or LLM calls per incident.

**Do:** instrument token and latency per Bob call from the very first adapter call (S4 exit
criterion). A cost claim cannot be reconstructed retroactively.

**Update (session 0003):** resolved at the source. `bob run --format json` reports
`stats.total_tokens`, `input_tokens`, `output_tokens`, cache counters, `duration_ms`,
`session_costs` and `tool_calls`. `BobUsage` in `bob/adapter.py` carries them straight
into `OutcomeRecord.cost_tokens` / `cost_wall_ms`. Nothing needs instrumenting around Bob.

---

## B. Stale — the doc drifted from the code

| Section | Doc says | Code says |
|---|---|---|
| 20 | `remediations` has no `changed_files` / `tests_added` | both exist as JSON columns (`apps/api/database.py:116`) |
| 20 | `verification_runs` has no `remediation_id` | it exists and is `nullable=False` (`apps/api/database.py:127`) |
| 21 | tree shows `reliability/`, `asmos/`, `bob/`, `connectors/`, `tests/` | created in this session; were absent |
| 37 | `cd bob-reliability-engineer` | the directory is `ReliabilityEngineer` |
| 37 | POSIX venv activation | primary dev machine is Windows; the activate path differs |
| 37 | "Testing: pytest" | `pytest` is not in `requirements.txt` and no tests exist |
| 16 | `BobAdapter` exposes `investigate` / `remediate` / `verify` | section 10 assigns root-cause analysis to Bob, so `diagnose` was missing. **Fixed** — `bob/adapter.py` exposes `investigate` / `diagnose` / `plan_remediation` / `remediate` |
| 18 | `POST /api/remediations/{id}/approve` | approvals are keyed by `incident_id` (section 12, and `ApprovalDB`), so the route is on the wrong noun |

Three declared dependencies are unused: `aiosqlite` (the engine is sync), `httpx` (no Bob
client yet), `gitpython` (no git connector yet). Harmless, but they imply capability the
repo does not have.

---

## C. Naming collision — acted on

Section 21 proposes a top-level `asmos/` package. The real ASMOS installs as an importable
package literally named `asmos` (its `pyproject.toml` declares `name = "asmos"`). A local
top-level `asmos/` directory shadows it, and an editable install of the research repo would
then break in ways that look like nothing.

**Done:** the directory is `asmos_bridge/`. It adapts onto ASMOS; it does not impersonate it.

---

## D. Confirmed correct

For the avoidance of doubt, these parts of the doc hold up and should not be second-guessed:

- 4.2 evidence-before-remediation, 4.3 mandatory verification, 4.4 human control for risky
  operations, 4.6 learn only from verified outcomes — all sound, and 4.6 is precisely the
  ASMOS invariant.
- Section 5 state definitions and the implemented transition table agree with each other.
- Section 19 entity relationships match the tables.
- Section 33 "what not to build" is good discipline and should be enforced.
- Section 35's first milestone is the right milestone.
