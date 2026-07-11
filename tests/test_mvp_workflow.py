import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.main import app
from complisoc.backend.compliance.confidence import calculate_final_confidence, publication_status
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.models import ControlCatalog, ControlMapping, NormalizedFinding, ReviewQueueItem, ScannerExecution, VerificationRecord
from complisoc.backend.normalization.normalizer import normalize_severity


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
    seed_controls(db)
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


def seed_controls(db):
    db.add_all(
        [
            ControlCatalog(
                framework_name="ISO/IEC 27001:2022 Annex A",
                framework_version="2022",
                control_id="A.5.15",
                control_family="Organizational",
                title="Access Control",
                description="Limit access to information and systems based on business and security requirements.",
                objective="Prevent unauthorized access.",
                evidence_examples=["access_review_report"],
                scanner_signals=["iam", "public_access", "permission"],
                keywords=["access", "iam", "permission", "public"],
                source_url="https://example.test/iso-a-5-15",
                active_status=True,
            ),
            ControlCatalog(
                framework_name="SOC 2 Trust Services Criteria (TSC) 2022",
                framework_version="2017 (Revised Points of Focus - 2022)",
                control_id="CC6.6",
                control_family="Logical and Physical Access Controls",
                title="Protection Against External Threats",
                description="Restrict inbound and outbound network traffic.",
                objective="Limit external exposure.",
                evidence_examples=["firewall_rules"],
                scanner_signals=["security_group", "open_ingress", "0.0.0.0/0"],
                keywords=["network", "firewall", "public", "ingress"],
                source_url="https://example.test/soc2-cc6-6",
                active_status=True,
            ),
        ]
    )
    db.commit()


def high_signal_finding():
    return {
        "scanner_name": "checkov",
        "scanner_finding_id": "CKV_AWS_1",
        "raw_json": {
            "finding_type": "iam public access permission",
            "resource_type": "aws_iam_policy",
            "resource_identifier": "aws_iam_policy.public_admin",
            "severity": "high",
            "title": "IAM policy allows public access permission",
            "description": "iam public access permission public iam access permission",
        },
    }


def low_signal_finding():
    return {
        "scanner_name": "checkov",
        "scanner_finding_id": "CKV_LOW_1",
        "raw_json": {
            "finding_type": "network",
            "resource_type": "aws_security_group",
            "resource_identifier": "sg-open",
            "severity": "medium",
            "title": "Network issue",
            "description": "network",
        },
    }


def test_confidence_threshold_rules():
    assert calculate_final_confidence(0.5, 1.0) == 0.7
    assert publication_status(0.7) == "published"
    assert publication_status(0.6999) == "manual_review"


def test_normalization_rejects_invalid_severity():
    with pytest.raises(ValueError):
        normalize_severity("urgent")


