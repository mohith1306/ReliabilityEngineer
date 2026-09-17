# CLAUDE.md — Working Agreement for Agents on This Repo

**Read this before touching anything.** It applies to Claude Code, IBM Bob, any other
agent, and any human working with one. It is short on purpose. The long-form vision is
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); read its corrections in
[docs/architecture/ERRATA.md](docs/architecture/ERRATA.md) before treating it as spec.

---

## 1. The one rule

> **Every working session writes a numbered memory file. No exceptions.**

This repo is built by a distributed team plus agents whose context window dies at the end
of every session. The memory ledger is the only thing that survives. A change that is not
in the ledger effectively did not happen, because the next person cannot find out why it
was made.

**Start of session** → `/session-start` (creates `docs/memory/sessions/NNNN-<slug>.md`)
**During session** → `/session-log` after each meaningful unit of work
**End of session** → `/session-end` (closes the file, updates the index and stage tracker)
**Picking up someone else's work** → `/catch-up` (reconstructs context from the ledger)

If you are an agent without slash commands, follow
[docs/memory/PROTOCOL.md](docs/memory/PROTOCOL.md) by hand. The protocol is the contract;
the commands are just a convenience wrapper over it.

---

## 2. What counts as a memory entry

Entries are numbered sequentially within a session file (`### 1.`, `### 2.`, …) and never
renumbered. Log an entry when you:

- make a decision that closes off an alternative
- discover something the repo does not already say (a constraint, a bug, a wrong assumption)
- change behaviour, schema, or a public interface
- hit a blocker, or unblock one
- verify something (tests, a benchmark run, a manual check)

Do **not** log routine mechanics — file reads, greps, a typo fix. The ledger is for things
a teammate would otherwise have to rediscover.

**Every entry carries evidence.** A claim with no `file:line`, command output, or artifact
path is a hypothesis, not a finding, and must be marked as such. This mirrors the product's
own memory contract (see §4) and it is not decoration: it is how we avoid a ledger full of
confident nonsense.

---

## 3. Stage discipline

Work is organised into stages tracked in [docs/stages/STAGES.md](docs/stages/STAGES.md).

- A stage has **verifiable exit criteria**. "Investigation engine done" is not a criterion;
  "`pytest tests/integration/test_investigation.py` passes and produces an evidence set of
  ≥5 items for the seeded failure" is.
- Never mark a stage `DONE` without naming the evidence that closes it.
- Never start a stage whose dependencies are not `DONE`, without logging why.

Check current state with `/stage`. Advance with `/stage advance <id>`.

---

## 4. Architectural non-negotiables

These come from the product thesis and from [ADR-0001](docs/decisions/ADR-0001-asmos-integration-posture.md).
Breaking one is an ADR-level decision, not an implementation detail.

1. **Bob is not reimplemented.** BRE orchestrates; Bob codes. If you find yourself writing
   a code-editing agent, stop.
2. **Reputation moves only on verification, never on generation.** Producing a diagnosis
   changes nothing. A *verified* or *refuted* outcome changes everything. (ASMOS Invariant 3.)
3. **Every computed score stores its components**, not just a scalar. A risk level of `HIGH`
   with no factor breakdown is unauditable and therefore unusable. (ASMOS Invariant 8.)
4. **Every prediction gets an outcome record.** Diagnoses, risk levels, and routing decisions
   are all predictions. See [ADR-0003](docs/decisions/ADR-0003-outcome-ledger.md).
5. **No write path to a target repo without a passed approval gate.** Analysis is free;
   mutation is privileged.
6. **The reliability loop must terminate.** Any re-investigation cycle carries an attempt
   counter and a hard cap.

---

## 5. Repository map

```
apps/api/           FastAPI surface — routes are thin; logic lives in services/
reliability/        The lifecycle engines (investigate, diagnose, risk, remediate, verify)
  ledger/           Outcome ledger — closes prediction→outcome. Everything learns from this.
  orchestration/    Workflow state machine driver
asmos_bridge/       Adapter onto the ASMOS memory/ownership/routing substrate.
                    NOT named `asmos/` — that would shadow the real installable package.
bob/                IBM Bob adapter (the external engineering capability)
connectors/         Repository / git / test / CI data sources
models/             Pydantic domain models (the wire + storage contract)
tests/              unit / integration / e2e
docs/
  ARCHITECTURE.md   Long-form vision. Aspirational; see ERRATA.
  architecture/     ERRATA.md (corrections), ASMOS_INTEGRATION.md (corrected §8)
  decisions/        ADRs — one file per irreversible decision
  memory/           THE SESSION LEDGER. Start here when you are lost.
  stages/           STAGES.md — where the build actually is
```

---

## 6. Conventions

- Python ≥ 3.11. `datetime.now(timezone.utc)`, never `datetime.utcnow()` (deprecated).
- Pydantic v2 models in `models/`; SQLAlchemy tables in `apps/api/database.py`. Keep them
  in sync or the API lies about what it stores.
- Routes do not touch the ORM directly once `apps/api/services/` exists.
- New table → new Alembic-shaped migration note in the session log, even though we are on
  `create_all` for now. Schema drift across teammates is the #1 way this repo breaks.
- Never commit `bre.db`, `.env`, or anything under `runs/`.
