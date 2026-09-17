# Architecture Decision Records

One file per decision that is expensive to reverse. Numbered, immutable once accepted.

A decision belongs here if reversing it later would mean rewriting code that other code
depends on, migrating stored data, or re-running experiments. Everything else belongs in a
session memory entry.

**Format:** `ADR-NNNN-<kebab-slug>.md` with Status / Context / Decision / Consequences /
Alternatives rejected. The "alternatives rejected" section is the part with long-term
value — it stops the team relitigating settled questions.

**Superseding:** never edit an accepted ADR. Write a new one and set the old one's status
to `Superseded by ADR-NNNN`.

| # | Title | Status |
|---|---|---|
| [0001](ADR-0001-asmos-integration-posture.md) | ASMOS integration posture | Accepted |
| [0002](ADR-0002-session-memory-protocol.md) | Session memory protocol | Accepted |
| [0003](ADR-0003-outcome-ledger.md) | Outcome ledger | Accepted |
