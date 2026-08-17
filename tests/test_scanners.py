import json
import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.schemas import ScanRequest
from complisoc.backend.api.main import list_available_scanners, run_scan
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.models import ControlCatalog
from complisoc.backend.scanners import runners


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
    try:
        yield db
    finally:
        db.close()


def _fake_run(returncode=0, stdout="", stderr=""):
    return type("Proc", (), {"returncode": returncode, "stdout": stdout, "stderr": stderr})()


def test_list_scanners_exposes_all_runners():
    items = list_available_scanners()
    names = {item.name for item in items}
    assert {"trivy", "checkov", "sonarqube", "defender"} <= names


def test_run_scan_ingests_findings(db_session):
    db_session.add(
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.5.15",
            control_family="Access Control",
            title="Access Control",
            description="Limit access to information and systems.",
            source_url="https://example.test/iso-a-5-15",
            active_status=True,
            scanner_signals=["public_access", "iam", "permission"],
            keywords=["public_access", "iam", "permission"],
        )
    )
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
    with patch("complisoc.backend.api.main.run_scanners", return_value=(fake_findings, [])), patch(
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
        scan_run = run_scan(ScanRequest(target="."), db_session)
    assert scan_run.target_environment == "."


def test_trivy_parser_extracts_vulns_and_misconfigs():
    report = {
        "Results": [
            {
                "Target": "app",
                "Type": "npm",
                "Vulnerabilities": [
                    {"VulnerabilityID": "CVE-1", "PkgName": "lodash", "Severity": "HIGH", "Title": "Bad", "Description": "desc"}
                ],
            },
            {
                "Target": "iac",
                "Type": "terraform",
                "Misconfigurations": [
                    {
                        "ID": "AVD-1",
                        "Type": "azure",
                        "Severity": "MEDIUM",
                        "Title": "Public",
                        "Message": "msg",
                        "CauseMetadata": {"Filepath": "main.tf", "Resource": "aws_thing"},
                    }
                ],
            },
        ]
    }
    with patch.object(runners.subprocess, "run", return_value=_fake_run(stdout=json.dumps(report))):
        findings, error = runners.TrivyScanner().run(".")
    assert error is None
    assert len(findings) == 2
    assert all(f["scanner_name"] == "trivy" for f in findings)
    assert findings[0]["raw_json"]["finding_type"] == "CVE-1"
    assert findings[1]["raw_json"]["resource_identifier"] == "main.tf::aws_thing"


def test_checkov_parser_extracts_failed_checks():
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
        findings, error = runners.CheckovScanner().run(".")
    assert error is None
    assert len(findings) == 1
    assert findings[0]["raw_json"]["finding_type"] == "CKV_AWS_1"
    assert findings[0]["raw_json"]["resource_identifier"] == "main.tf::aws_iam_policy.x"


def test_run_scanners_records_failure_when_binary_missing():
    with patch.object(runners.shutil, "which", return_value=None):
        findings, failures = runners.run_scanners(".", ["trivy"])
    assert findings == []
    assert failures and failures[0]["scanner_name"] == "trivy"


def test_sonarqube_parser_extracts_issues():
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
    with patch.dict(os.environ, {"SONAR_HOST_URL": "http://sonarqube", "SONAR_TOKEN": "token"}):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = report
        with patch.object(runners._requests, "Session") as MockSession:
            session_instance = MockSession.return_value
            session_instance.get.return_value = mock_resp
            session_instance.headers = {}
            findings, error = runners.SonarQubeScanner().run("my-project")
    assert error is None
    assert len(findings) == 1
    assert findings[0]["raw_json"]["finding_type"] == "squid:S1234"
    assert findings[0]["raw_json"]["resource_identifier"] == "my-project:/src/main.py"


def test_defender_parser_extracts_alerts():
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
    assert findings[0]["raw_json"]["defender_source"] == "alerts"


def test_defender_parser_extracts_assessments():
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
    assert findings[0]["raw_json"]["finding_type"] == "Enable disk encryption"
    assert findings[0]["raw_json"]["defender_source"] == "assessments"
    assert findings[0]["raw_json"]["remediationSteps"] == "Enable encryption on managed disks."


def test_defender_parser_extracts_secure_scores():
    score = {
        "properties": {
            "displayName": "Secure score",
            "severity": "MEDIUM",
            "description": "Overall secure score.",
            "score": {"controlId": "diskEncryption", "current": 2, "max": 10},
            "percentage": 20,
        }
    }
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {"access_token": "abc"}
    scores_resp = MagicMock()
    scores_resp.status_code = 200
    scores_resp.json.return_value = {"value": [score]}
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
            if "secureScores?" in url:
                return scores_resp
            return empty_resp
        session_instance.get.side_effect = _get_side_effect
        session_instance.headers = {}
        findings, error = runners.DefenderScanner().run("target")
    assert error is None
    assert len(findings) == 1
    assert findings[0]["raw_json"]["finding_type"] == "DefenderSecureScore"
    assert findings[0]["raw_json"]["defender_source"] == "secureScores"


def test_defender_retry_on_transient_failure():
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {"access_token": "abc"}
    fail_resp = MagicMock()
    fail_resp.status_code = 429
    fail_resp.raise_for_status.side_effect = runners._requests.HTTPError("429 Too Many Requests")
    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.json.return_value = {"value": []}
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
        session_instance.get.side_effect = [fail_resp, success_resp, success_resp, success_resp, success_resp]
        session_instance.headers = {}
        findings, error = runners.DefenderScanner().run("target")
    assert error is None
    assert findings == []
    assert session_instance.get.call_count >= 2


def test_sonarqube_missing_env_returns_failure():
    with patch.dict(os.environ, {}, clear=True):
        findings, failures = runners.run_scanners(".", ["sonarqube"])
    assert findings == []
    assert failures and failures[0]["scanner_name"] == "sonarqube"


def test_defender_missing_env_returns_failure():
    with patch.dict(os.environ, {}, clear=True):
        findings, failures = runners.run_scanners(".", ["defender"])
    assert findings == []
    assert failures and failures[0]["scanner_name"] == "defender"
