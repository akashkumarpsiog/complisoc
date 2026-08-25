"""Regression coverage for explicit-null severity normalization."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.database.base import Base
from complisoc.backend.models import RawFinding, ScanRun, ScannerExecution
from complisoc.backend.normalization.normalizer import normalize_raw_finding


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()


def _raw_finding(db_session, payload):
    run = ScanRun(target_environment="severity-regression", status="running")
    db_session.add(run)
    db_session.flush()
    execution = ScannerExecution(scan_run_id=run.id, scanner_name="trivy", status="completed")
    db_session.add(execution)
    db_session.flush()
    raw = RawFinding(scanner_execution_id=execution.id, scanner_finding_id="severity-case", scanner_name="trivy", raw_json=payload)
    db_session.add(raw)
    db_session.commit()
    return raw


@pytest.mark.parametrize("payload", [
    {"finding_type": "AVD-1", "resource_identifier": "main.tf::aws_s3_bucket.public", "title": "Public bucket", "severity": None},
    {"finding_type": "AVD-1", "resource_identifier": "main.tf::aws_s3_bucket.public", "title": "Public bucket"},
])
def test_missing_or_explicit_null_severity_defaults_to_medium(db_session, payload):
    """Regression for BUG-003 (../../BUG_REGISTRY.md#bug-003--none-bypass-in-severity-field-defaulting)."""
    normalized = normalize_raw_finding(db_session, _raw_finding(db_session, payload))

    assert normalized.severity == "medium"
