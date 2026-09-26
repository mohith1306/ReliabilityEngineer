"""Operator identity: API-key registry (S5 decision, session 0006).

Approvals never carry a caller-supplied name. The bearer key IS the identity:
it resolves to an operators row, and that row's id/name are what gets written
(ERRATA A6 -- `approved_by` as free text is not an identity).

Environment bootstrap for the demo:
    BRE_OPERATOR_KEY=<raw key>  BRE_OPERATOR_NAME=<display name>
On first successful auth the operator is created (only the env key ever
resolves, because the lookup is by hash of the key presented).
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

from sqlalchemy.orm import Session

from apps.api.database import OperatorDB, generate_id

ENV_KEY = "BRE_OPERATOR_KEY"
ENV_NAME = "BRE_OPERATOR_NAME"


class AuthenticationError(Exception):
    pass


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _bootstrap_from_env(db: Session) -> None:
    raw = os.environ.get(ENV_KEY)
    if not raw:
        return
    digest = hash_key(raw)
    exists = db.query(OperatorDB).filter(OperatorDB.api_key_hash == digest).first()
    if exists:
        return
    db.add(OperatorDB(
        id=generate_id(),
        name=os.environ.get(ENV_NAME) or "operator",
        api_key_hash=digest,
    ))
    db.commit()


def authenticate(db: Session, authorization: Optional[str]) -> OperatorDB:
    _bootstrap_from_env(db)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("missing bearer API key")
    raw = authorization.split(None, 1)[1].strip()
    if not raw:
        raise AuthenticationError("empty bearer API key")
    row = (
        db.query(OperatorDB)
        .filter(OperatorDB.api_key_hash == hash_key(raw))
        .first()
    )
    if row is None or row.revoked_at is not None:
        raise AuthenticationError("unknown or revoked API key")
    return row
