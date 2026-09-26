"""A protocol-faithful fake of the IBM Bob agent host (AHP).

Implements exactly the wire contract recovered in session 0005: JSON-RPC 2.0
envelopes, the confirmed method set with their parameter shapes, dispatchAction
notifications carrying the confirmed chat action taxonomy, and turn completion
as a snapshot carrying responseParts + usage. Its purpose is to prove
bob.AgentHostClient and bob.BobAdapter end to end over real sockets while the
real host cannot start on macOS (no darwin server build published).

Every request and notification is recorded on .requests / .notifications for
assertions.
"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Optional

from bob.execution import AHP_PROTOCOL_VERSION, ROOT_CHANNEL, AgentHostAddress

DEFAULT_PROMPT_TOKENS = 1500
DEFAULT_COMPLETION_TOKENS = 420


class FakeBobHost:
    def __init__(
        self,
        assistant_text: str,
        *,
        prompt_tokens: int = DEFAULT_PROMPT_TOKENS,
        completion_tokens: int = DEFAULT_COMPLETION_TOKENS,
        token: str = "fake-connection-token",
        fail_subscribe: bool = False,
    ):
        self.assistant_text = assistant_text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.token = token
        self.fail_subscribe = fail_subscribe
        self.requests: list[dict] = []
        self.notifications: list[dict] = []
        self.sessions: list[str] = []
        self.chats: list[str] = []
        self.address: Optional[AgentHostAddress] = None
        self._server = None
        self._thread = None

    def __enter__(self) -> "FakeBobHost":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self) -> None:
        from websockets.sync.server import serve

        self._server = serve(self._handler, "127.0.0.1", 0)
        port = self._server.socket.getsockname()[1]
        self.address = AgentHostAddress(
            host="127.0.0.1",
            port=port,
            token=self.token,
            protocol_version=AHP_PROTOCOL_VERSION,
            quality="stable",
            pid=None,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            try:
                conns = self._server.connections
                conns = conns() if callable(conns) else conns
                for connection in list(conns):
                    connection.close()
            except Exception:
                pass
            self._server.shutdown()
            self._server = None

    @property
    def url(self) -> str:
        assert self.address is not None, "host not started"
        return self.address.url

    def methods(self) -> list[str]:
        return [m["method"] for m in self.requests]

    def _handler(self, conn) -> None:
        try:
            for raw in conn:
                msg = json.loads(raw)
                if "id" in msg and "method" in msg:
                    self.requests.append(msg)
                    try:
                        result = self._route_request(msg["method"], msg.get("params") or {})
                        reply = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
                    except KeyError as unknown:
                        reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {
                            "code": -32601, "message": f"unknown method: {unknown}",
                        }}
                    conn.send(json.dumps(reply))
                elif "method" in msg:
                    self.notifications.append(msg)
                    self._route_notification(msg["method"], msg.get("params") or {}, conn)
        except Exception:
            return

    def _route_request(self, method: str, params: dict) -> Any:
        if method == "initialize":
            return {"serverSeq": 1, "snapshots": [], "defaultDirectory": "/tmp"}
        if method == "ping":
            return {"ok": True}
        if method == "listSessions":
            return {"items": [
                {"resource": s, "title": f"session {s}", "status": "idle",
                 "createdAt": "2026-09-26T00:00:00Z",
                 "modifiedAt": "2026-09-26T00:00:00Z"}
                for s in self.sessions
            ]}
        if method == "createSession":
            self.sessions.append(params.get("channel", ""))
            return {}
        if method == "createChat":
            self.chats.append(params.get("chat", ""))
            return {}
        if method == "subscribe":
            if self.fail_subscribe:
                raise KeyError("subscribe disabled")
            return {"snapshot": {"channel": params.get("channel"), "state": {}}}
        if method == "unsubscribe":
            return {}
        if method == "shutdown":
            return {}
        raise KeyError(method)

    def _route_notification(self, method: str, params: dict, conn) -> None:
        if method != "dispatchAction":
            return
        action = params.get("action") or {}
        if action.get("type") != "chat/turnStarted":
            return
        channel = params.get("channel", "")
        turn_id = action.get("turnId") or str(uuid.uuid4())
        conn.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "dispatchAction",
            "params": {"channel": channel, "action": {
                "type": "chat/turnStarted", "turnId": turn_id,
            }},
        }))
        conn.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "updateSnapshot",
            "params": {
                "channel": channel,
                "snapshot": {"activeTurn": {
                    "id": turn_id,
                    "status": "completed",
                    "responseParts": [
                        {"kind": "markdown", "text": self.assistant_text},
                    ],
                    "usage": {
                        "promptTokens": self.prompt_tokens,
                        "completionTokens": self.completion_tokens,
                    },
                }},
            },
        }))
