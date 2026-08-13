"""Tests for scenario-based PDF report generation (Week 13).

Validates that:
- Each scenario (container, IaC, code-security) generates a PDF artifact.
- All referenced control IDs exist in the control catalog.
- Findings are present for each scenario.
- No duplicate or mismatched control references occur.
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
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.models import ControlCatalog, ControlMapping
from complisoc.backend.reporting.reports import generate_scenario_report, _deterministic_narrative


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()

    db.add_all([
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.5.15",
            control_family="Access Control",
            title="Access control",
            description="Limit access to information.",
            source_url="https://example.test/iso-a-5-15",
            active_status=True,
            scanner_signals=["public_access", "iam", "permission"],
            keywords=["access", "iam", "permission", "public"],
        ),
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.8.8",
            control_family="Secure Development",
            title="Management of technical vulnerabilities",
            description="Technical vulnerabilities are identified and remediated.",
            source_url="https://example.test/iso-a-8-8",
            active_status=True,
            scanner_signals=["dependency", "vulnerability", "patch"],
            keywords=["dependency", "vulnerability", "patch", "cve"],
        ),
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.9.1",
            control_family="Logging",
            title="Logging and monitoring",
            description="Activity logging and continuous monitoring.",
            source_url="https://example.test/iso-a-9-1",
            active_status=True,
            scanner_signals=["network", "firewall", "ingress"],
            keywords=["logging", "audit", "trail"],
        ),
    ])
    db.commit()

    yield db
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


def _seed_scan_run(db, scanner_name, finding_id, title, severity="high"):
    from complisoc.backend.compliance.workflow import process_scan_run

    findings = [
        {
            "scanner_name": scanner_name,
            "scanner_finding_id": finding_id,
            "raw_json": {
                "finding_type": "public_access iam permission",
                "resource_type": "test_resource",
                "resource_identifier": f"resource_{finding_id}",
                "severity": severity,
                "title": title,
                "description": f"description for {title}",
            },
        }
    ]

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
        result = process_scan_run(
            db,
            target_environment="scenario-test",
            findings=findings,
        )

    return result["scan_run"].id


def _mock_narrative():
    return patch(
        "complisoc.backend.reporting.reports._generate_report_narrative",
        side_effect=_deterministic_narrative,
    )


class TestScenarioReports:
    SCENARIOS = [
        ("container", "trivy", "GOLD-CONT-1", "Container vulnerability found"),
        ("iac", "checkov", "GOLD-IAC-1", "IaC misconfiguration found"),
        ("code-security", "sonarqube", "GOLD-CODE-1", "Code security issue found"),
    ]

    @pytest.mark.parametrize("scenario,scanner,finding_id,title", SCENARIOS)
    def test_scenario_report_generates_pdf_and_valid_catalog_ids(self, db_session, client, scenario, scanner, finding_id, title):
        scan_run_id = _seed_scan_run(db_session, scanner, finding_id, title)

        with _mock_narrative():
            report = generate_scenario_report(db_session, scan_run_id=scan_run_id, scenario=scenario)

        assert report.report_type == f"scenario:{scenario}"
        assert report.content_path is not None
        assert report.content_hash is not None
        assert Path(report.content_path).exists(), "PDF artifact must exist on disk"

    @pytest.mark.parametrize("scenario,scanner,finding_id,title", SCENARIOS)
    def test_scenario_report_via_api(self, client, db_session, scenario, scanner, finding_id, title):
        scan_run_id = _seed_scan_run(db_session, scanner, finding_id, title)

        with _mock_narrative():
            resp = client.post("/api/v1/reports/scenario", json={"scan_run_id": scan_run_id, "scenario": scenario})

        assert resp.status_code == 201
        body = resp.json()
        assert body["report_type"] == f"scenario:{scenario}"
        assert body["content_path"].endswith(".pdf")
        assert Path(body["content_path"]).exists()

    def test_scenario_report_rejects_invalid_scenario(self, db_session, client):
        scan_run_id = _seed_scan_run(db_session, "trivy", "GOLD-VAL-1", "Test finding")

        resp = client.post(
            "/api/v1/reports/scenario",
            json={"scan_run_id": scan_run_id, "scenario": "invalid"},
        )
        assert resp.status_code == 400

    def test_scenario_report_no_findings_returns_error(self, db_session, client):
        scan_run_id = _seed_scan_run(db_session, "checkov", "GOLD-IAC-2", "IaC finding")

        with _mock_narrative():
            resp = client.post(
                "/api/v1/reports/scenario",
                json={"scan_run_id": scan_run_id, "scenario": "container"},
            )
        assert resp.status_code == 400

    def test_all_referenced_control_ids_exist_in_catalog(self, db_session):
        from complisoc.backend.compliance.workflow import process_scan_run

        findings = [
            {
                "scanner_name": "trivy",
                "scanner_finding_id": "GOLD-CONT-BATCH-1",
                "raw_json": {
                    "finding_type": "public_access iam permission",
                    "resource_type": "pkg",
                    "resource_identifier": "pkg1",
                    "severity": "high",
                    "title": "container vuln 1",
                    "description": "desc",
                },
            },
            {
                "scanner_name": "trivy",
                "scanner_finding_id": "GOLD-CONT-BATCH-2",
                "raw_json": {
                    "finding_type": "public_access iam permission",
                    "resource_type": "pkg",
                    "resource_identifier": "pkg2",
                    "severity": "critical",
                    "title": "container vuln 2",
                    "description": "desc2",
                },
            },
        ]

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
                ],
                items[1][0].id: [
                    CandidateDecision(
                        control_id=items[1][1][0].control_catalog.control_id,
                        maps=True,
                        confidence=0.95,
                        rationale="oracle",
                    )
                ],
            }
            MockVerifier.return_value.verify_batch.return_value = {
                1: VerificationDecision(result="agree", agreement_value=1.0, explanation="ok"),
                2: VerificationDecision(result="agree", agreement_value=1.0, explanation="ok"),
            }
            result = process_scan_run(
                db_session,
                target_environment="scenario-batch",
                findings=findings,
            )

        scan_run_id = result["scan_run"].id
        with _mock_narrative():
            report = generate_scenario_report(db_session, scan_run_id=scan_run_id, scenario="container")

        mappings = (
            db_session.query(ControlMapping)
            .join(ControlMapping.normalized_finding)
            .join(ControlCatalog, ControlMapping.control_catalog_id == ControlCatalog.id)
            .all()
        )
        referenced_catalog_ids = {m.control_catalog_id for m in mappings}
        all_catalog_ids = {c.id for c in db_session.query(ControlCatalog.id).all()}
        assert referenced_catalog_ids.issubset(all_catalog_ids), "orphaned control catalog references"

    def test_scenario_report_no_duplicate_control_references(self, db_session):
        scan_run_id = _seed_scan_run(db_session, "trivy", "GOLD-DUP-1", "Duplicate check")

        with _mock_narrative():
            report = generate_scenario_report(db_session, scan_run_id=scan_run_id, scenario="container")

        json_path = Path(report.content_path).parent
        json_files = list(json_path.glob(f"scenario-container-scan-{scan_run_id}.json"))

        all_control_ids = []
        for jf in json_files:
            data = json.loads(jf.read_text())
            all_control_ids.extend(data["control_ids_referenced"])
        assert len(all_control_ids) == len(set(all_control_ids)), "duplicate control IDs in scenario report"