---
session: 0005
title: Bob interface spike + read-only adapter
author: opencode (mimo)
stage: S4
started: 2026-09-26T17:07:00Z
ended: 2026-09-26T17:45:00Z
status: closed
---

## Context on entry

S3 had just closed (session 0004, `origin/main` = `ce10669`). S4's sharpest risk
was thread 0001#7: Bob's integration mechanism was unverified. The stage tracker
required "the actual Bob interface confirmed by a working call". The user chose
the recommended path after the platform blocker surfaced: **protocol adapter +
protocol-faithful fake host** (over Docker/linux-server and GUI-driving routes).

## Entries

### 1. IBM Bob is a VS Code fork, and its programmatic surface is a local WebSocket server
- **Type:** finding (closes thread 0001#7)
- **What:** `/Applications/IBM Bob.app` is `bobide`, a VSCodium-derived editor
  (bundle `com.ibm.software.bob` 2.1.0). Its CLI exposes subcommands
  `chat` ("pass in a prompt ... in the current working directory") and
  `agent` ("Manage agent host sessions": `host` / `ps` / `stop` / `kill` /
  `logs`). `bobide agent host` starts a supervisor that binds a localhost
  WebSocket and writes a lockfile.
- **Why:** this is the interface every downstream stage needs; ARCHITECTURE.md
  §16 deliberately left the mechanism open ("determined from the current IBM
  Bob capabilities ... rather than hardcoded prematurely").
- **Evidence:** `bin/bobide --help` output (subcommands section);
  `bin/bobide-tunnel agent --help` (host/ps/logs + `--connection-token` flags);
  session artifacts under `/tmp/bob_host.log`
- **Status:** resolved

### 2. The host supervisor cannot start on macOS: IBM publishes no darwin server builds
- **Type:** blocker (platform), documented not worked around
- **What:** the supervisor downloads a REH server before listening. Every
  `darwin/*` URL returns `404 {"detail":"REH server not found"}` — for both
  `reh` and `reh-web`, across versions `1.126.0+bob2.0.0/bob2.1.0/bob2.2.0`
  and product-name variants. `linux/x64` and `win32/x64` return `302` to a
  signed S3 URL that serves a real 21,658,088-byte tarball (`curl -L` → 200).
  The supervisor therefore prints "ready" (management socket) but every WS
  call gets `503` until it dies with `ServerDownloadError`.
- **Why:** no `--agent-host-path` escape exists on `agent host` (internal
  only), the app bundle contains no server entry point, and Docker's daemon
  is not running. The user chose the protocol-adapter route rather than the
  Docker or GUI workarounds.
- **Evidence:** curl matrix in session transcript;
  `/Users/mohith/.bobide-server/cli/agent-host-stable.log` lines 5 and 12;
  `agent ps --json` → `HTTP error: 503`
- **Status:** open — owner: first linux/x64 run (thread 0005#1)

### 3. The wire protocol was recovered from the shipped binaries and app bundle
- **Type:** finding
- **What:** JSON-RPC 2.0 over WS. Requests `{jsonrpc:"2.0", id, method, params}`;
  responses `{jsonrpc,id,result|error}`; notifications carry no id. Methods:
  `initialize, ping, listSessions, createSession, createChat, subscribe,
  unsubscribe, dispatchAction, disposeSession, disposeChat, shutdown` plus
  `resource*`. `initialize` params `{channel:"ahp-root://", protocolVersions,
  clientId, initialSubscriptions}`. Sessions are `<provider>:/<uuid>`;
  chat channels are `ahp-chat://default/<ref>`; chat turns are dispatched as
  actions `{type:"chat/turnStarted", turnId, message:{text,
  origin:{kind:"user"}}}` (taxonomy of 26 action types recovered). Incoming
  routing keys on `method` are `dispatchAction` and `ping`. Lockfile:
  `{"schemaVersion":1,"pid","port","host","connectionToken",
  "protocolVersion":"0.1.0","quality"}`.
- **Why:** with the real host unstartable on this machine, static recovery is
  the only way to build against the real contract instead of a invented one.
- **Evidence:** `strings bin/bobide-tunnel` (`ahp-types-0.4.0`, method list,
  `ws://127.0.0.1:?tkn=`); `out/vs/workbench/workbench.desktop.main.js`
  `_dispatchRequest` → `{jsonrpc:"2.0",id:s,method:e,params:t}`; real lockfile
  read after the supervisor run
- **Status:** resolved (assumption flagged: exact default chat-channel
  encoding and turn-completion delivery shape — thread 0005#1)

### 4. Adapter built against the recovered contract; round trip proven over real sockets
- **Type:** change
- **What:** `bob/execution.py` (CLI probe, lockfile discovery with pid-liveness,
  `AgentHostClient`), `bob/prompts.py` (task/constraints/output contract per
  ARCHITECTURE §16), `bob/adapter.py` (`investigate`/`diagnose` returning
  `models/diagnosis.Diagnosis`; `remediate`/`verify` raise). Tests drive it
  against `tests/support/fake_bob_host.py`, which implements the recovered
  envelope, method set, action taxonomy, and a usage-bearing turn snapshot —
  served on a real localhost WebSocket.
- **Why:** S4's contract is the read boundary; proving it against a faithful
  fake keeps the darwin blocker from stalling every stage after it.
- **Evidence:** `tests/integration/test_bob_adapter.py` → 12 passed
- **Status:** resolved

### 5. Token cost lands in the ledger on every call
- **Type:** change (closes thread 0004#7 for the adapter path)
- **What:** after each turn the adapter sums `usage.promptTokens +
  completionTokens` and measured wall time, and opens the prediction through
  `open_diagnosis_prediction(..., cost_tokens=, cost_wall_ms=)` with
  components `provider / evidence_count / source_types / prompt_sha256 /
  turn_id`. The fake host reports 1500 + 420 tokens; the test asserts the
  rollup total.
- **Why:** ERRATA A8 — cost cannot be reconstructed after the fact; S9's
  cost-per-incident comparison reads these fields.
- **Evidence:** `test_investigate_returns_diagnosis_and_writes_ledger`
  (`cost_rollup` → 1920 tokens, wall_ms > 0)
- **Status:** resolved — when the real host reports different usage fields,
  only `_extract_turn`'s key mapping needs revisiting

### 6. Read-only is enforced four ways, not one
- **Type:** change
- **What:** (a) `remediate()`/`verify()` raise `NotImplementedError` naming
  the approval gate; (b) an end-to-end test hashes a fixture repo and its
  `git status` before/after `investigate(working_directory=...)` and asserts
  byte equality; (c) a source scan rejects write APIs (`write_text`,
  `shutil.copy`, `git commit`, ...) anywhere in `bob/*.py`; (d) a public-
  surface test fails if `BobAdapter` grows unexpected public methods.
- **Why:** CLAUDE.md non-negotiable 5 — no write path without a passed
  approval gate — and S4's explicit exit criterion.
- **Evidence:** four tests in `test_bob_adapter.py`, all passing
- **Status:** resolved

### 7. Real working calls recorded
- **Type:** verification (criterion 1)
- **What:** `probe_cli()` → `{'banner': 'IBM Bob 1.126.0+bob2.1.0',
  'version': '1.126.0+bob2.1.0'}` from the installed binary. Discovery parses
  the real lockfile format (tested with the exact JSON the supervisor wrote).
  `bobide-tunnel agent ps --json` → real CLI call
  (`no agent host process is currently running`). During the spike the
  supervisor itself completed its startup handshake: `ready in 1261ms`,
  `ws://localhost:49863?tkn=19bd3134-...`, lockfile written.
- **Why:** criterion 1 says "confirmed by a working call, not assumed".
- **Evidence:** commands above; `test_probe_cli_calls_the_installed_bob_binary`,
  `test_discovery_parses_the_real_lockfile_format`
- **Status:** resolved — the one call NOT possible on this machine is the WS
  round trip against the real host (entry 2)

## Close-out

- **Shipped:** `bob/` package (execution/prompts/adapter), protocol-faithful
  fake host, 12 tests; `websockets>=13.0` added to requirements.
- **Open threads:** #1 darwin host gap + chat-channel encoding + turn-completion
  delivery (owner: first linux/x64 run); 0001#8, 0002#7, 0003#7 carry over.
  0004#7 now closed (adapter writes cost on every call).
- **Next session should:** S5 — risk engine + approval gate: `RiskClassifier`
  with factor breakdown, reproducible levels, verified-identity approvals,
  and a test that HIGH/CRITICAL cannot reach REMEDIATING without an approval
  row (STAGES exit criteria).
- **Stage delta:** S4 NOT_STARTED → DONE
