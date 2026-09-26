import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from authservice import AuthService, RequestTimeoutError, load_timeout
import pytest

CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "auth.yaml"


def test_login_within_timeout():
    """The configured timeout must still admit a 0.05s backend round trip."""
    service = AuthService(timeout_seconds=load_timeout(CONFIG))
    session = service.login("alice", "s3cret", backend_latency=0.05)
    assert session["user"] == "alice"


def test_verify_rejects_empty_token():
    assert AuthService().verify_token("") is False
