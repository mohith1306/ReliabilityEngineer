"""Authentication service for the dataforge platform.

Regression under investigation: login requests time out against the backend.
"""

DEFAULT_TIMEOUT_SECONDS = 5.0


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
