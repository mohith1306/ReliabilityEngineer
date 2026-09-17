# Bob Reliability Engineer (BRE)

**A software-reliability layer around IBM Bob.** Bob finds and writes the fix; BRE decides
whether it should be trusted — by building evidence, assessing risk, gating the write path
on human approval, verifying the result independently, and remembering which sources of
diagnosis turned out to be *verifiably right* about which parts of the system.

```
Detect → Investigate → Diagnose → Assess Risk → Approve → Remediate → Verify → Learn
```

> Do not just generate a fix. Build evidence, assess risk, verify the fix, and learn from
> the incident.

---

## Start here

| If you are... | Read |
|---|---|
| Any agent working on this repo | **[CLAUDE.md](CLAUDE.md)** — the working agreement. Not optional. |
| Joining, or returning after time away | run `/catch-up`, or read [docs/memory/INDEX.md](docs/memory/INDEX.md) bottom-up |
| Wondering where the build is | [docs/stages/STAGES.md](docs/stages/STAGES.md) |
| Reading the architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — **and** its [ERRATA](docs/architecture/ERRATA.md) first |
| Wondering why something is the way it is | [docs/decisions/](docs/decisions/) |

The architecture document is aspirational and contains known inaccuracies. The errata lists
them. Treat the errata as authoritative where the two disagree.

---

## The distinctive part

BRE's engineering memory is built on the **ASMOS** mechanism — learned per-topic ownership
from verified outcomes. Rather than retrieving "files similar to the error," it learns
*which source of diagnosis has been verifiably correct about this component before*, and
routes accordingly, falling back to full investigation when no source confidently owns the
topic.

The reason this fits reliability engineering better than it fits general QA: **the verifier
is a test suite.** Verification is a deterministic exit code, not a model grading itself.
That is a harder ground truth than the research setting had.

See [docs/architecture/ASMOS_INTEGRATION.md](docs/architecture/ASMOS_INTEGRATION.md).
Upstream: `C:\Users\csdee\PESU\CDSAML\ASMOS`.

---

## Layout

```
apps/api/        FastAPI surface. Routes stay thin; logic belongs in services/
reliability/     Lifecycle engines: investigator, diagnosis, risk, remediation,
                 verification, ledger, orchestration
asmos_bridge/    Ownership / routing / memory, adapted from ASMOS
bob/             IBM Bob adapter — the external engineering capability
connectors/      repository · git · tests · ci  (all read-only)
models/          Pydantic domain models
tests/           unit · integration · e2e
docs/            architecture · decisions (ADRs) · memory (session ledger) · stages
```

---

## Running it

**Use CPython, not the msys2 Python.** On a machine with msys2/MinGW on PATH, a bare
`python` may resolve to the msys2 build under `C:\msys64\ucrt64\bin`, which creates a
POSIX-layout venv (`bin/`, not `Scripts/`) and cannot install anything — its SSL has no
trusted root store, so every pip download fails certificate verification. Point at CPython
explicitly:

```bash
"$LOCALAPPDATA/Programs/Python/Python313/python.exe" -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt
venv/Scripts/python.exe -m uvicorn apps.api.main:app --reload --port 8001
```

API docs at `http://localhost:8001/docs`.

```bash
venv/Scripts/python.exe -m pytest
```

**Current state:** Phase 1 (models, incident state machine, SQLite, two routers) is
implemented and verified — **20 passed, 3 xfailed** on Python 3.13.7. The three xfails are
strict and deliberate: they pin the known integrity gaps from
[ERRATA](docs/architecture/ERRATA.md) (no FK check on `incident_id`, `started_at` never set,
no `DETECTED → CLOSED` edge) so the suite fails loudly the day someone fixes one without
updating the docs. Everything from stage S2 onward is scaffolded with contracts but not
built — see [STAGES.md](docs/stages/STAGES.md).


---

## The one rule

Every working session writes a numbered memory file under `docs/memory/sessions/`.
`/session-start` to open, `/session-log` as you go, `/session-end` to close. A change that
is not in the ledger effectively did not happen, because the next person cannot find out
why it was made.
