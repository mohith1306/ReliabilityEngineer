import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dbpool import ConnectionPool, ExhaustionError, load_pool_size

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "app.yaml"


def test_pool_sized_from_config():
    """Production needs >= 10 concurrent connections; the pool is sized from config."""
    pool = ConnectionPool(size=load_pool_size(CONFIG))
    acquired = []
    for _ in range(10):
        try:
            acquired.append(pool.acquire())
        except ExhaustionError:
            break
    assert len(acquired) >= 10, (
        f"connection pool exhausted after {len(acquired)} acquisitions"
    )


def test_release_returns_slot():
    pool = ConnectionPool(size=1)
    conn = pool.acquire()
    pool.release(conn)
    assert pool.acquire() is not None
