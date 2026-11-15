"""Shared test fixtures for AI quality tests.

Provides TestDataGenerator and other utilities as pytest fixtures.
"""
from __future__ import annotations

import os
import sys
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.ai_quality.generators.test_data_generator import TestDataGenerator
from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.api import main as api_main
from complisoc.backend.api.main import app
from complisoc.backend.compliance import langchain_pipeline
from complisoc.backend.compliance import mapping as mapping_module
from complisoc.backend.compliance import verification as verification_module
from complisoc.backend.compliance.mapping import CandidateDecision, _finding_fingerprint
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.database.session import get_db
from complisoc.backend.models import ControlCatalog


@pytest.fixture
def ai_quality_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = session_factory()
    benchmark_path = Path(__file__).resolve().parents[1] / "benchmark" / "gold_standard.json"
    catalog = json.loads(benchmark_path.read_text(encoding="utf-8"))
    db.add_all(
        [
            ControlCatalog(
                framework_name=catalog["framework"],
                framework_version=catalog["framework_version"],
                control_id=control["control_id"],
                control_family=control["control_family"],
                title=control["title"],
                description=control["description"],
                objective=control.get("objective"),
                evidence_examples=control.get("evidence_examples"),
                scanner_signals=control.get("scanner_signals"),
                keywords=control.get("keywords"),
                source_url=control["source_url"],
                active_status=True,
            )
            for control in catalog["controls"]
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def ai_quality_client(ai_quality_db):
    previous_bind = api_main.SessionLocal.kw.get("bind")
    api_main.SessionLocal.configure(bind=ai_quality_db.get_bind())

    def override_get_db():
        yield ai_quality_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        api_main.SessionLocal.configure(bind=previous_bind)


@pytest.fixture
def ai_quality_finding():
    def make_finding(index: int = 1) -> dict:
        return {
            "scanner_name": "checkov",
            "scanner_finding_id": f"AIQ-{index}",
            "raw_json": {
                "finding_type": "iam public access permission",
                "resource_type": "aws_iam_policy",
                "resource_identifier": f"aws_iam_policy.public_admin_{index}",
                "severity": "high",
                "title": "IAM policy allows public access permission",
                "description": "IAM policy grants public access without authorization.",
            },
        }

    return make_finding


@pytest.fixture
def mocked_ai_services(monkeypatch):
    state = {
        "maps": True,
        "confidence": 0.95,
        "rationale": "The finding describes public IAM access, matching the control objective.",
        "verification_result": "agree",
        "agreement_value": 1.0,
        "explanation": "The control addresses the finding's access permissions.",
    }

    mapper = MagicMock()
    verifier = MagicMock()

    def map_batch(items):
        return {
            _finding_fingerprint(finding): [
                CandidateDecision(
                    control_id=candidates[0].control_catalog.control_id,
                    maps=state["maps"],
                    confidence=state["confidence"],
                    rationale=state["rationale"],
                )
            ]
            for finding, candidates in items
        }

    def verify_batch(items):
        return {
            item.ref: VerificationDecision(
                result=state["verification_result"],
                agreement_value=state["agreement_value"],
                explanation=state["explanation"],
                model="mock-groq",
                prompt_version="test",
            )
            for item in items
        }

    mapper.map_batch.side_effect = map_batch
    verifier.verify_batch.side_effect = verify_batch
    monkeypatch.setattr(langchain_pipeline, "GeminiMapper", lambda: mapper)
    monkeypatch.setattr(langchain_pipeline, "GroqVerifier", lambda *args, **kwargs: verifier)
    return SimpleNamespace(state=state, mapper=mapper, verifier=verifier)


@pytest.fixture
def provider_response_clients(monkeypatch):
    state = {
        "gemini": json.dumps(
            {
                "results": [
                    {
                        "finding_id": 1,
                        "candidates": [
                            {
                                "control_id": "A.5.15",
                                "maps": True,
                                "confidence": 0.95,
                                "rationale": "The finding identifies public IAM access.",
                            }
                        ],
                    }
                ]
            }
        ),
        "groq": json.dumps(
            {
                "results": [
                    {
                        "ref": 1,
                        "result": "agree",
                        "explanation": "The control addresses the finding's access permissions.",
                    }
                ]
            }
        ),
    }

    def gemini_response(**kwargs):
        text = state["gemini"]
        prompt = kwargs.get("contents", "")
        fingerprints = re.findall(r"FINDING fingerprint=([0-9a-f]+)", prompt)
        if fingerprints:
            try:
                payload = extract_json(text)
            except (TypeError, json.JSONDecodeError):
                return SimpleNamespace(text=text)
            template_results = payload.get("results", [])
            if len(fingerprints) > len(template_results):
                template = template_results[0] if template_results else {}
                payload["results"] = [dict(template) for _ in fingerprints]
            for item, fingerprint in zip(payload.get("results", []), fingerprints):
                item["finding_id"] = fingerprint
            rewritten = json.dumps(payload)
            text = f"```json\n{rewritten}\n```" if text.lstrip().startswith("```") else rewritten
        return SimpleNamespace(text=text)

    gemini_call = MagicMock(side_effect=gemini_response)
    groq_call = MagicMock(
        side_effect=lambda **_: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=state["groq"])
                )
            ]
        )
    )
    gemini_client = SimpleNamespace(models=SimpleNamespace(generate_content=gemini_call))
    groq_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=groq_call))
    )

    monkeypatch.setattr(mapping_module, "GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setattr(mapping_module.genai, "Client", lambda **_: gemini_client)
    monkeypatch.setattr(verification_module, "GROQ_API_KEY", "unit-test-key")
    monkeypatch.setattr(verification_module, "GROQ_MODEL", "mock-groq")
    monkeypatch.setattr(verification_module, "Groq", lambda **_: groq_client)

    mapper = mapping_module.GeminiMapper()
    mapper.clear_cache()
    verifier = verification_module.GroqVerifier()

    def install_pipeline_clients():
        monkeypatch.setattr(langchain_pipeline, "GeminiMapper", lambda: mapper)
        monkeypatch.setattr(langchain_pipeline, "GroqVerifier", lambda *args, **kwargs: verifier)

    return SimpleNamespace(
        state=state,
        mapper=mapper,
        verifier=verifier,
        gemini_call=gemini_call,
        groq_call=groq_call,
        install_pipeline_clients=install_pipeline_clients,
    )


@pytest.fixture
def data_generator() -> TestDataGenerator:
    """Provide a deterministic TestDataGenerator."""
    return TestDataGenerator(seed=42)


@pytest.fixture
def sample_findings(data_generator: TestDataGenerator) -> list:
    """Generate a batch of sample findings."""
    return data_generator.generate_batch(10)


@pytest.fixture
def sample_controls(data_generator: TestDataGenerator) -> list:
    """Generate a batch of sample controls."""
    return [data_generator.generate_control() for _ in range(5)]


@pytest.fixture
def sample_finding_control_pairs(data_generator: TestDataGenerator) -> list:
    """Generate matching finding-control pairs."""
    return [data_generator.generate_finding_control_pair() for _ in range(5)]


@pytest.fixture
def adversarial_findings(data_generator: TestDataGenerator) -> list:
    """Generate adversarial test findings."""
    return [data_generator.generate_adversarial_finding() for _ in range(10)]


@pytest.fixture
def mock_gemini_response() -> dict:
    """Provide a mock Gemini API response."""
    return {
        "results": [
            {
                "finding_id": 1,
                "candidates": [
                    {"control_id": "A.5.15", "maps": True, "confidence": 0.95, "rationale": "direct match"},
                    {"control_id": "A.8.13", "maps": False, "confidence": 0.2, "rationale": "unrelated"},
                ],
            }
        ]
    }


@pytest.fixture
def mock_groq_response() -> dict:
    """Provide a mock Groq API response."""
    return {
        "results": [
            {"ref": 1, "result": "agree", "explanation": "correct mapping"},
        ]
    }
