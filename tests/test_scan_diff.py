"""Tests for the scan-to-scan drift/diff service.

These tests verify finding fingerprinting, diff classification, severity drift,
control drift, count invariants, and edge cases (first scan, empty scans,
failed scans, duplicate findings).
"""
from __future__ import annotations

import hashlib
from collections import Counter

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.compliance.diff import compare_scans, _finding_fingerprint
from complisoc.backend.database.base import Base
from complisoc.backend.models import (
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ScanRun,
    ScannerExecution,
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


def _seed_control(db):
    db.add(
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.5.15",
            control_family="Access Control",
            title="Access Control",
            description="Limit access to information and systems.",
            objective="Prevent unauthorized access.",
            evidence_examples=["access_review_report"],
            scanner_signals=["public_access", "iam", "permission"],
            keywords=["public_access", "iam", "permission"],
            source_url="https://example.test/iso-a-5-15",
            active_status=True,
        )
    )
    db.commit()


def _make_raw(db, scan_run_id, scanner_finding_id, raw_json):
    raw = RawFinding(
        scanner_execution_id=scan_run_id,
        scanner_finding_id=scanner_finding_id,
        scanner_name=raw_json.get("scanner_name", "checkov"),
        raw_json=raw_json,
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    return raw


def _make_normalized(db, raw_finding_id, overrides=None):
    raw = db.get(RawFinding, raw_finding_id)
    raw_json = raw.raw_json if raw else {}
    data = {
        "raw_finding_id": raw_finding_id,
        "scanner_name": raw_json.get("scanner_name", "checkov"),
        "finding_type": raw_json.get("finding_type", raw_json.get("check_id", "iam")),
        "resource_type": raw_json.get("resource_type", "iac"),
        "resource_identifier": raw_json.get("resource_identifier", raw_json.get("resource", "unknown")),
        "severity": raw_json.get("severity", "medium"),
        "title": raw_json.get("title", raw_json.get("check_name", "Test finding")),
        "description": raw_json.get("description"),
    }
    if overrides:
        data.update(overrides)
    nf = NormalizedFinding(**data)
    db.add(nf)
    db.commit()
    db.refresh(nf)
    return nf


def _make_scan_run(db, target_environment="test", status="completed"):
    scan = ScanRun(target_environment=target_environment, status=status)
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def _make_scanner_execution(db, scan_run_id, scanner_name="checkov"):
    se = ScannerExecution(scan_run_id=scan_run_id, scanner_name=scanner_name, status="completed")
    db.add(se)
    db.commit()
    db.refresh(se)
    return se


class TestFindingFingerprint:
    def test_stable_across_instances(self):
        engine = _engine()
        db = _session(engine)
        try:
            scan = _make_scan_run(db)
            se = _make_scanner_execution(db, scan.id)
            raw1 = _make_raw(db, se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.x", "title": "t"})
            raw2 = _make_raw(db, se.id, "CKV-2", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.x", "title": "t"})
            nf1 = _make_normalized(db, raw1.id)
            nf2 = _make_normalized(db, raw2.id)
            assert _finding_fingerprint(nf1) == _finding_fingerprint(nf2)
        finally:
            db.close()
            engine.dispose()

    def test_changes_with_resource_identifier(self):
        engine = _engine()
        db = _session(engine)
        try:
            scan = _make_scan_run(db)
            se = _make_scanner_execution(db, scan.id)
            raw1 = _make_raw(db, se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "title": "t"})
            raw2 = _make_raw(db, se.id, "CKV-2", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.b", "title": "t"})
            nf1 = _make_normalized(db, raw1.id)
            nf2 = _make_normalized(db, raw2.id)
            assert _finding_fingerprint(nf1) != _finding_fingerprint(nf2)
        finally:
            db.close()
            engine.dispose()


class TestDiffInvariants:
    def test_previous_equals_resolved_plus_unchanged(self):
        engine = _engine()
        db = _session(engine)
        try:
            _seed_control(db)
            prev = _make_scan_run(db, "prev", "completed")
            prev_se = _make_scanner_execution(db, prev.id)
            prev_raw1 = _make_raw(db, prev_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            prev_raw2 = _make_raw(db, prev_se.id, "CKV-2", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.b", "severity": "medium", "title": "B"})
            prev_nf1 = _make_normalized(db, prev_raw1.id)
            prev_nf2 = _make_normalized(db, prev_raw2.id)

            curr = _make_scan_run(db, "curr", "completed")
            curr_se = _make_scanner_execution(db, curr.id)
            curr_raw1 = _make_raw(db, curr_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            curr_raw3 = _make_raw(db, curr_se.id, "CKV-3", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.c", "severity": "low", "title": "C"})
            curr_nf1 = _make_normalized(db, curr_raw1.id)
            curr_nf3 = _make_normalized(db, curr_raw3.id)

            diff = compare_scans(db, prev.id, curr.id)
            assert diff.previous_finding_count == diff.resolved_count + diff.unchanged_count
            assert diff.current_finding_count == diff.new_count + diff.unchanged_count
        finally:
            db.close()
            engine.dispose()

    def test_current_equals_new_plus_unchanged(self):
        engine = _engine()
        db = _session(engine)
        try:
            prev = _make_scan_run(db, "prev", "completed")
            prev_se = _make_scanner_execution(db, prev.id)
            prev_raw = _make_raw(db, prev_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            _make_normalized(db, prev_raw.id)

            curr = _make_scan_run(db, "curr", "completed")
            curr_se = _make_scanner_execution(db, curr.id)
            curr_raw = _make_raw(db, curr_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            curr_raw2 = _make_raw(db, curr_se.id, "CKV-2", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.b", "severity": "medium", "title": "B"})
            _make_normalized(db, curr_raw.id)
            _make_normalized(db, curr_raw2.id)

            diff = compare_scans(db, prev.id, curr.id)
            assert diff.previous_finding_count == diff.resolved_count + diff.unchanged_count
            assert diff.current_finding_count == diff.new_count + diff.unchanged_count
        finally:
            db.close()
            engine.dispose()


class TestFirstScan:
    def test_first_scan_has_no_previous(self):
        engine = _engine()
        db = _session(engine)
        try:
            scan = _make_scan_run(db, "first", "completed")
            se = _make_scanner_execution(db, scan.id)
            raw = _make_raw(db, se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            _make_normalized(db, raw.id)

            diff = compare_scans(db, None, scan.id)
            assert diff.previous_scan_id is None
            assert diff.new_count == 1
            assert diff.resolved_count == 0
            assert diff.unchanged_count == 0
        finally:
            db.close()
            engine.dispose()


class TestEmptyScans:
    def test_empty_current_scan(self):
        engine = _engine()
        db = _session(engine)
        try:
            prev = _make_scan_run(db, "prev", "completed")
            prev_se = _make_scanner_execution(db, prev.id)
            raw = _make_raw(db, prev_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            _make_normalized(db, raw.id)

            curr = _make_scan_run(db, "curr", "completed")
            _make_scanner_execution(db, curr.id)

            diff = compare_scans(db, prev.id, curr.id)
            assert diff.previous_finding_count == 1
            assert diff.current_finding_count == 0
            assert diff.new_count == 0
            assert diff.resolved_count == 1
            assert diff.unchanged_count == 0
        finally:
            db.close()
            engine.dispose()


class TestFailedScan:
    def test_failed_scan_not_used_as_comparison(self):
        engine = _engine()
        db = _session(engine)
        try:
            failed = _make_scan_run(db, "failed", "failed")
            completed = _make_scan_run(db, "completed", "completed")
            se = _make_scanner_execution(db, completed.id)
            raw = _make_raw(db, se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            _make_normalized(db, raw.id)

            with pytest.raises(ValueError, match="Only completed scans can be compared"):
                compare_scans(db, failed.id, completed.id)
        finally:
            db.close()
            engine.dispose()


class TestSeverityDrift:
    def test_severity_drift_counts(self):
        engine = _engine()
        db = _session(engine)
        try:
            prev = _make_scan_run(db, "prev", "completed")
            prev_se = _make_scanner_execution(db, prev.id)
            raw1 = _make_raw(db, prev_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "critical", "title": "A"})
            raw2 = _make_raw(db, prev_se.id, "CKV-2", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.b", "severity": "high", "title": "B"})
            _make_normalized(db, raw1.id)
            _make_normalized(db, raw2.id)

            curr = _make_scan_run(db, "curr", "completed")
            curr_se = _make_scanner_execution(db, curr.id)
            raw3 = _make_raw(db, curr_se.id, "CKV-3", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.c", "severity": "critical", "title": "C"})
            raw4 = _make_raw(db, curr_se.id, "CKV-4", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.d", "severity": "medium", "title": "D"})
            _make_normalized(db, raw3.id)
            _make_normalized(db, raw4.id)

            diff = compare_scans(db, prev.id, curr.id)
            assert diff.severity_new.get("critical", 0) == 1
            assert diff.severity_new.get("medium", 0) == 1
            assert diff.severity_resolved.get("critical", 0) == 1
            assert diff.severity_resolved.get("high", 0) == 1
        finally:
            db.close()
            engine.dispose()


class TestControlDrift:
    def test_control_drift_uses_published_mappings(self):
        engine = _engine()
        db = _session(engine)
        try:
            _seed_control(db)
            control2 = ControlCatalog(
                framework_name="SOC2",
                framework_version="2017",
                control_id="CC6.1",
                control_family="Access Control",
                title="SOC2 Control",
                description="SOC2 control",
                objective="SOC2 objective",
                evidence_examples=["test"],
                scanner_signals=["iam"],
                keywords=["iam"],
                source_url="https://example.test/soc2",
                active_status=True,
            )
            db.add(control2)
            db.commit()

            prev = _make_scan_run(db, "prev", "completed")
            prev_se = _make_scanner_execution(db, prev.id)
            prev_raw = _make_raw(db, prev_se.id, "CKV-1", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.a", "severity": "high", "title": "A"})
            prev_nf = _make_normalized(db, prev_raw.id)
            prev_mapping = ControlMapping(
                normalized_finding_id=prev_nf.id,
                candidate_control_id=1,
                control_catalog_id=1,
                mapping_model="test",
                prompt_version="v1",
                rationale="test",
                gemini_confidence=0.9,
                final_confidence=0.9,
                mapping_status="published",
            )
            db.add(prev_mapping)
            db.commit()

            curr = _make_scan_run(db, "curr", "completed")
            curr_se = _make_scanner_execution(db, curr.id)
            curr_raw = _make_raw(db, curr_se.id, "CKV-2", {"scanner_name": "checkov", "finding_type": "iam", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.b", "severity": "high", "title": "B"})
            curr_nf = _make_normalized(db, curr_raw.id)
            curr_mapping = ControlMapping(
                normalized_finding_id=curr_nf.id,
                candidate_control_id=control2.id,
                control_catalog_id=control2.id,
                mapping_model="test",
                prompt_version="v1",
                rationale="test",
                gemini_confidence=0.9,
                final_confidence=0.9,
                mapping_status="published",
            )
            db.add(curr_mapping)
            db.commit()

            diff = compare_scans(db, prev.id, curr.id)
            assert "A.5.15" in diff.resolved_control_ids
            assert "CC6.1" in diff.new_control_ids
        finally:
            db.close()
            engine.dispose()
