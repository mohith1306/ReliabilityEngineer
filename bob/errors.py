"""Exception hierarchy shared by every way of reaching IBM Bob.

One root (`BobError`) so callers can `except BobError` without caring whether the
turn went over the documented Bob Shell CLI or the agent-host WebSocket.
"""

from __future__ import annotations


class BobError(Exception):
    """Base class for every Bob failure, whatever the transport."""


class BobNotInstalled(BobError):
    raise_note = "no bobide binary found; set BOB_CLI_PATH"


class BobNotAvailable(BobError):
    """Bob Shell is not installed, or is not authenticated (no BOB_API_KEY)."""


class BobHostUnavailable(BobError):
    """No usable agent host: none running, stale lockfile, or undownloadable server."""


class BobProtocolError(BobError):
    """A JSON-RPC error returned by the host."""


class BobTurnTimeout(BobError):
    """A chat turn did not complete within the deadline."""


class BobWriteRefused(BobError):
    """A write-path (agent-mode) call was attempted without explicit authorisation."""
