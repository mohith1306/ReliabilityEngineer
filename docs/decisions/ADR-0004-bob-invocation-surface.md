# ADR-0004 — Bob Invocation Surface

- **Status:** Accepted
- **Date:** 2026-09-17
- **Session:** [0003](../memory/sessions/0003-bob-interface-confirmed.md)

## Context

ARCHITECTURE.md section 16 deliberately deferred the Bob integration mechanism
("determined from the current IBM Bob capabilities... rather than hardcoded"). Every
stage from S4 onward assumed one existed. Thread 0001#7 called this the largest
schedule risk in the project.

Investigation found two viable surfaces, and they point in opposite directions.

**Bob Shell, non-interactive.** `bob run --format json --mode ask|plan|agent`,
authenticated with `BOB_API_KEY`, emitting a result object whose `stats` block carries
`total_tokens`, `input_tokens`, `output_tokens`, cache counters, `duration_ms`,
`session_costs` and `tool_calls`. Supports `--workspace`, `--max-turns`, `--max-cost`,
`--resume <task-id>`, and switches to disable MCP servers, subagents and tool groups.

**MCP.** Bob is an MCP client and can consume external MCP servers. BRE could expose
its memory and ledger as an MCP server that a developer's Bob session calls.

## Decision

**Use `bob run` as the primary surface. BRE calls Bob.**

The direction of the call is the product thesis, not an implementation detail.
ARCHITECTURE.md Decision 1 says BRE orchestrates Bob. If BRE were an MCP server, Bob
would be the orchestrator and BRE a tool it optionally consults -- which inverts the
product into a retrieval plugin and discards the lifecycle, the risk gate and the
verification loop.

Mode mapping, which gives a structural rather than conventional safety boundary:

| BRE stage | Bob mode | Can write? |
|---|---|---|
| Investigate (S2), Diagnose (S4) | `ask` | no |
| Plan remediation (S5) | `plan` | no |
| Remediate (S6) | `agent` | **yes** |

**MCP is deferred, not rejected.** Once the lifecycle works, exposing BRE's engineering
memory as an MCP server is a genuinely good second surface: a developer inside the Bob
IDE could ask "what do we know about this component" and get BRE's verified history.
That is additive and does not invert anything. Revisit at S9.

## Consequences

**Positive.** Cost accounting is native (ERRATA A8) -- Bob reports its own tokens and
duration, so nothing has to be instrumented around it or reconstructed. Loop
termination is native (ERRATA A4) via `--max-turns` and `--max-cost`, enforced by Bob
rather than simulated. `--resume <task-id>` lets the reinvestigation loop continue a
task instead of restarting cold, which preserves context across attempts. The
read/write boundary is enforced by the mode flag rather than by developer discipline.

**Negative.** A subprocess boundary means parsing, timeouts and a dependency on the CLI
staying stable; a schema change breaks us at run time. Mitigated by `parse_result`
degrading missing fields to zero rather than crashing, and by a unit test pinned to the
documented schema so drift surfaces there first. It also means Bob Shell must be
installed wherever BRE runs, which is a real deployment constraint for anything
multi-tenant.

**Consequence for the data model.** The JSON result carries **no list of changed files**.
`Remediation.changed_files` must be derived from git rather than from Bob's output. This
is a better source anyway -- git records what actually changed, not what the agent
believes it changed -- but it means remediation always runs against a git checkpoint,
which S6 already required for rollback.

**Unresolved.** The contract is documented but not yet confirmed against a running Bob.
`scripts/verify_bob.py` closes it. Until then every claim here is read from docs, not
observed.

## Alternatives rejected

- **BRE as an MCP server that Bob calls.** Rejected as the primary surface: it inverts
  the orchestration direction and reduces the product to a tool. Kept as a future
  additive surface.
- **Driving the Bob IDE directly** (UI automation, extension host). Rejected: fragile,
  undocumented, and unusable in CI, which is where incidents actually originate.
- **Waiting for a REST API.** None is documented. Bob Shell is the supported
  programmatic path and it is sufficient.
