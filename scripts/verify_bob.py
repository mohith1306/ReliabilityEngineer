"""Close thread 0001#7: prove one real round-trip to IBM Bob, with cost captured.

Run this once BOB_API_KEY is set and Bob Shell is installed:

    venv/Scripts/python.exe scripts/verify_bob.py

It makes ONE ask-mode (read-only) call with a tight turn cap, prints the token and
timing block, and writes a stamped artifact under docs/artifacts/. That artifact is
the evidence that closes the thread and unblocks stage S4.

Read-only by construction: ask mode cannot modify the workspace, and this script
never touches remediate().
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bob.adapter import BobAdapter, BobError, BobNotAvailable  # noqa: E402

PROMPT = (
    "In one short paragraph, what is the purpose of the models/ package in this "
    "repository? Do not modify any files."
)


def main() -> int:
    adapter = BobAdapter(workspace=REPO_ROOT, max_turns=3)

    pre = adapter.preflight()
    print("=" * 70)
    print("PREFLIGHT")
    print("=" * 70)
    print(f"  binary found : {pre.binary_found}  ({pre.binary_path or 'not on PATH'})")
    print(f"  BOB_API_KEY  : {'set' if pre.api_key_set else 'NOT SET'}")
    print(f"  version      : {pre.version or 'unknown'}")
    if not pre.ready:
        print()
        print(pre.explain())
        print()
        print("Thread 0001#7 remains OPEN. Nothing was called, nothing was billed.")
        return 2

    print()
    print("=" * 70)
    print("ROUND TRIP (ask mode, read-only, max 3 turns)")
    print("=" * 70)
    try:
        result = adapter.investigate(PROMPT)
    except (BobNotAvailable, BobError) as exc:
        print(f"  FAILED: {exc}")
        print()
        print("Thread 0001#7 remains OPEN -- and this failure is itself worth logging.")
        return 1

    u = result.usage
    print(f"  status        : {result.status}")
    print(f"  task_id       : {result.task_id}")
    print(f"  total tokens  : {u.total_tokens}  (in {u.input_tokens} / out {u.output_tokens})")
    print(f"  cache         : read {u.cache_read_tokens}, write {u.cache_write_tokens}, ratio {u.cache_ratio}")
    print(f"  tool calls    : {u.tool_calls}")
    print(f"  bob duration  : {u.duration_ms} ms")
    print(f"  wall clock    : {result.wall_ms:.0f} ms")
    print(f"  session cost  : {u.session_costs}")
    print()
    print("  last message:")
    print("  " + (result.last_message[:400] or "(empty)").replace("\n", "\n  "))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "docs" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"bob_roundtrip_{stamp}.json"
    artifact.write_text(
        json.dumps(
            {
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "thread": "0001#7",
                "mode": result.mode.value,
                "command": adapter.build_command(result.mode),
                "prompt": PROMPT,
                "status": result.status,
                "usage": u.__dict__,
                "wall_ms": result.wall_ms,
                "raw": result.raw,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print(f"  artifact: {artifact.relative_to(REPO_ROOT)}")
    if result.ok and u.total_tokens > 0:
        print("  THREAD 0001#7 CLOSED -- round trip succeeded and cost was captured.")
        print("  Paste the numbers above into a session entry and unblock S4.")
        return 0
    print("  Round trip completed but did not report usage. Thread stays OPEN;")
    print("  cost accounting (ERRATA A8) needs another source.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
