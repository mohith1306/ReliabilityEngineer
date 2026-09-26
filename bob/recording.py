"""Record what a LIVE Bob actually said, so it can be inspected and replayed later.

    BRE_BOB_RECORD_DIR=recordings     # opt-in; unset = nothing is recorded

Why: Bob is metered and credential-gated. When someone does have access -- the team on demo day -- the
most valuable thing that session can leave behind is Bob's real output: proof Bob was actually used (a
hackathon submission requirement), and a genuine recording to replay when Bob is not available, in place
of the hand-authored cassettes in bob/cassettes/.

What is recorded per turn: the kind (diagnosis | remediation), the full prompt and Bob's reply, the token
and cost figures Bob itself reported, wall time, and the provider. Never recorded: BOB_API_KEY (it is
not part of a prompt or a reply) or anything from the environment.

Safety: this module writes, so it is fenced. The record directory must NOT be inside the repository Bob
is working on -- a recording must never end up in a target repo's diff, or be mistaken for the fix -- and
it is never selected by default.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ENV_RECORD = "BRE_BOB_RECORD_DIR"


class RecordingRefused(ValueError):
    """The record directory is unsafe (inside the repository under repair)."""


def record_dir() -> Optional[Path]:
    raw = os.environ.get(ENV_RECORD, "").strip()
    return Path(raw).expanduser() if raw else None


def record_turn(
    kind: str,
    *,
    prompt: str,
    response: str,
    tokens: int,
    wall_ms: float,
    provider: str,
    workspace: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Optional[Path]:
    """Write one turn to BRE_BOB_RECORD_DIR. Returns the path, or None when recording is off."""
    directory = record_dir()
    if directory is None:
        return None
    directory = directory.resolve()
    if workspace:
        ws = Path(workspace).resolve()
        if directory == ws or ws in directory.parents:
            raise RecordingRefused(
                f"{ENV_RECORD} ({directory}) is inside the repository Bob is working on ({ws}); "
                "a recording must never land in a target repo's diff"
            )
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    payload = {
        "recorded_from_live_bob": provider not in ("replay-bob",),
        "kind": kind, "provider": provider, "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_sha256": digest, "prompt": prompt, "response": response,
        "tokens": tokens, "wall_ms": round(wall_ms, 1), "meta": meta or {},
    }
    path = directory / f"{stamp}-{kind}-{digest[:8]}.json"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:  # opt-in recording, not a target-repo write
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path
