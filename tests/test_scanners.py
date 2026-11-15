import asyncio
import json
import os
import sys
import time
from threading import Event, Timer
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.schemas import ScanRequest
from complisoc.backend.api.main import list_available_scanners, _execute_scan
from complisoc.backend.compliance.mapping import CandidateDecision, _finding_fingerprint
from complisoc.backend.compliance.langchain_pipeline import run_pipeline
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.models import ControlCatalog, NormalizedFinding, ScanRun
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
            _finding_fingerprint(items[0][0]): [
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
        scan_run = ScanRun(target_environment=".", status="running")
        db_session.add(scan_run)
        db_session.commit()
        db_session.refresh(scan_run)
        cancel_event = Event()
        _execute_scan(
            scan_run.id, ".", None, None, "full", None, cancel_event, db=db_session,
        )
    assert scan_run.target_environment == "."
    assert scan_run.status == "completed"
    assert db_session.query(NormalizedFinding).count() >= 1


def test_run_scan_cancels_scanner_work_after_client_disconnect(db_session):
    """Test that cancellation event is passed to scanners (sync version)."""
    observed = {}

    def run_until_cancelled(*args, cancel_event=None, **kwargs):
        observed["cancel_event"] = cancel_event
        # In sync version, cancellation is checked before each scanner
        if cancel_event and cancel_event.is_set():
            return [], []
        # Simulate scanner running
        return [], []

    with patch("complisoc.backend.api.main.run_scanners", side_effect=run_until_cancelled), patch(
        "complisoc.backend.api.main._run_compliance_pipeline",
        return_value={"scan_run": "cancelled"},
    ):
        scan_run = ScanRun(target_environment=".", status="running")
        db_session.add(scan_run)
        db_session.commit()
        db_session.refresh(scan_run)
        cancel_event = Event()
        cancel_event.set()  # simulate client-disconnect cancellation
        _execute_scan(
            scan_run.id, ".", None, None, "full", None, cancel_event, db=db_session,
        )

    assert scan_run.status == "failed"
    # The cancel_event is passed to scanners so they can stop work.
    assert "cancel_event" in observed


def test_cancelled_scanner_marks_not_started_scanners_as_failed():
    cancel_event = Event()
    first = MagicMock()
    first.is_available.return_value = True
    first.kind = "local"
    first.run.side_effect = runners.ScanCancelled("Scan cancelled by user.")
    second = MagicMock()
    second.is_available.return_value = True
    second.kind = "local"

    # Patch the entire SCANNER_RUNNERS dict
    with patch.object(runners, "SCANNER_RUNNERS", {"trivy": first, "checkov": second}):
        findings, failures = runners.run_scanners(
            ".",
            scanners=["trivy", "checkov"],
            cancel_event=cancel_event,
        )

    assert findings == []
    # In parallel execution, both scanners are submitted simultaneously.
    # The first raises ScanCancelled, which sets the cancel_event.
    # The second should see the cancelled event and fail with cancelled message.
    assert {failure["scanner_name"] for failure in failures} == {"trivy", "checkov"}
    for failure in failures:
        assert "cancelled" in failure["error_message"].lower()
    # In parallel mode, both may be called, but second should see cancellation
    # The key assertion is that both end up as failures with cancelled message


def test_cancelled_pipeline_marks_scan_failed(db_session):
    cancel_event = Event()
    cancel_event.set()

    result = run_pipeline(
        db_session,
        target_environment=".",
        findings=[],
        cancel_event=cancel_event,
    )

    assert result["scan_run"].status == "failed"
    assert any("cancelled" in failure.get("error", "").lower() for failure in result["failures"])


def test_run_command_terminates_process_when_cancelled():
    cancel_event = Event()
    timer = Timer(0.1, cancel_event.set)
    timer.start()
    try:
        with pytest.raises(runners.ScanCancelled, match="cancelled"):
            runners._run_command(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                timeout=30,
                cancel_event=cancel_event,
            )
    finally:
        timer.join()


def test_defender_connection_timeout_does_not_try_other_api_versions():
    scanner = runners.DefenderScanner()
    session = MagicMock()
    session.get.side_effect = runners._requests.Timeout("Defender endpoint timed out")

    response, version, error = scanner._request_with_version_fallback(
        session,
        "subscriptions/sub/providers/Microsoft.Security/alerts",
        {},
        timeout=8,
        versions=("2022-01-01", "2021-06-01", "2020-01-01-preview"),
    )

    assert response is None
    assert version is None
    assert "timed out" in error
    session.get.assert_called_once()


def test_scan_timeout_budget_is_bounded():
    assert runners.DEFAULT_SCAN_TIMEOUT_SECONDS == 60


class _ConnectedRequest:
    async def is_disconnected(self):
        return False


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
    with patch.object(runners, "_run_command", return_value=_fake_run(stdout=json.dumps(report))):
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
    with patch.object(runners, "_run_command", return_value=_fake_run(stdout=json.dumps(report))):
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


def test_resolve_scanners_uses_profile_when_present():
    with patch.object(runners.DefenderScanner, "is_available", return_value=True):
        assert runners.resolve_scanners(None, "azure") == ["defender"]
    with patch.object(runners.DefenderScanner, "is_available", return_value=False):
        assert runners.resolve_scanners(None, "azure") == ["checkov", "trivy", "sonarqube"]
    assert runners.resolve_scanners(None, "local") == ["checkov", "trivy", "sonarqube"]
    # Explicit scanner list wins over profile.
    assert runners.resolve_scanners(["trivy"], "azure") == ["trivy"]
    # Unspecified profile defaults to local scanners.
    assert runners.resolve_scanners(None, None) == ["checkov", "trivy", "sonarqube"]
    with pytest.raises(ValueError, match="Unsupported scan profile: aws"):
        runners.resolve_scanners(None, "aws")


def test_azure_profile_runs_only_defender_without_resolving_a_local_path():
    with patch.object(runners.DefenderScanner, "is_available", return_value=True), patch.object(
        runners.DefenderScanner, "run", return_value=([], None)
    ) as run_defender, patch.object(runners.CheckovScanner, "run") as run_checkov, patch.object(
        runners.TrivyScanner, "run"
    ) as run_trivy, patch.object(runners.SonarQubeScanner, "run") as run_sonarqube, patch.object(
        runners, "_resolve_target", side_effect=AssertionError("Azure scan must not resolve a local path")
    ):
        findings, failures = runners.run_scanners("azure-subscription", scan_profile="azure")

    assert findings == []
    assert failures == []
    run_defender.assert_called_once_with("azure-subscription", timeout=300, scan_mode="full", cancel_event=None)
    run_checkov.assert_not_called()
    run_trivy.assert_not_called()
    run_sonarqube.assert_not_called()


def test_scan_request_rejects_removed_aws_account_profile():
    with pytest.raises(ValidationError):
        ScanRequest(target=".", scan_profile="aws")


def test_groq_model_is_currently_supported():
    from complisoc.backend.core.config import GROQ_MODEL, GROQ_MODEL_FALLBACKS

    retired = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}
    assert GROQ_MODEL not in retired, "GROQ_MODEL must not use a retired Groq model (e.g. llama-3.3-70b-versatile)"
    assert GROQ_MODEL in GROQ_MODEL_FALLBACKS, "GROQ_MODEL must be part of the supported fallback list"


def test_ingest_records_selected_scanner_without_findings(db_session):
    from complisoc.backend.scanners.ingestion import ingest_findings

    scan_run, _ = ingest_findings(
        db_session,
        target_environment="azure-demo",
        findings=[],
        scanner_failures=[],
        selected_scanners=["defender", "checkov", "trivy", "sonarqube"],
    )
    recorded = {e.scanner_name: e for e in scan_run.scanner_executions}
    # A cloud scanner that ran but produced nothing must still be recorded so the
    # UI can show it was consulted.
    assert recorded["defender"].status == "completed"
    assert "no findings" in (recorded["defender"].error_message or "").lower()
