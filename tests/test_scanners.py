import json
import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.schemas import ScanRequest
from complisoc.backend.api.main import list_available_scanners, run_scan
from complisoc.backend.database.base import Base
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
    with patch.object(runners, "run_scanners", return_value=(fake_findings, [])):
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
    with patch.dict(
        os.environ,
        {
            "AZURE_TENANT_ID": "tenant",
            "AZURE_CLIENT_ID": "client",
            "AZURE_CLIENT_SECRET": "secret",
            "AZURE_SUBSCRIPTION_ID": "sub",
        },
    ), patch.object(runners._requests, "post", return_value=token_resp) as mock_post, patch.object(
        runners._requests, "Session"
    ) as MockSession:
        session_instance = MockSession.return_value
        session_instance.get.return_value = alerts_resp
        session_instance.headers = {}
        findings, error = runners.DefenderScanner().run("target")
    assert error is None
    assert len(findings) == 1
    assert findings[0]["raw_json"]["title"] == "Suspicious login"


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
