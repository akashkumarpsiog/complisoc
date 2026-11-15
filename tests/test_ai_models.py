"""Tests for AI model classes and pipeline error paths.

Covers GeminiMapper (mapping.py), GroqVerifier (verification.py), and
langchain_pipeline.py graceful-degradation paths — all with mocked AI clients.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.database.base import Base
from complisoc.backend.compliance.mapping import _finding_fingerprint
from complisoc.backend.models import (
    CandidateControl,
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ScanRun,
    ScannerExecution,
)


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

    db.add_all([
        ControlCatalog(
            framework_name="ISO/IEC 27001:2022 Annex A",
            framework_version="2022",
            control_id="A.5.15",
            control_family="Access Control",
            title="Access control",
            description="Limit access.",
            source_url="https://example.test/iso-a-5-15",
            active_status=True,
            scanner_signals=["public_access", "iam", "permission"],
            keywords=["access", "iam", "permission", "public"],
        ),
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()


def _make_finding(db, scanner_name="checkov", title="iam public access"):
    scan_run = db.query(ScanRun).first()
    if not scan_run:
        scan_run = ScanRun(target_environment="test", status="running")
        db.add(scan_run)
        db.flush()
    exec_ = ScannerExecution(scan_run_id=scan_run.id, scanner_name=scanner_name, status="completed")
    db.add(exec_)
    db.flush()
    raw = RawFinding(scanner_execution_id=exec_.id, scanner_finding_id="F1", scanner_name=scanner_name, raw_json={"finding_type": "iam public access permission", "resource_type": "aws_iam_policy", "resource_identifier": "aws_iam_policy.public_access", "severity": "high", "title": title, "description": "desc"})
    db.add(raw)
    db.flush()
    norm = NormalizedFinding(raw_finding_id=raw.id, scanner_name=scanner_name, finding_type="iam public access permission", resource_type="aws_iam_policy", resource_identifier="aws_iam_policy.public_access", severity="high", title=title, description="desc")
    db.add(norm)
    db.commit()
    return norm


def _make_candidate(db, finding, control=None):
    if control is None:
        control = db.query(ControlCatalog).first()
    candidate = CandidateControl(normalized_finding_id=finding.id, control_catalog_id=control.id, match_score=0.85)
    db.add(candidate)
    db.commit()
    return candidate


class TestGeminiMapper:
    def test_init_raises_without_api_key(self):
        from complisoc.backend.compliance.mapping import GeminiMapper

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", None):
            with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
                GeminiMapper()

    def test_map_batch_empty_returns_empty(self):
        from complisoc.backend.compliance.mapping import GeminiMapper

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ) as mock_genai:
            mock_genai.Client.return_value.models.generate_content.return_value.text = '{"results": []}'
            mapper = GeminiMapper()
            mapper.clear_cache()
            result = mapper.map_batch([])
            assert result == {}
            assert mock_genai.Client.call_args.kwargs == {"api_key": "fake"}
            assert mapper._timeout == 60.0

    def test_map_batch_with_valid_response(self, db_session):
        from complisoc.backend.compliance.mapping import GeminiMapper

        finding = _make_finding(db_session)
        candidate = _make_candidate(db_session, finding)
        control = candidate.control_catalog

        response_text = json.dumps({
            "results": [
                {
                    "finding_id": _finding_fingerprint(finding),
                    "candidates": [
                        {"control_id": control.control_id, "maps": True, "confidence": 0.95, "rationale": "strong match"}
                    ]
                }
            ]
        })

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ) as mock_genai:
            mock_genai.Client.return_value.models.generate_content.return_value.text = response_text
            mapper = GeminiMapper()
            mapper.clear_cache()
            result = mapper.map_batch([(finding, [candidate])])

        assert _finding_fingerprint(finding) in result
        decisions = result[_finding_fingerprint(finding)]
        assert len(decisions) == 1
        assert decisions[0].maps is True
        assert decisions[0].confidence == pytest.approx(0.95)

    def test_map_batch_filters_unknown_finding_ids(self, db_session):
        from complisoc.backend.compliance.mapping import GeminiMapper

        finding = _make_finding(db_session)
        candidate = _make_candidate(db_session, finding)
        control = candidate.control_catalog

        response_text = json.dumps({
            "results": [
                {"finding_id": 99999, "candidates": [{"control_id": control.control_id, "maps": True, "confidence": 0.9, "rationale": "x"}]}
            ]
        })

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ) as mock_genai, patch("complisoc.backend.core.retry.time.sleep"):
            mock_genai.Client.return_value.models.generate_content.return_value.text = response_text
            mapper = GeminiMapper()
            mapper.clear_cache()
            with pytest.raises(ValueError, match="no usable results"):
                mapper.map_batch([(finding, [candidate])])

    def test_map_batch_clamps_confidence(self, db_session):
        from complisoc.backend.compliance.mapping import GeminiMapper

        finding = _make_finding(db_session)
        candidate = _make_candidate(db_session, finding)
        control = candidate.control_catalog

        response_text = json.dumps({
            "results": [
                {
                    "finding_id": _finding_fingerprint(finding),
                    "candidates": [
                        {"control_id": control.control_id, "maps": False, "confidence": 5.0, "rationale": "weak"}
                    ]
                }
            ]
        })

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ) as mock_genai:
            mock_genai.Client.return_value.models.generate_content.return_value.text = response_text
            mapper = GeminiMapper()
            mapper.clear_cache()
            result = mapper.map_batch([(finding, [candidate])])

        decision = result[_finding_fingerprint(finding)][0]
        assert decision.confidence <= 0.99

    def test_map_one_with_valid_response(self, db_session):
        from complisoc.backend.compliance.mapping import GeminiMapper

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()

        response_text = json.dumps({"maps": True, "confidence": 0.87, "rationale": "good"})

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ) as mock_genai:
            mock_genai.Client.return_value.models.generate_content.return_value.text = response_text
            mapper = GeminiMapper()
            mapper.clear_cache()
            decision = mapper.map_one(finding, control)

        assert decision.maps is True
        assert decision.confidence == pytest.approx(0.87)

    def test_map_batch_no_results_raises(self, db_session):
        from complisoc.backend.compliance.mapping import GeminiMapper

        finding = _make_finding(db_session)
        candidate = _make_candidate(db_session, finding)

        response_text = '{"results": []}'

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ) as mock_genai, patch("complisoc.backend.core.retry.time.sleep"):
            mock_genai.Client.return_value.models.generate_content.return_value.text = response_text
            mapper = GeminiMapper()
            mapper.clear_cache()
            with pytest.raises(ValueError):
                mapper.map_batch([(finding, [candidate])])

    def test_map_batch_reports_original_error_when_all_chunks_fail(self, db_session):
        from complisoc.backend.compliance.mapping import GeminiMapper

        finding = _make_finding(db_session)
        candidate = _make_candidate(db_session, finding)

        with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.mapping.genai"
        ):
            mapper = GeminiMapper()
            mapper.clear_cache()
            mapper._map_one_chunk = MagicMock(side_effect=RuntimeError("provider quota exhausted"))
            # More than one chunk exercises the parallel chunk error handler.
            items = [(finding, [candidate])] * 26
            with pytest.raises(RuntimeError, match="provider quota exhausted"):
                mapper.map_batch(items)


class TestGroqVerifier:
    def test_init_raises_without_api_key(self):
        from complisoc.backend.compliance.verification import GroqVerifier

        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", None):
            with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
                GroqVerifier()

    def test_verify_batch_empty_returns_empty(self):
        from complisoc.backend.compliance.verification import GroqVerifier

        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq"
        ) as mock_groq:
            verifier = GroqVerifier()
            result = verifier.verify_batch([])
            assert result == {}
            assert mock_groq.call_args.kwargs == {"api_key": "fake"}
            assert verifier._timeout == 30.0

    def test_verify_batch_with_valid_response(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()

        response_text = json.dumps({
            "results": [{"ref": 1, "result": "agree", "explanation": "correct mapping"}]
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response_text))]
        )
        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier()
            item = PendingVerification(ref=1, finding=finding, control=control, confidence=0.95, rationale="test")
            result = verifier.verify_batch([item])

        assert 1 in result
        decision = result[1]
        assert decision.result == "agree"
        assert decision.agreement_value == 1.0
        assert mock_client.chat.completions.create.call_args.kwargs["max_completion_tokens"] == 4096

    def test_verify_batch_splits_only_when_groq_request_exceeds_tpm_limit(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        first_finding = _make_finding(db_session, title="first finding")
        second_finding = _make_finding(db_session, title="second finding")
        control = db_session.query(ControlCatalog).first()

        def response(ref):
            content = json.dumps({
                "results": [{"ref": ref, "result": "agree", "explanation": "correct mapping"}]
            })
            return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            RuntimeError(
                "Error code: 413: rate_limit_exceeded, tokens per minute: Limit 8000, Requested 8140, "
                "please reduce your message size."
            ),
            response(1),
            response(2),
        ]

        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier()
            items = [
                PendingVerification(ref=1, finding=first_finding, control=control, confidence=0.95, rationale="first"),
                PendingVerification(ref=2, finding=second_finding, control=control, confidence=0.90, rationale="second"),
            ]
            result = verifier.verify_batch(items)

        assert mock_client.chat.completions.create.call_count == 3
        assert set(result) == {1, 2}
        assert all(decision.result == "agree" for decision in result.values())

    def test_verify_batch_does_not_hide_tpm_error_for_single_mapping(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError(
            "rate_limit_exceeded, tokens per minute: Limit 8000, Requested 8140"
        )

        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier()
            item = PendingVerification(ref=1, finding=finding, control=control, confidence=0.95, rationale="test")
            with pytest.raises(RuntimeError, match="Requested 8140"):
                verifier.verify_batch([item])

    def test_verify_batch_falls_back_when_groq_reports_a_decommissioned_model(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()
        response_text = json.dumps({"results": [{"ref": 1, "result": "agree", "explanation": "correct mapping"}]})
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("The model `retired-model` has been decommissioned and is no longer supported."),
            MagicMock(choices=[MagicMock(message=MagicMock(content=response_text))]),
        ]

        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.GROQ_MODEL", "retired-model"
        ), patch("complisoc.backend.compliance.verification.GROQ_MODEL_FALLBACKS", ["openai/gpt-oss-20b"]), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier()
            item = PendingVerification(ref=1, finding=finding, control=control, confidence=0.95, rationale="test")
            result = verifier.verify_batch([item])

        assert result[1].model == "openai/gpt-oss-20b"
        assert [call.kwargs["model"] for call in mock_client.chat.completions.create.call_args_list] == [
            "retired-model", "openai/gpt-oss-20b"
        ]

    def test_verify_batch_filters_unknown_refs(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()

        response_text = json.dumps({"results": [{"ref": 99999, "result": "agree", "explanation": "x"}]})

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response_text))]
        )
        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ), patch("complisoc.backend.core.retry.time.sleep"):
            verifier = GroqVerifier()
            item = PendingVerification(ref=1, finding=finding, control=control, confidence=0.95, rationale="test")
            with pytest.raises(RuntimeError, match="Groq verification failed for all"):
                verifier.verify_batch([item])

    def test_verify_batch_retries_only_missing_refs_in_smaller_batches(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        first_finding = _make_finding(db_session, title="first finding")
        second_finding = _make_finding(db_session, title="second finding")
        control = db_session.query(ControlCatalog).first()
        partial = json.dumps({"results": [{"ref": 1, "result": "agree", "explanation": "ok"}]})
        retried = json.dumps({"results": [{"ref": 2, "result": "disagree", "explanation": "no"}]})
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=partial, finish_reason="stop"))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content=retried, finish_reason="stop"))]),
        ]
        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier(max_batch_size=2)
            items = [
                PendingVerification(ref=1, finding=first_finding, control=control, confidence=0.9, rationale="first"),
                PendingVerification(ref=2, finding=second_finding, control=control, confidence=0.9, rationale="second"),
            ]
            result = verifier.verify_batch(items)

        assert set(result) == {1, 2}
        assert result[1].result == "agree"
        assert result[2].result == "disagree"
        assert mock_client.chat.completions.create.call_count == 2

    def test_verify_batch_skips_invalid_results(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()

        response_text = json.dumps({"results": [{"ref": 1, "result": "maybe", "explanation": "x"}, {"ref": 2, "result": "agree", "explanation": "yes"}]})

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response_text))]
        )
        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ), patch("complisoc.backend.core.retry.time.sleep"):
            verifier = GroqVerifier()
            item = PendingVerification(ref=1, finding=finding, control=control, confidence=0.95, rationale="test")
            with pytest.raises(RuntimeError, match="Groq verification failed for all"):
                verifier.verify_batch([item])

    def test_verify_one_valid(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()
        response_text = json.dumps({"result": "agree", "explanation": "looks correct"})

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response_text))]
        )
        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier()
            decision = verifier.verify_one(finding, control, 0.95, "test rationale")

        assert decision.result == "agree"
        assert decision.agreement_value == 1.0

    def test_verify_one_invalid_result_raises(self, db_session):
        from complisoc.backend.compliance.verification import GroqVerifier

        finding = _make_finding(db_session)
        control = db_session.query(ControlCatalog).first()
        response_text = json.dumps({"result": "maybe", "explanation": "unclear"})

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response_text))]
        )
        with patch("complisoc.backend.compliance.verification.GROQ_API_KEY", "fake"), patch(
            "complisoc.backend.compliance.verification.Groq", return_value=mock_client
        ):
            verifier = GroqVerifier()
            with pytest.raises(ValueError, match="invalid result"):
                verifier.verify_one(finding, control, 0.95, "test")


class TestLangchainPipelineErrorPaths:
    def test_pipeline_handles_gemini_unavailable(self, db_session):
        """When GeminiMapper raises RuntimeError, pipeline falls back to manual review."""
        from complisoc.backend.compliance.workflow import process_scan_run

        findings = [
            {
                "scanner_name": "checkov",
                "scanner_finding_id": "ERR-1",
                "raw_json": {
                    "finding_type": "public_access iam permission",
                    "resource_type": "aws_iam_policy",
                    "resource_identifier": "aws_iam_policy.test",
                    "severity": "high",
                    "title": "iam public access permission",
                    "description": "desc",
                },
            }
        ]

        with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as MockMapper, patch(
            "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
        ) as MockVerifier:
            MockMapper.side_effect = RuntimeError("GEMINI_API_KEY is not configured; cannot perform AI mapping.")
            MockVerifier.side_effect = RuntimeError("GROQ_API_KEY is not configured; cannot perform AI verification.")
            result = process_scan_run(db_session, target_environment="err-test", findings=findings)

        assert result["scan_run"].status == "completed"
        assert db_session.query(NormalizedFinding).count() == 1
        mapping = db_session.query(ControlMapping).first()
        assert mapping.mapping_status == "manual_review"
        assert mapping.final_confidence is None
        assert mapping.gemini_confidence is None
        assert mapping.groq_agreement_value is None

    def test_pipeline_empty_findings(self, db_session):
        from complisoc.backend.compliance.workflow import process_scan_run

        result = process_scan_run(db_session, target_environment="empty-test", findings=[])

        assert result["scan_run"].status == "completed"
        assert len(result["raw_findings"]) == 0
