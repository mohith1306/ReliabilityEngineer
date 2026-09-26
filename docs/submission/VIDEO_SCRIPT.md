# Demo video script — target 3:00

Record the dashboard at 1080p, browser zoom ~110%, dark theme. Record voice separately if the room is loud.
**Decide before recording whether this is a LIVE or a SIMULATED run, and say which in the first 15 seconds.**
The pill in the corner will show it anyway; a mismatch between what you say and what it shows is the one thing to avoid.

| Time | On screen | Say (edit to taste) |
|---|---|---|
| 0:00 | Title card: **Bob Reliability Engineer**; tagline *"Don't just generate a fix. Verify it — and learn who was right."* | "AI agents like IBM Bob can write a fix in minutes. The question every team then asks is: was it right, was it safe, and did we learn anything?" |
| 0:15 | Dashboard; point at the mode pill | "This run uses **[live IBM Bob | a labelled Bob stand-in]** — you can see it here. Everything else you'll see is real: git, the test suite, the gate, the ledger." |
| 0:25 | Create *Connection pool exhaustion* → Run. Stops at AWAITING APPROVAL; open **Risk & approval** | "BRE gathers evidence, has Bob diagnose it read-only, and scores the risk — every factor visible. It's HIGH, so it stops. **Nothing has touched the repository.**" |
| 0:55 | Paste operator key → Approve | "A human approves — and the record stores who, from an API key. Never a name typed into a form." |
| 1:05 | Run → RESOLVED. Open **Patch**, then **Verification** | "The fix lands on its own branch after a pinned checkpoint. Then it's verified three ways: the failing test, its whole file, the entire suite. Only then is it called fixed." |
| 1:25 | **Ledger** tab | "Every prediction — diagnosis, risk, the fix — was written down *before* anyone knew if it was right, and closed only by that test run." |
| 1:40 | Create the **same** incident again → Run; open **Diagnosis** | "Same failure again. This time the diagnosis comes from **memory, at zero Bob cost** — because a passing test suite already vouched for it. That's ASMOS: trust earned by verification, not by similarity." |
| 2:00 | Create the **look-alike** → Run → Approve → Run; show the rollback, then **Ledger** (refuted) | "Now a trap: same symptom, different cause. Memory answers, the patch goes in, and **the tests say no**. BRE rolls it back, records the diagnosis as *refuted*, and stops offering that memory. Attempt two does a full investigation and finds the real cause." |
| 2:35 | **What BRE has learned** → **Evaluation** | "Ownership is computed only from verified outcomes. On recurring failures, 6 of 10 diagnoses came from memory with none refuted. On a corpus with look-alike twins the tests refuted 4 of 13 reuses — each rolled back and retried — and it was still about 10% cheaper, with the same resolution. **[Costs are nominal while Bob is simulated.]**" |
| 2:55 | Repo URL | "Bob Reliability Engineer: don't just generate a fix — verify it, and learn who was right." |

## Do-nots

- Do not describe a SIMULATED run as Bob's work.
- Do not show the operator key of a real deployment. (The demo key is public by design and says so.)
- Do not quote a token saving without "nominal" unless the run was live and measured.
- Do not skip the look-alike: it is the strongest evidence that the safety story is real.
