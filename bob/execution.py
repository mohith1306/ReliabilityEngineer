"""Transport for the IBM Bob agent-host protocol (AHP).

Confirmed mechanism (session 0005, closes thread 0001#7):

    bobide agent host      -> local WS server, lockfile with port + token
    ws://<host>:<port>?tkn=<token>
    JSON-RPC 2.0 envelopes: {jsonrpc, id, method, params} ->
                            {jsonrpc, id, result|error}
    host -> client notifications: {jsonrpc, method, params} with no id
    root channel: ahp-root://    chat channel: ahp-chat://default/<session-ref>
    protocolVersion 0.1.0 (from the lockfile)

Recovered from the shipped binaries and app bundle:

    bin/bobide --help               CLI surface incl. `agent host` subcommands
    bin/bobide-tunnel agent host    supervisor + lockfile writer
    ~/.bobide-server/cli/agent-host-stable.lock
        {"schemaVersion":1,"pid":..,"port":..,"host":"..",
         "connectionToken":"..","protocolVersion":"0.1.0","quality":"stable"}
    out/vs/workbench/workbench.desktop.main.js
        _dispatchRequest -> {jsonrpc:"2.0", id, method, params}
        methods: initialize / ping / listSessions / createSession /
                 createChat / subscribe / unsubscribe / dispatchAction /
                 disposeSession / disposeChat / shutdown
        initialize params {channel: "ahp-root://", protocolVersions, clientId,
                           initialSubscriptions}
        createSession params {channel: "<provider>:/<uuid>", provider, model?,
                              workingDirectory?, config?}
        dispatchAction (notification) {channel, clientSeq, action}
        chat turn action {type:"chat/turnStarted", turnId,
                          message:{text, origin:{kind:"user"}}}
        incoming routing keys on method: "dispatchAction", "ping"

Platform note: the supervisor downloads a server build before listening.
IBM publishes linux/x64 and win32/x64 REH archives; every darwin/* path
returns 404 (evidence in session 0005), so on macOS the host never becomes
ready. discovery still works -- the lockfile and CLI are real here -- and
every connection failure surfaces as BobHostUnavailable with that fact.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .errors import (  # noqa: F401  (re-exported: callers import these from here)
    BobError,
    BobHostUnavailable,
    BobNotInstalled,
    BobProtocolError,
    BobTurnTimeout,
)

AHP_PROTOCOL_VERSION = "0.1.0"
ROOT_CHANNEL = "ahp-root://"
DEFAULT_REQUEST_TIMEOUT = 15.0
DEFAULT_TURN_TIMEOUT = 120.0

ENV_CLI = "BOB_CLI_PATH"
ENV_HOST = "BOB_AGENT_HOST"

_APP_BIN = Path("/Applications/IBM Bob.app/Contents/Resources/app/bin")
_CLI_CANDIDATES = (
    _APP_BIN / "bobide",
    _APP_BIN / "bobide-tunnel",
)


@dataclass(frozen=True)
class AgentHostAddress:
    host: str
    port: int
    token: str
    protocol_version: str = AHP_PROTOCOL_VERSION
    quality: str = "stable"
    pid: Optional[int] = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}?tkn={self.token}"

    def pid_alive(self) -> bool:
        return _pid_alive(self.pid)


def _pid_alive(pid: Optional[int]) -> bool:
    """Is `pid` a running process? Never signals it.

    `os.kill(pid, 0)` is the POSIX idiom, but on Windows any signal other than
    CTRL_C_EVENT/CTRL_BREAK_EVENT is delivered as TerminateProcess -- so the
    "liveness probe" would kill the very Bob host it was checking. Windows takes
    the OpenProcess/GetExitCodeProcess route instead.
    """
    if pid is None:
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        ERROR_ACCESS_DENIED = 5
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE  # 64-bit handles: default int truncates
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            # Access denied still means the process exists; only "no such pid" is dead.
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def find_cli() -> Optional[Path]:
    env = os.environ.get(ENV_CLI)
    if env and Path(env).exists():
        return Path(env)
    for candidate in _CLI_CANDIDATES:
        if candidate.exists():
            return candidate
    for name in ("bobide", "bobide-tunnel"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def probe_cli() -> dict:
    """A real call to the real Bob CLI. Returns version banner details."""
    cli = find_cli()
    if cli is None:
        raise BobNotInstalled(BobNotInstalled.raise_note)
    proc = subprocess.run(
        [str(cli), "chat", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise BobProtocolError(
            f"bobide chat --help failed rc={proc.returncode}: {proc.stderr[:400]}"
        )
    banner = (proc.stdout or proc.stderr).strip().splitlines()[0]
    version = banner.split()[-1] if banner.split() else "unknown"
    return {"cli": str(cli), "banner": banner, "version": version}


def _lockfile_candidates() -> list[Path]:
    bases = []
    cli_data = os.environ.get("VSCODE_CLI_DATA_DIR")
    if cli_data:
        bases.append(Path(cli_data))
    bases.append(Path.home() / ".bobide-server" / "cli")
    bases.append(Path.home() / ".bobide" / "cli")
    out: list[Path] = []
    for base in bases:
        if base.is_dir():
            out.extend(sorted(base.glob("*.lock")))
    return out


def discover_agent_host(explicit: Optional[str] = None) -> AgentHostAddress:
    """explicit URL -> BOB_AGENT_HOST -> live lockfile -> BobHostUnavailable."""
    raw = explicit or os.environ.get(ENV_HOST)
    if raw:
        return _from_url(raw, pid=None)

    for path in _lockfile_candidates():
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        address = AgentHostAddress(
            host=data.get("host", "127.0.0.1"),
            port=int(data.get("port", 0)),
            token=data.get("connectionToken", ""),
            protocol_version=data.get("protocolVersion", AHP_PROTOCOL_VERSION),
            quality=data.get("quality", "stable"),
            pid=data.get("pid"),
        )
        if address.port and address.token and address.pid_alive():
            return address

    raise BobHostUnavailable(
        "no live agent host found (checked BOB_AGENT_HOST and "
        f"{len(_lockfile_candidates())} lockfiles). Start one with "
        "`bobide agent host`. On macOS the supervisor currently fails to "
        "download a darwin server build (IBM publishes linux/x64 and "
        "win32/x64 only) -- see docs/memory/sessions/0005."
    )


def _from_url(raw: str, pid: Optional[int]) -> AgentHostAddress:
    parsed = urlparse(raw)
    if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
        raise BobHostUnavailable(f"malformed agent host URL: {raw!r}")
    token = ""
    for part in (parsed.query or "").split("&"):
        if part.startswith("tkn="):
            token = part[4:]
    if not token:
        raise BobHostUnavailable(f"agent host URL has no tkn= token: {raw!r}")
    return AgentHostAddress(
        host=parsed.hostname,
        port=parsed.port or 80,
        token=token,
        pid=pid,
    )


class AgentHostClient:
    """JSON-RPC 2.0 client for the agent host. Requests are answered
    in order; notifications that arrive while waiting are stashed and can
    be replayed by wait_for_notification."""

    def __init__(
        self,
        address: AgentHostAddress,
        *,
        client_id: Optional[str] = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.address = address
        self.client_id = client_id or f"bre-{uuid.uuid4()}"
        self.timeout = timeout
        self.notifications: list[dict] = []
        self._conn = None
        self._next_id = 0

    def __enter__(self) -> "AgentHostClient":
        from websockets.sync.client import connect

        try:
            self._conn = connect(
                self.address.url,
                open_timeout=self.timeout,
                close_timeout=2,
                legacy=True,
            )
        except Exception as exc:
            raise BobHostUnavailable(
                f"cannot connect to agent host at {self.address.host}:"
                f"{self.address.port}: {exc}"
            ) from exc
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def _send(self, payload: dict) -> None:
        if self._conn is None:
            raise BobHostUnavailable("client is not connected")
        self._conn.send(json.dumps(payload))

    def request(self, method: str, params: dict, timeout: Optional[float] = None) -> Any:
        self._next_id += 1
        req_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        deadline = (timeout or self.timeout)
        end = time.monotonic() + deadline
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise BobProtocolError(f"timed out waiting for {method} response")
            try:
                raw = self._conn.recv(timeout=remaining)
            except TimeoutError:
                raise BobProtocolError(
                    f"timed out waiting for {method} response"
                ) from None
            except Exception as exc:
                raise BobProtocolError(f"connection lost during {method}: {exc}") from exc
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if msg.get("id") == req_id:
                if "error" in msg:
                    err = msg["error"]
                    raise BobProtocolError(
                        f"{method} failed: code={err.get('code')} "
                        f"message={err.get('message')}"
                    )
                return msg.get("result")
            if "method" in msg and "id" not in msg:
                self.notifications.append(msg)

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def wait_for_notification(
        self,
        predicate: Callable[[dict], bool],
        *,
        timeout: float,
        label: str = "event",
    ) -> dict:
        end = time.monotonic() + timeout
        for cached in self.notifications:
            if predicate(cached):
                self.notifications.remove(cached)
                return cached
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise BobTurnTimeout(f"timed out after {timeout:.0f}s waiting for {label}")
            try:
                raw = self._conn.recv(timeout=remaining)
            except TimeoutError:
                continue
            except Exception as exc:
                raise BobProtocolError(f"connection lost waiting for {label}: {exc}") from exc
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if "method" in msg and "id" not in msg:
                if predicate(msg):
                    return msg
                self.notifications.append(msg)

    def initialize(self) -> dict:
        return self.request("initialize", {
            "channel": ROOT_CHANNEL,
            "protocolVersions": [AHP_PROTOCOL_VERSION],
            "clientId": self.client_id,
            "initialSubscriptions": [ROOT_CHANNEL],
        })

    def ping(self) -> Any:
        return self.request("ping", {})

    def list_sessions(self) -> list[dict]:
        result = self.request("listSessions", {"channel": ROOT_CHANNEL})
        return (result or {}).get("items", [])

    def create_session(
        self,
        channel: str,
        provider: str,
        *,
        working_directory: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        params: dict = {"channel": channel, "provider": provider}
        if working_directory is not None:
            params["workingDirectory"] = working_directory
        if model is not None:
            params["model"] = model
        return self.request("createSession", params) or {}

    def create_chat(self, channel: str, chat: str, model: Optional[str] = None) -> dict:
        params: dict = {"channel": channel, "chat": chat}
        if model is not None:
            params["model"] = model
        return self.request("createChat", params) or {}

    def subscribe(self, channel: str) -> dict:
        result = self.request("subscribe", {"channel": channel})
        return (result or {}).get("snapshot", {})

    def unsubscribe(self, channel: str) -> None:
        self.notify("unsubscribe", {"channel": channel})

    def dispatch_action(self, channel: str, action: dict, client_seq: int) -> None:
        self.notify("dispatchAction", {
            "channel": channel,
            "clientSeq": client_seq,
            "action": action,
        })

    def dispose_session(self, channel: str) -> dict:
        return self.request("disposeSession", {"channel": channel}) or {}

    def shutdown(self) -> None:
        try:
            self.request("shutdown", {}, timeout=3.0)
        except BobError:
            pass


def chat_channel_for(session_uri: str) -> str:
    """ahp-chat://default/<ref> -- the default chat channel for a session.

    The real client builds <ref> from the session URI (base64url in the app
    bundle); both ends of a BRE call use this one function, and the live
    encoding gets confirmed against a running host (thread 0005#1).
    """
    import base64

    ref = base64.urlsafe_b64encode(session_uri.encode()).decode().rstrip("=")
    return f"ahp-chat://default/{ref}"
