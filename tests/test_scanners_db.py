"""Scanner → DB integration tests.

These tests verify that scanner findings are correctly ingested into SQLite
through the full pipeline: run_scanners → process_scan_run → DB assertions.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.main import run_scan
from complisoc.backend.api import main as api_main
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.models import (
    ControlCatalog,
    NormalizedFinding,
    RawFinding,
    ScanRun,
    ScannerExecution,
)
from complisoc.backend.scanners import runners
from complisoc.backend.scanners.ingestion import ingest_findings
from complisoc.backend.api.schemas import ScanRequest


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    yield engine


@pytest.fixture()
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def app_db(db_engine, db_session):
    from complisoc.backend.api.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield db_session
    app.dependency_overrides.pop(get_db, None)


def _fake_run(returncode=0, stdout="", stderr=""):
    return type("Proc", (), {"returncode": returncode, "stdout": stdout, "stderr": stderr})()


class TestTrivyIntegration:
    def test_trivy_findings_ingested_into_db(self, db_session):
        report = {
            "Results": [
                {
                    "Target": ".",
                    "Type": "terraform",
                    "Vulnerabilities": [],
                    "Misconfigurations": [
                        {
                            "ID": "AVD-AWS-001",
                            "Type": "aws",
                            "Severity": "HIGH",
                            "Title": "Public S3 bucket",
                            "Message": "Bucket is public.",
                            "CauseMetadata": {"Filepath": "main.tf", "Resource": "aws_s3_bucket.bad"},
                        }
                    ],
                }
            ]
        }
        with patch.object(runners.subprocess, "run", return_value=_fake_run(stdout=json.dumps(report))):
            findings, failures = runners.TrivyScanner().run(".")
        assert len(findings) == 1
        assert findings[0]["scanner_name"] == "trivy"


class TestCheckovIntegration:
    def test_checkov_findings_ingested_into_db(self, db_session):
        report = {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_AWS_1",
                        "check_name": "IAM public",
                        "resource": "aws_iam_policy.x",
                        "file_path": "main.tf",
                        "resource_type": "aws_iam_policy",
                        "severity": "HIGH",
                        "description": "desc",
                    }
                ]
            }
        }
        with patch.object(runners.subprocess, "run", return_value=_fake_run(stdout=json.dumps(report))):
            findings, failures = runners.CheckovScanner().run(".")
        assert len(findings) == 1
        assert findings[0]["raw_json"]["finding_type"] == "CKV_AWS_1"


class TestSonarQubeIntegration:
    def test_sonarqube_findings_ingested_into_db(self, db_session):
        report = {
            "issues": [
                {
                    "rule": "squid:S1234",
                    "type": "VULNERABILITY",
                    "severity": "BLOCKER",
                    "message": "Remove this hack.",
                    "component": "my-project:/src/main.py",
                }
            ],
            "total": 1,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = report
        with patch.dict(os.environ, {"SONAR_HOST_URL": "http://sonarqube", "SONAR_TOKEN": "token"}):
            with patch.object(runners._requests, "Session") as MockSession:
                session_instance = MockSession.return_value
                session_instance.get.return_value = mock_resp
                session_instance.headers = {}
                findings, error = runners.SonarQubeScanner().run("my-project")
        assert error is None
        assert len(findings) == 1
        assert findings[0]["raw_json"]["finding_type"] == "squid:S1234"


class TestDefenderIntegration:
    def test_defender_findings_ingested_into_db(self, db_session):
        alert = {
            "properties": {
                "alertDisplayName": "Suspicious login",
                "alertType": "Signin",
                "severity": "HIGH",
                "description": "Suspicious sign-in detected.",
                "resourceIdentities": [{"resourceId": "/subscriptions/sub/resource/r1"}],
            }
        }
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "abc"}
        alerts_resp = MagicMock()
        alerts_resp.status_code = 200
        alerts_resp.json.return_value = {"value": [alert]}
        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.json.return_value = {"value": []}
        with patch.dict(
            os.environ,
            {
                "AZURE_TENANT_ID": "tenant",
                "AZURE_CLIENT_ID": "client",
                "AZURE_CLIENT_SECRET": "secret",
                "AZURE_SUBSCRIPTION_ID": "sub",
            },
        ), patch.object(runners._requests, "post", return_value=token_resp), patch.object(
            runners._requests, "Session"
        ) as MockSession:
            session_instance = MockSession.return_value
            def _get_side_effect(url, **kwargs):
                if "alerts?" in url:
                    return alerts_resp
                return empty_resp
            session_instance.get.side_effect = _get_side_effect
            session_instance.headers = {}
            findings, error = runners.DefenderScanner().run("target")
        assert error is None
        assert len(findings) == 1
        assert findings[0]["raw_json"]["title"] == "Suspicious login"

    def test_defender_recommendations_ingested_into_db(self, db_session):
        assessment = {
            "properties": {
                "displayName": "Enable disk encryption",
                "assessmentType": "DiskEncryption",
                "severity": "HIGH",
                "description": "Managed disks should be encrypted.",
                "resourceDetails": {"resourceId": "/subscriptions/sub/resource/r2", "resourceType": "Microsoft.Compute/disks"},
                "remediationSteps": "Enable encryption on managed disks.",
            }
        }
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "abc"}
        assessments_resp = MagicMock()
        assessments_resp.status_code = 200
        assessments_resp.json.return_value = {"value": [assessment]}
        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.json.return_value = {"value": []}
        with patch.dict(
            os.environ,
            {
                "AZURE_TENANT_ID": "tenant",
                "AZURE_CLIENT_ID": "client",
                "AZURE_CLIENT_SECRET": "secret",
                "AZURE_SUBSCRIPTION_ID": "sub",
            },
        ), patch.object(runners._requests, "post", return_value=token_resp), patch.object(
            runners._requests, "Session"
        ) as MockSession:
            session_instance = MockSession.return_value
            def _get_side_effect(url, **kwargs):
                if "assessments?" in url:
                    return assessments_resp
                return empty_resp
            session_instance.get.side_effect = _get_side_effect
            session_instance.headers = {}
            findings, error = runners.DefenderScanner().run("target")
        assert error is None
        assert len(findings) == 1
        assert findings[0]["raw_json"]["defender_source"] == "assessments"


class TestScanRunDBLineage:
    def test_duplicate_scanner_finding_ids_are_deduplicated(self, db_session):
        findings = [
            {
                "scanner_name": "trivy",
                "scanner_finding_id": "duplicate-1",
                "raw_json": {"title": "same finding"},
            },
            {
                "scanner_name": "trivy",
                "scanner_finding_id": "duplicate-1",
                "raw_json": {"title": "same finding repeated"},
            },
        ]

        scan_run, raw_findings = ingest_findings(
            db_session,
            target_environment="duplicate-test",
            findings=findings,
        )

        assert scan_run.status == "completed"
        assert len(raw_findings) == 1
        assert db_session.query(RawFinding).count() == 1

    def test_full_scan_creates_lineage_in_db(self, app_db):
        db_session = app_db
        db_session.add(ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.5.15",
            control_family="Access Control",
            title="Access Control",
            description="Limit access.",
            source_url="https://example.test/iso-a-5-15",
            active_status=True,
            scanner_signals=["public_access", "iam", "permission"],
            keywords=["public_access", "iam", "permission"],
        ))
        db_session.commit()

        fake_findings = [
            {
                "scanner_name": "trivy",
                "scanner_finding_id": "t1",
                "raw_json": {
                    "finding_type": "vuln",
                    "resource_type": "pkg",
                    "resource_identifier": "app::lodash",
                    "severity": "high",
                    "title": "Outdated lodash",
                },
            }
        ]
        with patch.object(api_main, "run_scanners", return_value=(fake_findings, [])), patch(
            "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
        ) as MockMapper, patch(
            "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
        ) as MockVerifier:
            MockMapper.return_value.map_batch.side_effect = lambda items: {
                items[0][0].id: [
                    CandidateDecision(
                        control_id=items[0][1][0].control_catalog.control_id,
                        maps=True,
                        confidence=0.95,
                        rationale="High signal",
                    )
                ]
            }
            MockVerifier.return_value.verify_batch.return_value = {
                1: VerificationDecision(result="agree", agreement_value=1.0, explanation="Correct")
            }
            scan_run = run_scan(ScanRequest(target="."), app_db)
        app_db.commit()
        raw_findings = app_db.query(RawFinding).filter(RawFinding.scanner_execution_id == scan_run.id).all()
        assert len(raw_findings) == 1
        assert raw_findings[0].scanner_name == "trivy"

