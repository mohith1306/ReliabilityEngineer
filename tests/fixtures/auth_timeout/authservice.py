"""Authentication service for the dataforge platform.

Regression under investigation: login requests time out against the backend.
"""

import re
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 5.0


def load_timeout(config_path) -> float:
    """Read `request_timeout_seconds` from a YAML config without a YAML dependency."""
    for line in Path(config_path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*request_timeout_seconds:\s*([0-9.]+)", line)
        if match:
            return float(match.group(1))
    return DEFAULT_TIMEOUT_SECONDS


class RequestTimeoutError(RuntimeError):
    """Raised when the auth backend exceeds the configured timeout."""


class AuthService:
    """Issues sessions for valid credentials within the request timeout."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        if timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        self.timeout_seconds = timeout_seconds

    def login(self, username: str, password: str, backend_latency: float = 0.05) -> dict:
        """Authenticate a user; fail when the backend round trip exceeds timeout."""
        if not username or not password:
            raise ValueError("username and password are required")
        if backend_latency > self.timeout_seconds:
            raise RequestTimeoutError(
                f"login request timed out after {self.timeout_seconds}s "
                f"(backend latency {backend_latency}s) for user {username}"
            )
        return {"user": username, "timeout_seconds": self.timeout_seconds}

    def verify_token(self, token: str) -> bool:
        return bool(token) and len(token) >= 8
