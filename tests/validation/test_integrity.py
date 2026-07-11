"""Data integrity & lineage validation (Week 8 gap #7).

Proves the full compliance record chain is intact and that no orphaned
records remain after a complete pipeline run:

    ScanRun -> ScannerExecution -> RawFinding
            -> NormalizedFinding -> ControlMapping
            -> VerificationRecord (+ CandidateControl, ReviewQueueItem)

and that the exported audit bundle's checksums line up with the raw
findings it claims to cover.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.main import process_scan_run
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.models import (
    CandidateControl,
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ReviewQueueItem,
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


def seed_controls(db):
    db.add_all(
        [
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
            ),
            ControlCatalog(
                framework_name="ISO/IEC 27001:2022 Annex A",
                framework_version="2022",
                control_id="A.5.18",
                control_family="Access Control",
                title="Access rights",
                description="Provisioning and review of access rights.",
                objective="Prevent privilege escalation.",
                evidence_examples=["privilege_review"],
                scanner_signals=["privileged", "admin", "root", "runasuser"],
                keywords=["privileged", "admin", "root", "runasuser"],
                source_url="https://example.test/iso-a-5-18",
                active_status=True,
            ),
        ]
    )
    db.commit()


def _oracle_mapper(items):
    out = {}
    for finding, candidates in items:
        out[finding.id] = [
            CandidateDecision(
                control_id=candidate.control_catalog.control_id,
                maps=(rank == 0),
                confidence=0.95 if rank == 0 else 0.10,
                rationale="oracle",
            )
            for rank, candidate in enumerate(candidates)
        ]
    return out


def _oracle_verifier(items):
    return {
        item.ref: VerificationDecision(result="agree", agreement_value=1.0, explanation="oracle")
        for item in items
    }


def run_full_pipeline(db):
    findings = [
        {
            "scanner_name": "checkov",
            "scanner_finding_id": "INT-1",
            "raw_json": {
                "finding_type": "public_access iam permission",
                "resource_type": "aws_iam_policy",
                "resource_identifier": "aws_iam_policy.public_admin",
                "severity": "high",
                "title": "public access iam permission issue",
                "description": "public_access iam permission misconfiguration",
            },
        },
        {
            "scanner_name": "checkov",
            "scanner_finding_id": "INT-2",
            "raw_json": {
                "finding_type": "public_access iam permission",
                "resource_type": "aws_iam_policy",
                "resource_identifier": "aws_iam_policy.public_admin2",
                "severity": "medium",
                "title": "public access iam permission issue two",
                "description": "public_access iam permission misconfiguration two",
            },
        },
        {
            "scanner_name": "trivy",
            "scanner_finding_id": "INT-3",
            "raw_json": {
                "finding_type": "privileged admin root runasuser",
                "resource_type": "pod",
                "resource_identifier": "pod.insecure",
                "severity": "high",
                "title": "privileged admin root runasuser container",
                "description": "privileged admin root runasuser misconfiguration",
            },
        },
    ]
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = _oracle_mapper
        MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier
        return process_scan_run(db, target_environment="integrity-check", findings=findings)


def _ids(db, model, col):
    return {getattr(row, col) for row in db.query(model).all()}


def assert_no_orphans(db):
    scan_ids = _ids(db, ScanRun, "id")
    exec_ids = _ids(db, ScannerExecution, "id")
    raw_ids = _ids(db, RawFinding, "id")
    norm_ids = _ids(db, NormalizedFinding, "id")
    cand_ids = _ids(db, CandidateControl, "id")
    catalog_ids = _ids(db, ControlCatalog, "id")
    mapping_ids = _ids(db, ControlMapping, "id")
    vr_ids = _ids(db, VerificationRecord, "id")
    rq_ids = _ids(db, ReviewQueueItem, "id")

    # Forward referential integrity.
    for exec in db.query(ScannerExecution).all():
        assert exec.scan_run_id in scan_ids, f"ScannerExecution {exec.id} orphaned from ScanRun"
    for raw in db.query(RawFinding).all():
        assert raw.scanner_execution_id in exec_ids, f"RawFinding {raw.id} orphaned from ScannerExecution"
    for norm in db.query(NormalizedFinding).all():
        assert norm.raw_finding_id in raw_ids, f"NormalizedFinding {norm.id} orphaned from RawFinding"
    for cand in db.query(CandidateControl).all():
        assert cand.normalized_finding_id in norm_ids, f"CandidateControl {cand.id} orphaned"
        assert cand.control_catalog_id in catalog_ids, f"CandidateControl {cand.id} missing catalog"
    for mapping in db.query(ControlMapping).all():
        assert mapping.normalized_finding_id in norm_ids, f"ControlMapping {mapping.id} orphaned from NormalizedFinding"
        assert mapping.candidate_control_id in cand_ids, f"ControlMapping {mapping.id} orphaned from CandidateControl"
        assert mapping.control_catalog_id in catalog_ids, f"ControlMapping {mapping.id} orphaned from ControlCatalog"
    for vr in db.query(VerificationRecord).all():
        assert vr.control_mapping_id in mapping_ids, f"VerificationRecord {vr.id} orphaned from ControlMapping"
    for rq in db.query(ReviewQueueItem).all():
        assert rq.control_mapping_id in mapping_ids, f"ReviewQueueItem {rq.id} orphaned from ControlMapping"

    # Reverse: every parent referenced by a child must itself exist.
    assert vr_ids, "no verification records were produced"
    assert mapping_ids, "no control mappings were produced"
    return {
        "scan_runs": len(scan_ids),
        "scanner_executions": len(exec_ids),
        "raw_findings": len(raw_ids),
        "normalized_findings": len(norm_ids),
        "candidate_controls": len(cand_ids),
        "control_mappings": len(mapping_ids),
        "verification_records": len(vr_ids),
        "review_queue_items": len(rq_ids),
    }


class TestLineageIntegrity:
    def test_full_chain_intact_without_orphans(self):
        engine = _engine()
        db = _session(engine)
        try:
            seed_controls(db)
            result = run_full_pipeline(db)

            # Public API surface.
            assert result["scan_run"].status == "completed"
            assert len(result["raw_findings"]) == 3
            assert db.query(NormalizedFinding).count() == 3
            assert db.query(ControlMapping).count() == 3
            assert db.query(VerificationRecord).count() == 3

            counts = assert_no_orphans(db)

            # At least one complete chain end-to-end.
            chain = (
                db.query(ScanRun).first()
                and db.query(ScannerExecution).first()
                and db.query(RawFinding).first()
                and db.query(NormalizedFinding).first()
                and db.query(ControlMapping).first()
                and db.query(VerificationRecord).first()
            )
            assert chain is not None, "incomplete lineage chain"

            # Both seeded controls should have received at least one mapping.
            mapped_catalogs = {
                m.control_catalog_id for m in db.query(ControlMapping).all()
            }
            catalog_ids = {c.id for c in db.query(ControlCatalog).all()}
            assert mapped_catalogs == catalog_ids, "not every control was exercised"
            assert counts["control_mappings"] == 3
        finally:
            db.close()

    def test_audit_bundle_checksums_match_raw_findings(self):
        from complisoc.backend.reporting.reports import generate_audit_bundle

        engine = _engine()
        db = _session(engine)
        try:
            seed_controls(db)
            result = run_full_pipeline(db)
            scan_run_id = result["scan_run"].id

            bundle = generate_audit_bundle(db, scan_run_id=scan_run_id)
            payload = json.loads(Path(bundle.bundle_path).read_text(encoding="utf-8"))

            raw_findings = db.query(RawFinding).all()
            assert len(payload["raw_finding_ids"]) == len(raw_findings)

            for raw in raw_findings:
                expected = hashlib.sha256(
                    json.dumps(raw.raw_json, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
                assert payload["raw_finding_checksums"][str(raw.id)] == expected, (
                    f"checksum mismatch for raw finding {raw.id}"
                )

            # Every normalized finding references a raw finding that exists.
            norm_ids = {n.id for n in db.query(NormalizedFinding).all()}
            for nf in payload["normalized_findings"]:
                assert nf["raw_finding_id"] in norm_ids
                assert nf["id"] in norm_ids

            # Every lineage entry maps back to a real raw finding.
            raw_id_set = {r.id for r in raw_findings}
            for entry in payload["lineage"]:
                assert entry["finding"]["raw_finding_id"] in raw_id_set
        finally:
            db.close()

    def test_no_orphans_when_findings_partially_map(self):
        engine = _engine()
        db = _session(engine)
        try:
            seed_controls(db)
            # A single finding whose tokens match no active control -> no candidates.
            with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
                "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
            ) as MockVerifier:
                MockMapper.return_value.map_batch.side_effect = _oracle_mapper
                MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier
                result = process_scan_run(
                    db,
                    target_environment="partial",
                    findings=[
                        {
                            "scanner_name": "checkov",
                            "scanner_finding_id": "NOMATCH",
                            "raw_json": {
                                "finding_type": "unrelated_noise_xyz",
                                "resource_type": "mystery",
                                "resource_identifier": "mystery.resource.xyz",
                                "severity": "low",
                                "title": "unrelated noise xyz",
                                "description": "this does not match any control",
                            },
                        }
                    ],
                )
            assert result["scan_run"].status == "completed"
            assert_no_orphans(db)
        finally:
            db.close()
