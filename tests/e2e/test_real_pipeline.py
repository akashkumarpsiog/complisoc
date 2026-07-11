"""End-to-end pipeline test against real IaC changes (Week 8 gap #6).

For each target kind (Terraform, Kubernetes):

1. Create a temporary IaC file containing a *known bad pattern*.
2. Invoke the actual ``/api/v1/scans`` endpoint (via TestClient, so the
   real route + real pipeline are exercised).
3. Assert findings, control mappings, and report artifacts are created.
4. Clean up the temporary files (``tmp_path`` handles this automatically,
   plus an explicit removal guard).

The scanner and AI steps are replaced with deterministic doubles so the
test is reproducible and does not require network access or scanner
binaries. A *live* variant also exists that runs the real scanners
against ``scan_targets/`` and is skipped automatically when the binaries
are not installed.
"""
from __future__ import annotations

import pathlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api.main import app
from complisoc.backend.api.schemas import ScanRequest
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.models import ControlCatalog
from complisoc.backend.scanners import runners

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCAN_TARGETS = REPO_ROOT / "scan_targets"


def _seed_controls(db) -> None:
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


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = TestingSessionLocal()
    _seed_controls(db)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db.close()


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


def _make_run_scanners(kind: str):
    def _run(target, scanners=None, timeout=300):
        base = pathlib.Path(target)
        text = ""
        for f in base.rglob("*"):
            if f.is_file():
                try:
                    text += f.read_text(errors="ignore") + "\n"
                except Exception:
                    pass
        if kind == "terraform":
            return [
                {
                    "scanner_name": "checkov",
                    "scanner_finding_id": "E2E-TF-1",
                    "raw_json": {
                        "finding_type": "public_access iam permission",
                        "resource_type": "aws_s3_bucket",
                        "resource_identifier": "aws_s3_bucket.public_known_bad",
                        "severity": "high",
                        "title": "public access iam permission violation",
                        "description": "public_access iam permission misconfiguration in IaC",
                    },
                }
            ], []
        return [
            {
                "scanner_name": "checkov",
                "scanner_finding_id": "E2E-K8S-1",
                "raw_json": {
                    "finding_type": "privileged admin root runasuser",
                    "resource_type": "pod",
                    "resource_identifier": "pod.insecure_known_bad",
                    "severity": "high",
                    "title": "privileged admin root runasuser container",
                    "description": "privileged admin root runasuser misconfiguration in IaC",
                },
            }
        ], []

    return _run


@pytest.mark.parametrize("kind", ["terraform", "kubernetes"])
def test_e2e_real_pipeline_creates_findings_mappings_artifacts(client, tmp_path, kind):
    if kind == "terraform":
        target_dir = tmp_path / "terraform"
        target_dir.mkdir()
        tf_file = target_dir / "main.tf"
        tf_file.write_text(
            'resource "aws_s3_bucket" "bad" {\n'
            '  bucket = "public-bucket"\n'
            "}\n"
            "resource \"aws_s3_bucket_public_access_block\" \"bad\" {\n"
            "  block_public_acls = false\n"
            "  # KNOWN_BAD_TF: public access block disabled\n"
            "}\n",
            encoding="utf-8",
        )
        assert "KNOWN_BAD_TF" in tf_file.read_text(encoding="utf-8")
        expected_finding_id = "E2E-TF-1"
        expected_control = "A.5.15"
    else:
        target_dir = tmp_path / "kubernetes"
        target_dir.mkdir()
        yaml_file = target_dir / "deployment.yaml"
        yaml_file.write_text(
            "apiVersion: v1\n"
            "kind: Pod\n"
            "metadata:\n"
            "  name: insecure-pod\n"
            "spec:\n"
            "  containers:\n"
            "  - name: app\n"
            "    image: nginx:latest\n"
            "    # KNOWN_BAD_K8S: privileged container\n"
            "    securityContext:\n"
            "      privileged: true\n"
            "      runAsUser: 0\n",
            encoding="utf-8",
        )
        assert "KNOWN_BAD_K8S" in yaml_file.read_text(encoding="utf-8")
        expected_finding_id = "E2E-K8S-1"
        expected_control = "A.5.18"

    with patch(
        "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
    ) as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = _oracle_mapper
        MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier
        with patch("complisoc.backend.api.main.run_scanners", _make_run_scanners(kind)):
            response = client.post(
                "/api/v1/scans",
                json={"target": str(target_dir), "scanners": ["checkov"]},
            )

    assert response.status_code == 201, response.text
    scan_run_id = response.json()["id"]

    summary = client.get(f"/api/v1/scan-runs/{scan_run_id}/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["raw_findings"] >= 1, "no raw findings were created"
    assert body["mappings"] >= 1, "no control mappings were created"

    findings = client.get("/api/v1/findings")
    assert findings.status_code == 200
    assert len(findings.json()) >= 1

    mappings = client.get(f"/api/v1/mappings?scan_run_id={scan_run_id}")
    assert mappings.status_code == 200
    mapped_controls = {
        m["control_catalog_id"]: m["mapping_status"] for m in mappings.json()
    }
    assert mapped_controls, "no control mappings returned"
    assert any(
        status == "published" for status in mapped_controls.values()
    ), f"expected a published mapping for {expected_control}; got {mapped_controls}"

    eng = client.post("/api/v1/reports/engineering", json={"scan_run_id": scan_run_id})
    assert eng.status_code == 201
    assert eng.json()["content_hash"]
    assert pathlib.Path(eng.json()["content_path"]).exists(), "engineering report artifact missing"

    bundle = client.post("/api/v1/audit-bundles", json={"scan_run_id": scan_run_id})
    assert bundle.status_code == 201
    assert bundle.json()["checksum"]
    assert pathlib.Path(bundle.json()["bundle_path"]).exists(), "audit bundle artifact missing"


@pytest.mark.skipif(
    not (runners.TrivyScanner().is_available() or runners.CheckovScanner().is_available()),
    reason="trivy/checkov not installed; live E2E scan skipped",
)
@pytest.mark.parametrize("kind", ["terraform", "kubernetes"])
def test_e2e_live_real_scanners_against_scan_targets(client, kind):
    target_dir = SCAN_TARGETS / kind
    if not target_dir.exists():
        pytest.skip(f"scan_targets/{kind} not present")

    with patch(
        "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
    ) as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = _oracle_mapper
        MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier
        response = client.post(
            "/api/v1/scans",
            json={"target": str(target_dir), "scanners": ["trivy", "checkov"]},
        )

    assert response.status_code == 201, response.text
    scan_run_id = response.json()["id"]
    summary = client.get(f"/api/v1/scan-runs/{scan_run_id}/summary").json()
    assert summary["raw_findings"] >= 1, "live scanners produced no findings"
    assert summary["mappings"] >= 1, "live scan produced no mappings"
