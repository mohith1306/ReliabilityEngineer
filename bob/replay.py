"""Replay Bob -- a labelled stand-in so the pipeline runs where no live Bob exists.

Why this exists: Bob is a metered, credential-gated service. CI, a contributor without a
key, and a deployed demo all need the *rest* of BRE (evidence, ledger, gate, remediation
branch, verification, routing) to run end to end. A cassette holds one scripted Bob
response per failure scenario.

What it is NOT: Bob, an agent, or evidence about Bob's quality. Non-negotiable 1 (CLAUDE.md)
says BRE never reimplements a coding agent, and this does not: it replays a fixed answer
for a fixed failure signature and refuses anything else.

Honesty rules, enforced in code rather than in a README:
  * Never auto-selected. It runs only when BRE_BOB_TRANSPORT=replay is set explicitly.
  * Every turn it produces carries `extra["simulated"] = True`, which the adapter writes
    into the outcome record's `components`, so a ledger row can always be told apart from
    a real Bob call, and metrics can be reported separately.
  * A cassette matches on the *failure signature in the repository* (a file line matching an
    anchored pattern), not on a name -- a repo that does not exhibit a recorded failure,
    including one that has already been fixed, gets an honest "no recorded response".
  * Token figures in a cassette are nominal placeholders (`usage_is_simulated`). They keep
    the cost plumbing exercised; they are not measurements and must never be reported as
    such.

When live Bob is available, its real responses can be captured into this same format.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .errors import BobNotAvailable
from .transport import TurnOutcome

CASSETTE_DIR = Path(__file__).with_name("cassettes")
ENV_VALUE = "replay"


@dataclass(frozen=True)
class Cassette:
    scenario: str
    provenance: str
    match_file: str
    match_pattern: str
    diagnosis: dict
    remediation: dict
    cites: tuple[str, ...] = ()
    usage_is_simulated: bool = True
    path: Optional[Path] = field(default=None, compare=False)


def load_cassettes(directory: Path = CASSETTE_DIR) -> list[Cassette]:
    cassettes: list[Cassette] = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        cassettes.append(Cassette(
            scenario=raw["scenario"],
            provenance=raw["provenance"],
            match_file=raw["match"]["file"],
            match_pattern=raw["match"]["pattern"],
            diagnosis=raw["diagnosis"],
            remediation=raw["remediation"],
            cites=tuple(raw.get("cites", ())),
            usage_is_simulated=bool(raw.get("usage_is_simulated", True)),
            path=path,
        ))
    return cassettes


def match_cassette(repo_root: str | Path, cassettes: Optional[list[Cassette]] = None) -> Optional[Cassette]:
    """The cassette whose failure signature the repository currently exhibits, if any."""
    for cassette in cassettes if cassettes is not None else load_cassettes():
        target = Path(repo_root) / cassette.match_file
        try:
            if target.is_file() and re.search(
                cassette.match_pattern, target.read_text(encoding="utf-8"), re.MULTILINE
            ):
                return cassette
        except OSError:
            continue
    return None


def find_by_root_cause(root_cause: str, cassettes: Optional[list[Cassette]] = None) -> Optional[Cassette]:
    """The cassette whose scripted diagnosis IS this root cause.

    A remediating agent acts on the diagnosis it is given, not on some other knowledge of the repo.
    Replay honours that: it looks the diagnosis up, so a wrong diagnosis (a memory that does not fit
    this incident) leads to a wrong fix, and the test suite -- not the stand-in -- decides.
    """
    for cassette in cassettes if cassettes is not None else load_cassettes():
        if cassette.diagnosis.get("root_cause") == root_cause:
            return cassette
    return None


_EVIDENCE_LINE = re.compile(r"^- \[[^\]]+\]\s+(\S+)", re.M)


class ReplayTransport:
    """Read-only transport: answers a diagnosis prompt from a matching cassette."""

    name = "replay"

    def __init__(self, cassettes: Optional[list[Cassette]] = None) -> None:
        self._cassettes = cassettes

    def run(self, prompt: str, *, working_directory: Optional[str] = None) -> TurnOutcome:
        if not working_directory:
            raise BobNotAvailable("replay Bob needs a working_directory to match a failure signature")
        cassette = match_cassette(working_directory, self._cassettes)
        if cassette is None:
            raise BobNotAvailable(
                f"no recorded Bob response matches the failure in {working_directory}. Replay only "
                "answers scenarios it has a cassette for; use live Bob for anything else."
            )
        cited = [
            ref for ref in _EVIDENCE_LINE.findall(prompt)
            if any(c in ref for c in cassette.cites)
        ]
        body = dict(cassette.diagnosis)
        tokens = int(body.pop("usage_tokens", 0))
        body["evidence_ids"] = cited
        return TurnOutcome(
            text=json.dumps(body),
            tokens=tokens,
            wall_ms=0.0,
            provider="replay-bob",
            turn_id=f"replay:{cassette.scenario}",
            extra={"simulated": True, "scenario": cassette.scenario,
                   "usage_is_simulated": cassette.usage_is_simulated},
        )
