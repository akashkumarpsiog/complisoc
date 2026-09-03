"""API endpoint tests for main.py — exercises all routes with mocked AI.

Improves coverage of the FastAPI application layer (dashboard endpoints,
controls, findings, mappings, review queue, reports, audit bundles, scan runs).
All AI calls are mocked to keep tests deterministic and offline.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.main import app
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.models import ControlCatalog, ControlMapping


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = TestingSessionLocal()

    db.add_all([
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.5.15",
            control_family="Access Control",
            title="Access control",
            description="Limit access.",
            source_url="https://example.test/iso-a-5-15",
            active_status=True,
            scanner_signals=["public_access", "iam", "permission"],
            keywords=["access", "iam", "permission", "public"],
        ),
        ControlCatalog(
            framework_name="SOC2",
            framework_version="2017",
            control_id="CC5.2",
            control_family="Monitoring",
            title="System monitoring",
            description="Monitor system activity.",
            source_url="https://example.test/soc2-cc5-2",
            active_status=True,
            scanner_signals=["logging", "audit"],
            keywords=["logging", "audit", "monitor"],
        ),
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _high_signal_finding():
    return {
        "scanner_name": "checkov",
        "scanner_finding_id": "API-1",
        "raw_json": {
            "finding_type": "public_access iam permission",
            "resource_type": "aws_iam_policy",
            "resource_identifier": "aws_iam_policy.public_access",
            "severity": "high",
            "title": "public access iam permission found",
            "description": "Public access on iam permission",
        },
    }


def _seed_scan(client, db_session):
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = lambda items: {
            items[0][0].id: [
                CandidateDecision(
                    control_id=items[0][1][0].control_catalog.control_id,
                    maps=True,
                    confidence=0.95,
                    rationale="oracle",
                )
            ]
        }
        MockVerifier.return_value.verify_batch.return_value = {
            1: VerificationDecision(result="agree", agreement_value=1.0, explanation="oracle")
        }
        resp = client.post(
            "/api/v1/scan-runs",
            json={"target_environment": "api-test", "findings": [_high_signal_finding()]},
        )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_readiness(self, client):
        resp = client.get("/api/v1/readiness")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


class TestControlsAPI:
    def test_list_controls(self, client):
        resp = client.get("/api/v1/controls")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(item["control_id"] == "A.5.15" for item in data)

    def test_list_controls_filter_by_framework(self, client):
        resp = client.get("/api/v1/controls?framework=SOC2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(item["framework_name"] == "SOC2" for item in data)

    def test_get_control(self, client, db_session):
        control = db_session.query(ControlCatalog).first()
        resp = client.get(f"/api/v1/controls/{control.id}")
        assert resp.status_code == 200
        assert resp.json()["control_id"] == control.control_id

    def test_get_control_not_found(self, client):
        resp = client.get("/api/v1/controls/99999")
        assert resp.status_code == 404


class TestFindingsAPI:
    def test_list_findings(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.get(f"/api/v1/findings?scan_run_id={scan_run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["scanner_name"] == "checkov"

    def test_get_finding_not_found(self, client):
        resp = client.get("/api/v1/findings/99999")
        assert resp.status_code == 404


class TestMappingsAPI:
    def test_list_mappings(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.get(f"/api/v1/mappings?scan_run_id={scan_run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_get_mapping_not_found(self, client):
        resp = client.get("/api/v1/mappings/99999")
        assert resp.status_code == 404

    def test_mapping_verification(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        mapping = db_session.query(ControlMapping).first()
        resp = client.get(f"/api/v1/mappings/{mapping.id}/verification")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestReviewQueueAPI:
    def test_list_review_queue_empty(self, client):
        resp = client.get("/api/v1/review-queue")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_approve_review_item_not_found(self, client):
        resp = client.post("/api/v1/review-queue/99999/approve", json={"reviewer_id": "tester", "comments": "ok"})
        assert resp.status_code == 404

    def test_reject_review_item_not_found(self, client):
        resp = client.post("/api/v1/review-queue/99999/reject", json={"reviewer_id": "tester", "comments": "no"})
        assert resp.status_code == 404

    def test_approve_updates_review_and_mapping_without_comments(self, client, db_session):
        from complisoc.backend.models import ReviewQueueItem

        _seed_scan(client, db_session)
        mapping = db_session.query(ControlMapping).first()
        mapping.mapping_status = "manual_review"
        item = ReviewQueueItem(control_mapping_id=mapping.id, status="pending", review_reason_code="LOW_CONFIDENCE")
        db_session.add(item)
        db_session.commit()

        resp = client.post(f"/api/v1/review-queue/{item.id}/approve", json={"reviewer_id": "tester"})

        assert resp.status_code == 200
        db_session.refresh(item)
        db_session.refresh(mapping)
        assert item.status == "approved"
        assert item.comments is None
        assert mapping.mapping_status == "published"

    def test_cannot_decide_review_item_twice(self, client, db_session):
        from complisoc.backend.models import ReviewQueueItem

        _seed_scan(client, db_session)
        mapping = db_session.query(ControlMapping).first()
        item = ReviewQueueItem(control_mapping_id=mapping.id, status="approved", review_reason_code="LOW_CONFIDENCE")
        db_session.add(item)
        db_session.commit()

        resp = client.post(f"/api/v1/review-queue/{item.id}/approve", json={})

        assert resp.status_code == 409


class TestReportsAPI:
    def test_list_reports(self, client):
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_report_not_found(self, client):
        resp = client.get("/api/v1/reports/99999")
        assert resp.status_code == 404

    def test_create_engineering_report(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.post("/api/v1/reports/engineering", json={"scan_run_id": scan_run_id})
        assert resp.status_code == 201
        body = resp.json()
        assert body["report_type"] == "engineering"
        assert Path(body["content_path"]).exists()

    def test_create_leadership_report(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.post("/api/v1/reports/leadership", json={"scan_run_id": scan_run_id})
        assert resp.status_code == 201
        body = resp.json()
        assert body["report_type"] == "leadership"
        assert Path(body["content_path"]).exists()

    def test_create_report_scan_run_not_found(self, client):
        resp = client.post("/api/v1/reports/engineering", json={"scan_run_id": 99999})
        assert resp.status_code == 404

    def test_pdf_download_not_found(self, client):
        resp = client.get("/api/v1/reports/99999/pdf")
        assert resp.status_code == 404


class TestAuditBundlesAPI:
    def test_list_audit_bundles(self, client):
        resp = client.get("/api/v1/audit-bundles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_audit_bundle_not_found(self, client):
        resp = client.get("/api/v1/audit-bundles/99999")
        assert resp.status_code == 404

    def test_create_audit_bundle(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.post("/api/v1/audit-bundles", json={"scan_run_id": scan_run_id})
        assert resp.status_code == 201
        body = resp.json()
        assert "checksum" not in body or body["checksum"] is None
        assert body["bundle_path"]

    def test_download_audit_bundle_not_found(self, client):
        resp = client.get("/api/v1/audit-bundles/99999/download")
        assert resp.status_code == 404

    def test_create_audit_bundle_scan_run_not_found(self, client):
        resp = client.post("/api/v1/audit-bundles", json={"scan_run_id": 99999})
        assert resp.status_code == 404


class TestDashboardAPI:
    def test_control_coverage(self, client, db_session):
        _seed_scan(client, db_session)
        resp = client.get("/api/v1/dashboard/control-coverage")
        assert resp.status_code == 200
        body = resp.json()
        assert "covered_controls" in body
        assert "total_controls" in body

    def test_severity_distribution(self, client, db_session):
        _seed_scan(client, db_session)
        resp = client.get("/api/v1/dashboard/severity-distribution")
        assert resp.status_code == 200
        assert "severity_counts" in resp.json()

    def test_gap_summary(self, client, db_session):
        _seed_scan(client, db_session)
        resp = client.get("/api/v1/dashboard/gap-summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "failed_controls" in body

    def test_remediation_backlog(self, client, db_session):
        _seed_scan(client, db_session)
        mapping = db_session.query(ControlMapping).first()
        mapping.mapping_status = "manual_review"
        db_session.commit()
        resp = client.get("/api/v1/dashboard/remediation-backlog")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert body["items"][0]["control_catalog_id"] == mapping.control_catalog_id
        assert "suggested_remediation_steps" not in body["items"][0]

    def test_control_drill_down_and_on_demand_suggestion(self, client, db_session):
        _seed_scan(client, db_session)
        mapping = db_session.query(ControlMapping).first()
        mapping.mapping_status = "manual_review"
        db_session.commit()
        detail = client.get(f"/api/v1/dashboard/controls/{mapping.control_catalog_id}/drill-down")
        assert detail.status_code == 200
        assert detail.json()["items"][0]["mapping_id"] == mapping.id
        with patch("complisoc.backend.api.main.GROQ_API_KEY", None):
            suggestion = client.post(f"/api/v1/dashboard/remediation-backlog/{mapping.id}/suggestion")
        assert suggestion.status_code == 200
        assert suggestion.json()["source"] == "deterministic_fallback"
        assert len(suggestion.json()["steps"]) >= 2

    def test_trends(self, client, db_session):
        _seed_scan(client, db_session)
        resp = client.get("/api/v1/dashboard/trends")
        assert resp.status_code == 200
        assert "trends" in resp.json()
        assert {"findings", "high_critical_findings", "published", "manual_review"}.issubset(resp.json()["trends"][0])

    def test_cloud_findings(self, client, db_session):
        from complisoc.backend.models import NormalizedFinding, RawFinding, ScannerExecution, ScanRun
        scan_run = ScanRun(target_environment="cloud-test", status="completed")
        db_session.add(scan_run)
        db_session.commit()
        db_session.refresh(scan_run)
        execution = ScannerExecution(scan_run_id=scan_run.id, scanner_name="defender", status="completed")
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)
        raw1 = RawFinding(scanner_execution_id=execution.id, scanner_name="defender", scanner_finding_id="d1", raw_json={"defender_source": "alerts"})
        raw2 = RawFinding(scanner_execution_id=execution.id, scanner_name="defender", scanner_finding_id="d2", raw_json={"defender_source": "assessments"})
        raw3 = RawFinding(scanner_execution_id=execution.id, scanner_name="defender", scanner_finding_id="d3", raw_json={"defender_source": "secureScores"})
        db_session.add_all([raw1, raw2, raw3])
        db_session.commit()
        db_session.refresh(raw1)
        db_session.refresh(raw2)
        db_session.refresh(raw3)
        db_session.add_all([
            NormalizedFinding(
                raw_finding_id=raw1.id,
                scanner_name="defender",
                finding_type="DefenderAlert",
                resource_type="azure-resource",
                resource_identifier="r1",
                severity="high",
                title="Alert",
                metadata_json={"defender_source": "alerts"},
            ),
            NormalizedFinding(
                raw_finding_id=raw2.id,
                scanner_name="defender",
                finding_type="DefenderRecommendation",
                resource_type="azure-resource",
                resource_identifier="r2",
                severity="high",
                title="Rec",
                metadata_json={"defender_source": "assessments"},
            ),
            NormalizedFinding(
                raw_finding_id=raw3.id,
                scanner_name="defender",
                finding_type="DefenderSecureScore",
                resource_type="secure-score",
                resource_identifier="diskEncryption",
                severity="medium",
                title="Score",
                metadata_json={"defender_source": "secureScores"},
            ),
        ])
        db_session.commit()
        resp = client.get("/api/v1/dashboard/cloud-findings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["alerts"] == 1
        assert body["recommendations"] == 1
        assert body["secure_scores"] == 1


class TestScanRunsAPI:
    def test_list_scan_runs(self, client, db_session):
        _seed_scan(client, db_session)
        resp = client.get("/api/v1/scan-runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_get_scan_run(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.get(f"/api/v1/scan-runs/{scan_run_id}")
        assert resp.status_code == 200
        assert resp.json()["target_environment"] == "api-test"

    def test_get_scan_run_not_found(self, client):
        resp = client.get("/api/v1/scan-runs/99999")
        assert resp.status_code == 404

    def test_get_scan_run_summary(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.get(f"/api/v1/scan-runs/{scan_run_id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["normalized_findings"] >= 1

    def test_get_scan_run_summary_not_found(self, client):
        resp = client.get("/api/v1/scan-runs/99999/summary")
        assert resp.status_code == 404


class TestFileResponseErrors:
    def test_report_pdf_file_missing_returns_404(self, client, db_session):
        """When a report record exists but the PDF file was deleted, return 404."""
        from complisoc.backend.reporting.reports import _write_artifact
        from complisoc.backend.models import ComplianceReport
        from uuid import uuid4

        report = ComplianceReport(
            scan_run_id=1,
            report_type="engineering",
            generated_by="test",
            content_path=f"/nonexistent/report-{uuid4().hex}.pdf",
            content_hash="0123456789abcdef",
        )
        db_session.add(report)
        db_session.commit()

        resp = client.get(f"/api/v1/reports/{report.id}/pdf")
        assert resp.status_code == 404

    def test_audit_bundle_download_file_missing_returns_404(self, client, db_session):
        from complisoc.backend.models import AuditBundle
        from uuid import uuid4

        bundle = AuditBundle(
            scan_run_id=1,
            bundle_path=f"/nonexistent/bundle-{uuid4().hex}.json",
            checksum="deadbeef",
        )
        db_session.add(bundle)
        db_session.commit()

        resp = client.get(f"/api/v1/audit-bundles/{bundle.id}/download")
        assert resp.status_code == 404


class TestReviewQueueEdgeCases:
    def test_approve_review_item_missing_mapping(self, client, db_session):
        from complisoc.backend.models import ReviewQueueItem

        item = ReviewQueueItem(
            control_mapping_id=99999,
            status="pending",
            review_reason_code="TEST",
        )
        db_session.add(item)
        db_session.flush()

        resp = client.post(
            f"/api/v1/review-queue/{item.id}/approve",
            json={"reviewer_id": "tester", "comments": "approved"},
        )
        assert resp.status_code == 404


class TestScannersAPI:
    def test_list_scanners(self, client):
        resp = client.get("/api/v1/scanners")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4
        names = {s["name"] for s in data}
        assert {"trivy", "checkov", "sonarqube", "defender"} <= names


class TestAIMetricsAPI:
    def test_ai_metrics_returns_defaults_when_empty(self, client):
        resp = client.get("/api/v1/dashboard/ai-metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_mappings"] == 0
        assert body["manual_review_rate"] == 0.0

    def test_ai_metrics_reflects_published_and_review_counts(self, client, db_session):
        scan_run_id = _seed_scan(client, db_session)
        resp = client.get("/api/v1/dashboard/ai-metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_mappings"] >= 1
        assert body["published_mappings"] >= 1
        assert body["avg_final_confidence"] is not None

    def test_ai_metrics_agreement_rate_reflects_verification_records(self, client, db_session):
        def make_finding(fid):
            return {
                "scanner_name": "checkov",
                "scanner_finding_id": fid,
                "raw_json": {
                    "finding_type": "public_access iam permission",
                    "resource_type": "aws_iam_policy",
                    "resource_identifier": f"aws_iam_policy.public_{fid}",
                    "severity": "high",
                    "title": f"public access iam permission found {fid}",
                    "description": f"Public access on iam permission {fid}",
                },
            }

        with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
            "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
        ) as MockVerifier:
            MockMapper.return_value.map_batch.side_effect = lambda items: {
                items[0][0].id: [CandidateDecision(control_id=items[0][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="oracle")],
                items[1][0].id: [CandidateDecision(control_id=items[1][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="oracle")],
            }
            MockVerifier.return_value.verify_batch.return_value = {
                1: VerificationDecision(result="agree", agreement_value=1.0, explanation="oracle"),
                2: VerificationDecision(result="disagree", agreement_value=0.0, explanation="nope"),
            }
            client.post(
                "/api/v1/scan-runs",
                json={"target_environment": "metrics-test", "findings": [make_finding("MET-1"), make_finding("MET-2")]},
            )
        resp = client.get("/api/v1/dashboard/ai-metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_mappings"] == 2
        assert body["agreement_rate"] == 0.5


class TestAuditBundleVerifyAPI:
    def test_verify_audit_bundle_returns_valid_status(self, client, db_session):
        from complisoc.backend.reporting.reports import generate_audit_bundle

        scan_run_id = _seed_scan(client, db_session)
        bundle = generate_audit_bundle(db_session, scan_run_id=scan_run_id)
        resp = client.get(f"/api/v1/audit-bundles/{bundle.id}/verify")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "VALID"
        assert body["bundle_verified"] is True
        assert body["manifest_verified"] is True

    def test_verify_audit_bundle_not_found(self, client):
        resp = client.get("/api/v1/audit-bundles/99999/verify")
        assert resp.status_code == 404

    def test_verify_audit_bundle_detects_tampered_bundle(self, client, db_session):
        from complisoc.backend.reporting.reports import generate_audit_bundle

        scan_run_id = _seed_scan(client, db_session)
        bundle = generate_audit_bundle(db_session, scan_run_id=scan_run_id)
        original = Path(bundle.bundle_path).read_text(encoding="utf-8")
        tampered = original.replace("scan_run", "scan_ruN")
        Path(bundle.bundle_path).write_text(tampered, encoding="utf-8")
        try:
            resp = client.get(f"/api/v1/audit-bundles/{bundle.id}/verify")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "TAMPERED"
            assert body["bundle_verified"] is False
            assert any("checksum mismatch" in e for e in body["errors"])
        finally:
            Path(bundle.bundle_path).write_text(original, encoding="utf-8")

    def test_verify_audit_bundle_detects_missing_files(self, client, db_session):
        from complisoc.backend.models import AuditBundle
        from uuid import uuid4

        bundle = AuditBundle(
            scan_run_id=1,
            bundle_path=f"/nonexistent/bundle-{uuid4().hex}.json",
            manifest_path=f"/nonexistent/manifest-{uuid4().hex}.json",
            checksum="deadbeef",
        )
        db_session.add(bundle)
        db_session.commit()

        resp = client.get(f"/api/v1/audit-bundles/{bundle.id}/verify")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "TAMPERED"
        assert body["bundle_verified"] is False
        assert body["manifest_verified"] is False
