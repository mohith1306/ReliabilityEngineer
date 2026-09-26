"""Connection pool for the dataforge database layer (capped variant).

Regression under investigation: CI reports connection pool exhaustion even though
config/app.yaml asks for a healthy pool size.
"""

import re
from pathlib import Path

DEFAULT_POOL_SIZE = 20


def load_pool_size(config_path) -> int:
    """Read `pool_size` from a YAML config without a YAML dependency."""
    for line in Path(config_path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*pool_size:\s*(\d+)", line)
        if match:
            return int(match.group(1))
    return DEFAULT_POOL_SIZE


class ExhaustionError(RuntimeError):
    """Raised when every pool slot is taken."""


class ConnectionPool:
    """Fixed-size pool of database connections."""

    def __init__(self, size: int = DEFAULT_POOL_SIZE):
        if size < 1:
            raise ValueError("pool size must be positive")
        self.size = min(size, 2)  # cap: protect the shared database during load-shedding
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