def test_process_scan_run_creates_full_lineage(db_session):
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = lambda items: {
            items[0][0].id: [CandidateDecision(control_id=items[0][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="High signal")],
            items[1][0].id: [CandidateDecision(control_id=items[1][1][0].control_catalog.control_id, maps=True, confidence=0.40, rationale="Low signal")],
        }
        MockVerifier.return_value.verify_batch.return_value = {
            1: VerificationDecision(result="agree", agreement_value=1.0, explanation="Correct", model="groq", prompt_version="mvp-v1"),
            2: VerificationDecision(result="disagree", agreement_value=0.0, explanation="Incorrect", model="groq", prompt_version="mvp-v1"),
        }

        result = process_scan_run(
            db_session,
            target_environment="aws-iac",
            findings=[high_signal_finding(), low_signal_finding()],
        )

    assert result["scan_run"].status == "completed"
    assert len(result["raw_findings"]) == 2
    assert db_session.query(NormalizedFinding).count() == 2
    assert db_session.query(ControlMapping).count() == 2
    assert db_session.query(ReviewQueueItem).count() == 1
    assert MockMapper.return_value.map_batch.call_count == 1
    assert MockVerifier.return_value.verify_batch.call_count == 1

    published = db_session.query(ControlMapping).filter(ControlMapping.mapping_status == "published").one()
    assert published.final_confidence >= 0.70
    assert published.gemini_confidence == pytest.approx(0.95)
    assert published.groq_agreement_value == pytest.approx(1.0)

    manual_review = db_session.query(ControlMapping).filter(ControlMapping.mapping_status == "manual_review").one()
    assert manual_review.final_confidence < 0.70
    assert manual_review.gemini_confidence == pytest.approx(0.40)
    assert manual_review.groq_agreement_value == pytest.approx(0.0)


def test_api_scan_run_and_reports(client):
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = lambda items: {
            items[0][0].id: [CandidateDecision(control_id=items[0][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="High signal")]
        }
        MockVerifier.return_value.verify_batch.return_value = {
            1: VerificationDecision(result="agree", agreement_value=1.0, explanation="Correct"),
        }

        response = client.post(
            "/api/v1/scan-runs",
            json={"target_environment": "aws-iac", "findings": [high_signal_finding()]},
        )
    assert response.status_code == 201
    scan_run_id = response.json()["id"]

    summary = client.get(f"/api/v1/scan-runs/{scan_run_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["mappings"] == 1

    engineering = client.post("/api/v1/reports/engineering", json={"scan_run_id": scan_run_id})
    assert engineering.status_code == 201
    assert engineering.json()["content_hash"]

    bundle = client.post("/api/v1/audit-bundles", json={"scan_run_id": scan_run_id})
    assert bundle.status_code == 201
    assert bundle.json()["checksum"]

    controls = client.get("/api/v1/controls")
    assert controls.status_code == 200
    assert len(controls.json()) == 2


def test_scanner_failure_is_persisted_explicitly(db_session):
    result = process_scan_run(
        db_session,
        target_environment="aws-iac",
        findings=[],
        scanner_failures=[{"scanner_name": "trivy", "error_message": "binary not found"}],
    )

    assert result["scan_run"].status == "failed"
    failed_execution = (
        db_session.query(ScannerExecution)
        .filter(ScannerExecution.scanner_name == "trivy")
        .one()
    )
    assert failed_execution.status == "failed"
    assert failed_execution.error_message == "binary not found"


def test_api_rejects_malformed_scan_run(client):
    response = client.post(
        "/api/v1/scan-runs",
        json={
            "target_environment": "aws-iac",
            "findings": [
                {
                    "scanner_name": "checkov",
                    "scanner_finding_id": "CKV_BAD",
                    "raw_json": "not-an-object",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_leadership_report_uses_published_posture_only(client):
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = lambda items: {
            items[0][0].id: [CandidateDecision(control_id=items[0][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="High signal")],
            items[1][0].id: [CandidateDecision(control_id=items[1][1][0].control_catalog.control_id, maps=True, confidence=0.40, rationale="Low signal")],
        }
        MockVerifier.return_value.verify_batch.return_value = {
            1: VerificationDecision(result="agree", agreement_value=1.0, explanation="Correct"),
            2: VerificationDecision(result="disagree", agreement_value=0.0, explanation="Incorrect"),
        }

        response = client.post(
            "/api/v1/scan-runs",
            json={"target_environment": "aws-iac", "findings": [high_signal_finding(), low_signal_finding()]},
        )
    scan_run_id = response.json()["id"]

    leadership = client.post("/api/v1/reports/leadership", json={"scan_run_id": scan_run_id})
    assert leadership.status_code == 201
    report = leadership.json()
    assert report["scan_run_id"] == scan_run_id
    assert report["report_type"] == "leadership"
    assert report["content_path"].endswith(".pdf")
    assert Path(report["content_path"]).exists()


def test_audit_bundle_contains_lineage_checksums(client):
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = lambda items: {
            items[0][0].id: [CandidateDecision(control_id=items[0][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="High signal")]
        }
        MockVerifier.return_value.verify_batch.return_value = {
            1: VerificationDecision(result="agree", agreement_value=1.0, explanation="Correct"),
        }

        response = client.post(
            "/api/v1/scan-runs",
            json={"target_environment": "aws-iac", "findings": [high_signal_finding()]},
        )
    scan_run_id = response.json()["id"]

    bundle = client.post("/api/v1/audit-bundles", json={"scan_run_id": scan_run_id})
    assert bundle.status_code == 201
    bundle_path = Path(bundle.json()["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))

    assert payload["scan_run"]["id"] == scan_run_id
    assert payload["raw_finding_ids"]
    assert set(payload["raw_finding_checksums"]) == {str(raw_id) for raw_id in payload["raw_finding_ids"]}
    assert payload["normalized_findings"][0]["raw_finding_id"] in payload["raw_finding_ids"]
    assert payload["lineage"][0]["finding"]["raw_finding_id"] in payload["raw_finding_ids"]
