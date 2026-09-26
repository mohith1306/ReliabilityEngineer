"""Runtime configuration, read from the environment. One place, so the UI can tell the truth about it.

    BRE_BOB_TRANSPORT   shell | host | replay | (unset = auto). `replay` is the labelled stand-in and is
                        NEVER selected automatically.
    BOB_API_KEY         Bob Shell credential (never echoed anywhere).
    BRE_REPO_ALLOWLIST  repositories BRE may write to (os.pathsep-separated). Empty = read-only.
    BRE_DEMO=1          enable /api/demo/*: BRE builds throwaway fixture repositories under BRE_DEMO_DIR
                        and allowlists exactly that directory. For the hackathon demo and local trials.
    BRE_MAX_ATTEMPTS    hard cap on loop passes per incident (default 3).
    BRE_OPERATOR_KEY / BRE_OPERATOR_NAME   the bootstrap approver (see apps/api/auth.py).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from bob.shell import BobShell
from bob.transport import ENV_TRANSPORT
from reliability.remediation.allowlist import RepoAllowlist
from reliability.verification.verifier import max_attempts

ENV_DEMO = "BRE_DEMO"
ENV_DEMO_DIR = "BRE_DEMO_DIR"


def demo_enabled() -> bool:
    return os.environ.get(ENV_DEMO, "").strip() in ("1", "true", "yes")


def demo_dir() -> Path:
    return Path(os.environ.get(ENV_DEMO_DIR) or Path(tempfile.gettempdir()) / "bre-demo")


def allowlist() -> RepoAllowlist:
    base = RepoAllowlist.from_env()
    if demo_enabled():
        return RepoAllowlist([*base.roots, demo_dir()])
    return base


def bob_mode() -> dict:
    """What a reader must know before believing anything on screen."""
    forced = os.environ.get(ENV_TRANSPORT, "").strip().lower()
    if forced == "replay":
        return {"mode": "replay", "simulated": True, "label": "SIMULATED BOB",
                "detail": "Bob is replaced by a labelled replay stand-in. Verification (git + pytest) is real."}
    pre = BobShell(os.getcwd()).preflight()
    if forced in ("", "shell") and pre.ready:
        return {"mode": "shell", "simulated": False, "label": "LIVE IBM BOB",
                "detail": f"Bob Shell ({pre.version or 'version unknown'})"}
    if forced == "host":
        return {"mode": "host", "simulated": False, "label": "IBM BOB (agent host, experimental)",
                "detail": "read-only transport; remediation needs Bob Shell"}
    return {"mode": "unavailable", "simulated": False, "label": "NO BOB",
            "detail": "Bob Shell is not installed or BOB_API_KEY is not set. Set BRE_BOB_TRANSPORT=replay for the "
                      "labelled stand-in."}


def snapshot() -> dict:
    from asmos_bridge.routing.router import resolve_tau

    tau, tau_source = resolve_tau()
    al = allowlist()
    return {
        "bob": bob_mode(),
        "write_access": {"allowlisted_repositories": [str(r) for r in al.roots], "read_only": not al.roots},
        "demo": demo_enabled(),
        "max_attempts": max_attempts(),
        "tau": {"value": tau, "source": tau_source},
        "operator_configured": bool(os.environ.get("BRE_OPERATOR_KEY")),
        # Only ever shown for a public demo instance that opted in explicitly. The key gates approvals; on a
        # real deployment it is a secret and this field stays absent.
        "demo_operator_key": (os.environ.get("BRE_OPERATOR_KEY")
                              if demo_enabled() and os.environ.get("BRE_DEMO_SHOW_KEY") == "1" else None),
        "version": "0.2.0",
    }
