"""Connection pool for the dataforge database layer.

Regression under investigation: CI reports connection pool exhaustion
in the pool-sized-from-config path.
"""

DEFAULT_POOL_SIZE = 20


class ExhaustionError(RuntimeError):
    """Raised when every pool slot is taken."""


class ConnectionPool:
    """Fixed-size pool of database connections."""

    def __init__(self, size: int = DEFAULT_POOL_SIZE):
        if size < 1:
            raise ValueError("pool size must be positive")
        self.size = size
        self._in_use = 0

    def acquire(self):
        if self._in_use >= self.size:
            raise ExhaustionError(
                f"connection pool exhausted: {self._in_use}/{self.size} in use"
            )
        self._in_use += 1
        return object()

    def release(self, conn) -> None:
        if self._in_use > 0:
            self._in_use -= 1
