"""Tests for the evidence lineage endpoint and service.

Verifies that the existing evidence chain is exposed read-only and that
missing downstream records are handled gracefully.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.compliance.lineage import get_finding_lineage
from complisoc.backend.database.base import Base
from complisoc.backend.models import (
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ScanRun,
    ScannerExecution,
    VerificationRecord,
)


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return engine


def _session(engine):
    Local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return Local()


def _seed(db):
    scan = ScanRun(target_environment="test", status="completed")
    db.add(scan)
    db.commit()
    db.refresh(scan)

    se = ScannerExecution(scan_run_id=scan.id, scanner_name="checkov", status="completed")
    db.add(se)
    db.commit()
    db.refresh(se)

    raw = RawFinding(
        scanner_execution_id=se.id,
        scanner_finding_id="CKV-1",
        scanner_name="checkov",
        raw_json={"finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.x", "severity": "high", "title": "Test"},
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)

    nf = NormalizedFinding(
        raw_finding_id=raw.id,
        scanner_name="checkov",
        finding_type="iam",
        resource_type="aws_iam_policy",
        resource_identifier="aws_iam_policy.x",
        severity="high",
        title="Test finding",
        description="Test description",
    )
    db.add(nf)
    db.commit()
    db.refresh(nf)

    control = ControlCatalog(
        framework_name="ISO/IEC 27001:2022 Annex A",
        framework_version="2022",
        control_id="A.5.15",
        control_family="Access Control",
        title="Access Control",
        description="Limit access.",
        objective="Prevent unauthorized access.",
        evidence_examples=["access_review_report"],
        scanner_signals=["iam"],
        keywords=["iam"],
        source_url="https://example.test/iso-a-5-15",
        active_status=True,
    )
    db.add(control)
    db.commit()
    db.refresh(control)

    mapping = ControlMapping(
        normalized_finding_id=nf.id,
        candidate_control_id=control.id,
        control_catalog_id=control.id,
        mapping_model="gemini-batch",
        prompt_version="v1",
        rationale="test",
        gemini_confidence=0.9,
        final_confidence=0.92,
        verification_status="agree",
        groq_agreement_value=0.9,
        mapping_status="published",
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    vr = VerificationRecord(
        control_mapping_id=mapping.id,
        verification_model="groq",
        prompt_version="v1",
        result="agree",
        explanation="Correct mapping",
        agreement_value=0.9,
    )
    db.add(vr)
    db.commit()
    db.refresh(vr)

    return {"scan": scan, "se": se, "raw": raw, "nf": nf, "control": control, "mapping": mapping, "vr": vr}


class TestLineageReturnsFullChain:
    def test_lineage_returns_scan_run(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            lineage = get_finding_lineage(db, data["nf"].id)
            assert lineage["scan_run"] is not None
            assert lineage["scan_run"]["id"] == data["scan"].id
            assert lineage["scan_run"]["target_environment"] == "test"
        finally:
            db.close()
            engine.dispose()

    def test_lineage_returns_raw_finding(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            lineage = get_finding_lineage(db, data["nf"].id)
            assert lineage["raw_finding"] is not None
            assert lineage["raw_finding"]["id"] == data["raw"].id
            assert lineage["raw_finding"]["scanner_name"] == "checkov"
        finally:
            db.close()
            engine.dispose()

    def test_lineage_returns_normalized_finding(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            lineage = get_finding_lineage(db, data["nf"].id)
            assert lineage["normalized_finding"]["id"] == data["nf"].id
            assert lineage["normalized_finding"]["severity"] == "high"
        finally:
            db.close()
            engine.dispose()

    def test_lineage_returns_mapping(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            lineage = get_finding_lineage(db, data["nf"].id)
            assert len(lineage["mappings"]) == 1
            assert lineage["mappings"][0]["mapping_id"] == data["mapping"].id
            assert lineage["mappings"][0]["control_id"] == "A.5.15"
        finally:
            db.close()
            engine.dispose()

    def test_lineage_returns_verification(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            lineage = get_finding_lineage(db, data["nf"].id)
            assert len(lineage["mappings"][0]["verification_records"]) == 1
            assert lineage["mappings"][0]["verification_records"][0]["result"] == "agree"
        finally:
            db.close()
            engine.dispose()


class TestLineageMissingData:
    def test_missing_mapping(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            db.delete(data["mapping"])
            db.commit()
            lineage = get_finding_lineage(db, data["nf"].id)
            assert lineage["mappings"] == []
            assert lineage["scan_run"] is not None
            assert lineage["raw_finding"] is not None
        finally:
            db.close()
            engine.dispose()

    def test_missing_verification(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            db.delete(data["vr"])
            db.commit()
            lineage = get_finding_lineage(db, data["nf"].id)
            assert lineage["mappings"][0]["verification_records"] == []
        finally:
            db.close()
            engine.dispose()


class TestLineageDoesNotModifyData:
    def test_lineage_is_read_only(self):
        engine = _engine()
        db = _session(engine)
        try:
            data = _seed(db)
            original_title = data["nf"].title
            get_finding_lineage(db, data["nf"].id)
            db.refresh(data["nf"])
            assert data["nf"].title == original_title
        finally:
            db.close()
            engine.dispose()
