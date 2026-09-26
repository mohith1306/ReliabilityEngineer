import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Integer, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = "sqlite:///./bre.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_id() -> str:
    return uuid.uuid4().hex[:12]


class IncidentDB(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    repository = Column(String, nullable=False)
    branch = Column(String, default="main")
    type = Column(String, nullable=False)
    severity = Column(String, default="unknown")
    status = Column(String, default="DETECTED")
    attempt = Column(Integer, default=1)  # loop pass; capped by reliability.orchestration
    description = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class IncidentEventDB(Base):
    """Append-only audit log: every state change and every notable engine action.

    Integer primary key on purpose: ordering must not depend on clock resolution.
    Written only through reliability.orchestration.lifecycle.Lifecycle.
    """

    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)           # transition | diagnosis | risk | approval | remediation | ...
    actor = Column(String, nullable=False, default="system")
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class InvestigationDB(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    summary = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvidenceDB(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True)
    investigation_id = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source_reference = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    relevance_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DiagnosisDB(Base):
    __tablename__ = "diagnoses"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    root_cause = Column(Text, nullable=False)
    confidence = Column(Float, default=0.0)
    affected_components = Column(JSON, default=list)
    evidence_ids = Column(JSON, default=list)
    assumptions = Column(JSON, default=list)
    unresolved_uncertainty = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskAssessmentDB(Base):
    __tablename__ = "risk_assessments"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    confidence = Column(Float, default=0.0)
    factors = Column(JSON, default=dict)
    blast_radius = Column(Integer, default=0)
    affected_components = Column(JSON, default=list)
    api_surface_affected = Column(Boolean, default=False)
    database_migration = Column(Boolean, default=False)
    tests_available = Column(String, default="none")
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalDB(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    operator_id = Column(String, nullable=True)
    operator_name = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OperatorDB(Base):
    __tablename__ = "operators"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    api_key_hash = Column(String, nullable=False, unique=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RemediationDB(Base):
    __tablename__ = "remediations"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    summary = Column(Text, default="")
    patch_reference = Column(String, nullable=True)  # the bre/* branch holding the patch
    changed_files = Column(JSON, default=list)       # from `git diff`, never from Bob's claim
    tests_added = Column(JSON, default=list)
    # --- S6: write-path provenance (see reliability/remediation) ---
    repo_root = Column(String, nullable=True)
    base_branch = Column(String, nullable=True)
    checkpoint_sha = Column(String, nullable=True)   # HEAD before any patch; the rollback anchor
    commit_sha = Column(String, nullable=True)       # the patch commit on the bre/* branch
    executor = Column(String, nullable=True)         # bob-shell | replay-bob | ...
    attempt = Column(Integer, default=1)
    baseline_failures = Column(JSON, default=list)   # tests already red at the checkpoint
    preexisting_untracked = Column(JSON, default=list)  # untracked files that were there BEFORE the patch;
                                                        # rollback must never delete these
    cost_tokens = Column(Integer, default=0)
    cost_wall_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)


class VerificationDB(Base):
    __tablename__ = "verification_runs"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    remediation_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    tests_run = Column(Integer, default=0)
    tests_passed = Column(Integer, default=0)
    tests_failed = Column(Integer, default=0)
    regressions = Column(JSON, default=list)
    test_results = Column(JSON, default=list)
    levels = Column(JSON, default=dict)  # {"targeted": {...}, "component": {...}, "regression": {...}}
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class EngineeringMemoryDB(Base):
    __tablename__ = "engineering_memory"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_incident_id = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    embedding_reference = Column(String, nullable=True)
    # --- S8: verified-memory fields (asmos_bridge/memory/store.py) ---
    topic = Column(String, nullable=True, index=True)
    keywords = Column(JSON, default=list)              # analysed incident keywords; the similarity basis
    status = Column(String, default="active")          # active | superseded (corrections supersede, never overwrite)
    superseded_by = Column(String, nullable=True)
    verification_run_id = Column(String, nullable=True)  # a memory record must be backed by a real passed run
    claim_class = Column(String, default="B")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class OutcomeRecordDB(Base):
    """Prediction in, verified outcome out. ADR-0003.

    Opened at prediction time with status='pending'. Only reliability.verification
    (or the evaluation harness, via an `eval:`-prefixed run id) may close it.
    tenant_id and cost_* exist from the first write -- neither can be backfilled
    (ERRATA A7, A8).
    """

    __tablename__ = "outcome_records"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    incident_id = Column(String, nullable=False, index=True)
    predictor_id = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    prediction_type = Column(String, nullable=False)
    prediction_payload = Column(JSON, default=dict)
    claim_class = Column(String, nullable=False, default="B")
    predicted_at = Column(DateTime, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    components = Column(JSON, default=dict)
    attempt_number = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="pending", index=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(String, nullable=True)
    verification_run_id = Column(String, nullable=True)
    cost_tokens = Column(Integer, nullable=False, default=0)
    cost_wall_ms = Column(Float, nullable=False, default=0.0)


# (table, legacy column) -> the current column its value should be carried into. Anything not listed
# here is dropped with the rebuilt table.
LEGACY_COLUMN_MAP = {("approvals", "approved_by"): "operator_name"}


def rebuild_legacy_tables(bind=None) -> list[str]:
    """Rebuild tables that still carry an obsolete NOT NULL column the current model no longer writes.

    SQLite cannot drop a NOT NULL constraint in place, and `create_all` never alters an existing table,
    so a `bre.db` from before a rename (S5: approvals.approved_by -> operator_id/operator_name) makes every
    INSERT fail with "NOT NULL constraint failed". The one safe fix is rename -> create -> copy -> drop.

    Data carried across is deliberately conservative: a legacy free-text `approved_by` becomes
    `operator_name` but `operator_id` stays NULL, so an approval that was never authenticated can never
    satisfy the gate after the migration (ERRATA A6). Returns the tables it rebuilt.
    """
    from sqlalchemy import inspect, text

    bind = bind or engine
    inspector = inspect(bind)
    rebuilt: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        model_cols = {c.name for c in table.columns}
        info = inspector.get_columns(table.name)
        obsolete_required = [c for c in info if c["name"] not in model_cols and not c["nullable"] and c.get("default") is None]
        if not obsolete_required:
            continue
        legacy = f"{table.name}__legacy"
        old_cols = {c["name"] for c in info}
        copy: list[tuple[str, str]] = [(c, c) for c in old_cols & model_cols]
        for (t, old_name), new_name in LEGACY_COLUMN_MAP.items():
            if t == table.name and old_name in old_cols and new_name not in {n for _, n in copy}:
                copy.append((old_name, new_name))
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table.name} RENAME TO {legacy}"))
            table.create(bind=conn)
            if copy:
                dst = ", ".join(n for _, n in copy)
                src = ", ".join(o for o, _ in copy)
                conn.execute(text(f"INSERT INTO {table.name} ({dst}) SELECT {src} FROM {legacy}"))
            conn.execute(text(f"DROP TABLE {legacy}"))
        rebuilt.append(table.name)
    return rebuilt


def ensure_columns(bind=None) -> list[str]:
    """Add columns that exist on the models but not in an already-created database.

    `create_all` never alters an existing table, so a teammate's old `bre.db` silently
    lacks every column added since (this bit S5's approvals rename). A defaulted or
    nullable ADD COLUMN is the one migration SQLite does safely, and it is all we need.
    Returns the columns it added, for logging.
    """
    from sqlalchemy import inspect, text

    bind = bind or engine
    inspector = inspect(bind)
    added: list[str] = []
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                ddl = column.type.compile(dialect=bind.dialect)
                default = ""
                if column.default is not None and getattr(column.default, "is_scalar", False):
                    value = column.default.arg
                    default = f" DEFAULT {value!r}" if isinstance(value, (int, float)) else f" DEFAULT '{value}'"
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl}{default}"))
                added.append(f"{table.name}.{column.name}")
    return added


def init_db():
    Base.metadata.create_all(bind=engine)
    rebuild_legacy_tables(engine)
    ensure_columns(engine)
