from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from complisoc.backend.api.main import app
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
db = TestingSessionLocal()

from complisoc.backend.models import ControlCatalog
db.add_all([
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
])
db.commit()

def override_get_db():
    yield db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_groq_agreement_value_exposed_in_api():
    with patch("complisoc.backend.compliance.workflow.GeminiMapper") as MockMapper, patch("complisoc.backend.compliance.workflow.GroqVerifier") as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = lambda items: {
            items[0][0].id: [CandidateDecision(control_id=items[0][1][0].control_catalog.control_id, maps=True, confidence=0.95, rationale="High signal")],
        }
        MockVerifier.return_value.verify_batch.return_value = {
            1: VerificationDecision(result="agree", agreement_value=1.0, explanation="Correct"),
        }
        response = client.post(
            "/api/v1/scan-runs",
            json={
                "target_environment": "test",
                "findings": [{
                    "scanner_name": "checkov",
                    "scanner_finding_id": "CKV_1",
                    "raw_json": {
                        "finding_type": "iam public access permission",
                        "resource_type": "aws_iam_policy",
                        "resource_identifier": "aws_iam_policy.public_admin",
                        "severity": "high",
                        "title": "IAM policy allows public access permission",
                        "description": "iam public access permission public iam access permission",
                    },
                }],
            },
        )

    assert response.status_code == 201
    scan_run_id = response.json()["id"]

    mappings_resp = client.get(f"/api/v1/mappings?scan_run_id={scan_run_id}")
    assert mappings_resp.status_code == 200
    mappings = mappings_resp.json()
    assert len(mappings) == 1
    m = mappings[0]
    print("mapping keys:", list(m.keys()))
    assert "groq_agreement_value" in m, "groq_agreement_value missing from API response!"
    assert m["gemini_confidence"] == 0.95
    assert m["groq_agreement_value"] == 1.0
    assert m["final_confidence"] == 0.97
    assert m["verification_status"] == "agree"
    assert m["mapping_status"] == "published"

