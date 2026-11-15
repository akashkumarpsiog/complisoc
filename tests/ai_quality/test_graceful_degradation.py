"""Provider-failure tests against the real persistence workflow."""
from __future__ import annotations

import json

from complisoc.backend.compliance import langchain_pipeline, mapping as mapping_module
from complisoc.backend.compliance import verification as verification_module
from complisoc.backend.compliance.mapping import CandidateDecision
from complisoc.backend.compliance.workflow import process_scan_run


def _run(db, finding, mocked_ai_services, target="ai-quality-degradation"):
    return process_scan_run(db, target_environment=target, findings=[finding])


class TestGracefulDegradation:
    def test_available_providers_publish_through_full_pipeline(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-available")
        assert result["mappings"][0].mapping_status == "published"
        assert result["mappings"][0].verification_status == "agree"

    def test_gemini_unavailable_queues_mapping_for_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services, monkeypatch
    ):
        def unavailable():
            raise RuntimeError("GEMINI_API_KEY is not configured")

        monkeypatch.setattr(langchain_pipeline, "GeminiMapper", unavailable)
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-no-gemini")
        assert result["mappings"][0].mapping_status == "manual_review"
        assert result["review_items"][0].review_reason_code == "AI_MAPPER_FAILURE"

    def test_gemini_timeout_does_not_persist_success(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.mapper.map_batch.side_effect = TimeoutError("provider timeout")
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-gemini-timeout")
        assert result["mappings"][0].mapping_status == "manual_review"
        assert result["mappings"][0].gemini_confidence is None

    def test_gemini_malformed_json_is_handled_by_pipeline(
        self, ai_quality_db, ai_quality_finding, provider_response_clients, monkeypatch
    ):
        provider_response_clients.state["gemini"] = "{invalid"
        provider_response_clients.install_pipeline_clients()
        monkeypatch.setattr(mapping_module, "call_with_retry", lambda fn, **_: fn())
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-gemini-json",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_partial_gemini_batch_keeps_missing_finding_in_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        def partial(items):
            finding, candidates = items[0]
            return {
                finding.id: [
                    CandidateDecision(
                        control_id=candidates[0].control_catalog.control_id,
                        maps=True,
                        confidence=0.95,
                        rationale="controlled provider response",
                    )
                ]
            }

        mocked_ai_services.mapper.map_batch.side_effect = partial
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-partial-gemini",
            findings=[ai_quality_finding(1), ai_quality_finding(2)],
        )
        assert sorted(mapping.mapping_status for mapping in result["mappings"]) == [
            "manual_review",
            "published",
        ]

    def test_empty_gemini_results_are_not_treated_as_success(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.mapper.map_batch.side_effect = None
        mocked_ai_services.mapper.map_batch.return_value = {}
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-empty-gemini")
        assert result["mappings"][0].mapping_status == "manual_review"
        assert result["review_items"][0].review_reason_code == "AI_MAPPER_FAILURE"

    def test_groq_unavailable_forces_manual_review_even_with_high_gemini_confidence(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services, monkeypatch
    ):
        def unavailable(*args, **kwargs):
            raise RuntimeError("GROQ_API_KEY is not configured")

        monkeypatch.setattr(langchain_pipeline, "GroqVerifier", unavailable)
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-no-groq")
        assert result["mappings"][0].gemini_confidence == 0.95
        assert result["mappings"][0].mapping_status == "manual_review"
        assert result["review_items"][0].review_reason_code == "AI_VERIFIER_FAILURE"

    def test_groq_timeout_forces_manual_review(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        mocked_ai_services.verifier.verify_batch.side_effect = TimeoutError("provider timeout")
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-groq-timeout")
        assert result["mappings"][0].mapping_status == "manual_review"
        assert result["mappings"][0].verification_status == "failed"

    def test_groq_malformed_json_forces_manual_review(
        self, ai_quality_db, ai_quality_finding, provider_response_clients, monkeypatch
    ):
        provider_response_clients.state["groq"] = "{invalid"
        provider_response_clients.install_pipeline_clients()
        monkeypatch.setattr(verification_module, "call_with_retry", lambda fn, **_: fn())
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-groq-json",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_groq_invalid_result_forces_manual_review(
        self, ai_quality_db, ai_quality_finding, provider_response_clients, monkeypatch
    ):
        response = json.loads(provider_response_clients.state["groq"])
        response["results"][0]["result"] = "unknown"
        provider_response_clients.state["groq"] = json.dumps(response)
        provider_response_clients.install_pipeline_clients()
        monkeypatch.setattr(verification_module, "call_with_retry", lambda fn, **_: fn())
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-groq-invalid-result",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == "manual_review"


class TestPartialResults:
    def test_missing_verifier_result_is_manual_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.verifier.verify_batch.side_effect = None
        mocked_ai_services.verifier.verify_batch.return_value = {}
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-no-verdict")
        assert result["mappings"][0].verification_status == "failed"
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_missing_verifier_result_creates_review_item(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.verifier.verify_batch.side_effect = None
        mocked_ai_services.verifier.verify_batch.return_value = {}
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-no-verdict-item")
        assert result["review_items"][0].review_reason_code == "AI_VERIFIER_FAILURE"

    def test_two_findings_keep_separate_mapping_rows(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-two-findings",
            findings=[ai_quality_finding(1), ai_quality_finding(2)],
        )
        assert len(result["mappings"]) == 2
        assert len({mapping.normalized_finding_id for mapping in result["mappings"]}) == 2

    def test_findings_remain_persisted_after_gemini_failure(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.mapper.map_batch.side_effect = RuntimeError("provider unavailable")
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-retain-finding")
        assert len(result["raw_findings"]) == 1
        assert len(result["normalized_findings"]) == 1

    def test_no_findings_does_not_invoke_provider(self, ai_quality_db, mocked_ai_services):
        result = process_scan_run(ai_quality_db, target_environment="degradation-empty-input", findings=[])
        assert result["scan_run"].status == "completed"
        mocked_ai_services.mapper.map_batch.assert_not_called()
        mocked_ai_services.verifier.verify_batch.assert_not_called()

    def test_scanner_failure_is_recorded_without_success_shaped_mapping(self, ai_quality_db):
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-scanner-failure",
            findings=[],
            scanner_failures=[{"scanner_name": "trivy", "error_message": "timeout"}],
        )
        assert result["scan_run"].status == "failed"
        assert result["mappings"] == []

    def test_both_providers_unavailable_preserve_finding_and_manual_review(
        self, ai_quality_db, ai_quality_finding, monkeypatch
    ):
        def unavailable(*args, **kwargs):
            raise RuntimeError("provider unavailable")

        monkeypatch.setattr(langchain_pipeline, "GeminiMapper", unavailable)
        monkeypatch.setattr(langchain_pipeline, "GroqVerifier", unavailable)
        result = process_scan_run(
            ai_quality_db,
            target_environment="degradation-both-unavailable",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == "manual_review"
        assert len(result["raw_findings"]) == 1

    def test_provider_failure_is_reported_in_pipeline_result(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.mapper.map_batch.side_effect = RuntimeError("provider unavailable")
        result = _run(ai_quality_db, ai_quality_finding(), mocked_ai_services, "degradation-reported-error")
        assert any("provider unavailable" in item["error_message"] for item in result["failures"])
