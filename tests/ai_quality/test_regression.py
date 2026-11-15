"""Application regression checks with controlled provider responses.

These protect parser, normalization, workflow, and lineage behavior. They do
not measure live model stability; benchmark snapshots remain separate.
"""
from __future__ import annotations

import json

from complisoc.backend.compliance import mapping as mapping_module
from complisoc.backend.compliance.confidence import calculate_final_confidence, publication_status
from complisoc.backend.compliance.lineage import get_finding_lineage
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.normalization.normalizer import normalize_severity


def _process(db, finding, provider_response_clients, target="regression"):
    provider_response_clients.install_pipeline_clients()
    return process_scan_run(
        db,
        target_environment=target,
        findings=[finding],
    )


class TestWorkflowRegression:
    def test_control_selection_remains_catalog_bounded(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].control_catalog.control_id == "A.5.15"

    def test_mapping_confidence_remains_from_provider_response(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].gemini_confidence == 0.95

    def test_verification_result_remains_persisted(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].verification_status == "agree"

    def test_final_confidence_formula_remains_stable(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].final_confidence == calculate_final_confidence(0.95, 1.0)

    def test_publication_threshold_remains_enforced(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.state["confidence"] = 0.4
        result = process_scan_run(
            ai_quality_db,
            target_environment="regression-threshold",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == publication_status(0.64)
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_verifier_failure_remains_manual_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.verifier.verify_batch.side_effect = RuntimeError("verification unavailable")
        result = process_scan_run(
            ai_quality_db,
            target_environment="regression-verifier-failure",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_provider_failure_keeps_raw_and_normalized_finding(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.mapper.map_batch.side_effect = RuntimeError("mapping unavailable")
        result = process_scan_run(
            ai_quality_db,
            target_environment="regression-mapper-failure",
            findings=[ai_quality_finding()],
        )
        assert len(result["raw_findings"]) == 1
        assert len(result["normalized_findings"]) == 1

    def test_repeat_controlled_response_produces_same_mapping(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        first = _process(ai_quality_db, ai_quality_finding(1), provider_response_clients, "regression-repeat-1")
        second = _process(ai_quality_db, ai_quality_finding(2), provider_response_clients, "regression-repeat-2")
        assert first["mappings"][0].control_catalog.control_id == second["mappings"][0].control_catalog.control_id

    def test_raw_evidence_remains_unchanged(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        finding = ai_quality_finding()
        original = dict(finding["raw_json"])
        result = _process(ai_quality_db, finding, provider_response_clients, "regression-immutable-raw")
        assert result["raw_findings"][0].raw_json == original


class TestParserRegression:
    def test_fenced_gemini_json_remains_supported(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        response = provider_response_clients.state["gemini"]
        provider_response_clients.state["gemini"] = f"```json\n{response}\n```"
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "regression-fenced-json")
        assert result["mappings"][0].mapping_status == "published"

    def test_gemini_rejects_candidate_outside_controlled_catalog(
        self, ai_quality_db, ai_quality_finding, provider_response_clients, monkeypatch
    ):
        response = json.loads(provider_response_clients.state["gemini"])
        response["results"][0]["candidates"][0]["control_id"] = "A.9.1"
        provider_response_clients.state["gemini"] = json.dumps(response)
        monkeypatch.setattr(mapping_module, "call_with_retry", lambda fn, **_: fn())
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "regression-invalid-control")
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_severity_alias_remains_normalized(self):
        assert normalize_severity("moderate") == "medium"

    def test_null_severity_default_remains_supported(self, ai_quality_db, ai_quality_finding):
        finding = ai_quality_finding()
        finding["raw_json"]["severity"] = None
        result = process_scan_run(
            ai_quality_db,
            target_environment="regression-null-severity",
            findings=[finding],
        )
        assert result["normalized_findings"][0].severity == "medium"

    def test_lineage_keeps_mapping_explanation_association(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "regression-lineage")
        lineage = get_finding_lineage(ai_quality_db, result["normalized_findings"][0].id)
        assert lineage["mappings"][0]["verification_records"][0]["explanation"] == (
            "The control addresses the finding's access permissions."
        )

    def test_parser_error_is_not_converted_to_success(
        self, ai_quality_db, ai_quality_finding, provider_response_clients, monkeypatch
    ):
        provider_response_clients.state["gemini"] = "{invalid"
        monkeypatch.setattr(mapping_module, "call_with_retry", lambda fn, **_: fn())
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "regression-parser-error")
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_verification_metadata_keeps_mock_provider_identity(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "regression-mock-metadata")
        lineage = get_finding_lineage(ai_quality_db, result["normalized_findings"][0].id)
        assert lineage["mappings"][0]["verification_records"][0]["verification_model"] == "mock-groq"

    def test_numeric_string_confidence_remains_supported(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        response = json.loads(provider_response_clients.state["gemini"])
        response["results"][0]["candidates"][0]["confidence"] = "0.91"
        provider_response_clients.state["gemini"] = json.dumps(response)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "regression-string-confidence")
        assert result["mappings"][0].gemini_confidence == 0.91
