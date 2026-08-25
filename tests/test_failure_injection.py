"""Failure-injection tests.

Proves the pipeline handles AI provider failures, malformed input, and
database errors without silent data loss or incorrect publication.

These tests are aligned with the architecture's failure-handling invariants:

* AI failure -> finding retained, mapping = manual_review, no data loss
* Verification failure -> manual review, no automatic publication
* Malformed AI response -> validation rejects it, invalid mapping never published
* Database failure -> pipeline fails explicitly, no silent success
* Malformed scanner output -> normalization rejects/logs it, pipeline continues safely
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.compliance.langchain_pipeline import run_pipeline
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.verification import VerificationDecision
from complisoc.backend.database.base import Base
from complisoc.backend.models import (
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ReviewQueueItem,
    ScanRun,
    ScannerExecution,
    VerificationRecord,
)


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return engine


def _session(engine):
    Local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return Local()


def seed_controls(db):
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
        ]
    )
    db.commit()


def _finding():
    return {
        "scanner_name": "checkov",
        "scanner_finding_id": "CKV_TEST_1",
        "raw_json": {
            "finding_type": "iam",
            "resource_type": "aws_iam_policy",
            "resource_identifier": "aws_iam_policy.test",
            "severity": "high",
            "title": "Test finding",
            "description": "Test description",
        },
    }


def _oracle_mapper(items):
    return {
        items[0][0].id: [
            CandidateDecision(
                control_id=items[0][1][0].control_catalog.control_id,
                maps=True,
                confidence=0.95,
                rationale="oracle",
            )
        ]
    }


def _oracle_verifier(items):
    return {
        item.ref: VerificationDecision(result="agree", agreement_value=1.0, explanation="oracle")
        for item in items
    }


class TestGeminiUnavailable:
    def test_gemini_unavailable_queues_manual_review_no_data_loss(self):
        engine = _engine()
        db = _session(engine)
        seed_controls(db)
        try:
            with patch(
                "complisoc.backend.compliance.langchain_pipeline.GeminiMapper",
                side_effect=RuntimeError("GEMINI_API_KEY is not configured"),
            ), patch(
                "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
            ) as MockVerifier:
                MockVerifier.return_value.verify_batch.return_value = {}
                result = run_pipeline(db, target_environment="test", findings=[_finding()])
            assert result["scan_run"].status == "completed"
            assert len(result["mappings"]) == 1
            mapping = result["mappings"][0]
            assert mapping.mapping_status == "manual_review"
            assert mapping.gemini_confidence is None
            assert len(result["review_items"]) == 1
            assert result["review_items"][0].review_reason_code == "AI_MAPPER_FAILURE"
        finally:
            db.close()
            engine.dispose()


class TestGroqUnavailable:
    def test_groq_unavailable_prevents_auto_publication(self):
        engine = _engine()
        db = _session(engine)
        seed_controls(db)
        try:
            def low_confidence_mapper(items):
                return {
                    items[0][0].id: [
                        CandidateDecision(
                            control_id=items[0][1][0].control_catalog.control_id,
                            maps=True,
                            confidence=0.5,
                            rationale="oracle",
                        )
                    ]
                }

            with patch(
                "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
            ) as MockMapper, patch(
                "complisoc.backend.compliance.langchain_pipeline.GroqVerifier",
                side_effect=RuntimeError("GROQ_API_KEY is not configured"),
            ):
                MockMapper.return_value.map_batch.side_effect = low_confidence_mapper
                result = run_pipeline(db, target_environment="test", findings=[_finding()])
            assert len(result["mappings"]) == 1
            mapping = result["mappings"][0]
            assert mapping.mapping_status == "manual_review"
            assert mapping.groq_agreement_value == 0.0
            assert mapping.verification_status == "failed"
            assert len(result["review_items"]) == 1
            assert result["review_items"][0].review_reason_code == "AI_VERIFIER_FAILURE"
        finally:
            db.close()
            engine.dispose()


class TestMalformedGeminiResponse:
    def test_empty_batch_decision_queues_manual_review(self):
        engine = _engine()
        db = _session(engine)
        seed_controls(db)
        try:
            with patch(
                "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
            ) as MockMapper, patch(
                "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
            ) as MockVerifier:
                MockMapper.return_value.map_batch.return_value = {}
                MockVerifier.return_value.verify_batch.return_value = {}
                result = run_pipeline(db, target_environment="test", findings=[_finding()])
            assert len(result["mappings"]) == 1
            mapping = result["mappings"][0]
            assert mapping.mapping_status == "manual_review"
            assert mapping.gemini_confidence is None
            assert "Gemini batch mapping returned no result" in (mapping.rationale or "")
        finally:
            db.close()
            engine.dispose()


class TestDatabaseFailure:
    def test_pipeline_fails_explicitly_on_db_commit_error(self):
        engine = _engine()
        db = _session(engine)
        seed_controls(db)
        try:
            original_commit = db.commit
            def failing_commit():
                raise RuntimeError("database is read-only")

            db.commit = failing_commit
            with patch(
                "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
            ) as MockMapper, patch(
                "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
            ) as MockVerifier:
                MockMapper.return_value.map_batch.side_effect = _oracle_mapper
                MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier
                with pytest.raises(RuntimeError, match="database is read-only"):
                    run_pipeline(db, target_environment="test", findings=[_finding()])
        finally:
            db.commit = original_commit
            db.close()
            engine.dispose()


class TestMalformedScannerOutput:
    def test_normalization_rejects_incomplete_finding_and_pipeline_continues(self):
        engine = _engine()
        db = _session(engine)
        seed_controls(db)
        try:
            incomplete = {
                "scanner_name": "checkov",
                "scanner_finding_id": "CKV_TEST_INCOMPLETE",
                "raw_json": {
                    "finding_type": "iam",
                    "resource_type": "aws_iam_policy",
                    "resource_identifier": "aws_iam_policy.test",
                    "severity": "high",
                },
            }
            good = _finding()
            with patch(
                "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
            ) as MockMapper, patch(
                "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
            ) as MockVerifier:
                MockMapper.return_value.map_batch.side_effect = _oracle_mapper
                MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier
                result = run_pipeline(db, target_environment="test", findings=[incomplete, good])
            assert len(result["mappings"]) == 1
            mapping = result["mappings"][0]
            assert mapping.normalized_finding.raw_finding.scanner_finding_id == good["scanner_finding_id"]
            assert mapping.mapping_status == "published"
            assert len(result["failures"]) == 1
            assert "raw finding requires" in result["failures"][0]["error"]
        finally:
            db.close()
            engine.dispose()
