"""Tests for parsing and associating explanations with audit lineage.

These use controlled provider responses and do not assess live explanation
relevance, evidentiary grounding, or semantic consistency.
"""
from __future__ import annotations

from complisoc.backend.compliance.lineage import get_finding_lineage
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.models import VerificationRecord


def _process(db, finding, provider_response_clients, target="explanation"):
    provider_response_clients.install_pipeline_clients()
    result = process_scan_run(
        db,
        target_environment=target,
        findings=[finding],
    )
    normalized = result["normalized_findings"][0]
    return result, normalized, get_finding_lineage(db, normalized.id)


class TestExplanationAssociation:
    def test_mapper_rationale_is_parsed_and_persisted(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["mappings"][0]["rationale"] == "The finding identifies public IAM access."

    def test_rationale_belongs_to_selected_control_mapping(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        mapping = lineage["mappings"][0]
        assert mapping["control_id"] == "A.5.15"
        assert mapping["rationale"]

    def test_verifier_explanation_is_parsed_and_persisted(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["mappings"][0]["verification_records"][0]["explanation"] == (
            "The control addresses the finding's access permissions."
        )

    def test_verification_record_references_its_mapping(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        mapping_id = result["mappings"][0].id
        record = ai_quality_db.query(VerificationRecord).filter_by(control_mapping_id=mapping_id).one()
        assert record.control_mapping_id == lineage["mappings"][0]["mapping_id"]

    def test_rationale_and_verification_explanation_remain_separate(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        mapping = lineage["mappings"][0]
        assert mapping["rationale"] != mapping["verification_records"][0]["explanation"]

    def test_lineage_includes_original_finding_evidence(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, normalized, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["raw_finding"]["raw_json"]["title"] == normalized.title

    def test_lineage_includes_normalized_finding(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        _, normalized, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["normalized_finding"]["id"] == normalized.id
        assert lineage["normalized_finding"]["severity"] == "high"

    def test_lineage_contains_control_title_and_id(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        mapping = lineage["mappings"][0]
        assert (mapping["control_id"], mapping["control_title"]) == ("A.5.15", "Access Control")

    def test_verification_result_and_explanation_are_returned_together(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        verification = lineage["mappings"][0]["verification_records"][0]
        assert verification["result"] == "agree"
        assert verification["explanation"]

    def test_mapping_confidence_is_available_in_lineage(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        mapping = lineage["mappings"][0]
        assert mapping["gemini_confidence"] == 0.95
        assert mapping["final_confidence"] == 0.97

    def test_provider_models_are_recorded_in_lineage(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        verification = lineage["mappings"][0]["verification_records"][0]
        assert verification["verification_model"] == "mock-groq"

    def test_lineage_has_scan_run_and_raw_finding_references(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["scan_run"]["id"] is not None
        assert lineage["raw_finding"]["scanner_finding_id"] == "AIQ-1"


class TestExplanationAuditability:
    def test_mapping_creation_timestamp_is_available(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["mappings"][0]["created_at"]

    def test_verification_timestamp_is_available(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["mappings"][0]["verification_records"][0]["timestamp"]

    def test_mapping_prompt_version_is_recorded(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result, _, _ = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].prompt_version

    def test_exactly_one_verification_record_is_linked(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert len(lineage["mappings"][0]["verification_records"]) == 1

    def test_rationale_is_not_attached_to_unrelated_finding(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        first = ai_quality_finding(1)
        second = ai_quality_finding(2)
        provider_response_clients.install_pipeline_clients()
        result = process_scan_run(
            ai_quality_db,
            target_environment="explanation-two-findings",
            findings=[first, second],
        )
        first_lineage = get_finding_lineage(ai_quality_db, result["normalized_findings"][0].id)
        second_lineage = get_finding_lineage(ai_quality_db, result["normalized_findings"][1].id)
        assert first_lineage["mappings"][0]["mapping_id"] != second_lineage["mappings"][0]["mapping_id"]

    def test_missing_rationale_parser_fallback_is_traceable(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        provider_response_clients.state["gemini"] = (
            '{"results":[{"finding_id":1,"candidates":[{"control_id":"A.5.15",'
            '"maps":true,"confidence":0.95}]}]}'
        )
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "explanation-no-rationale")
        assert lineage["mappings"][0]["rationale"] == "No rationale provided by model."

    def test_missing_verification_explanation_parser_fallback_is_traceable(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        provider_response_clients.state["groq"] = (
            '{"results":[{"ref":1,"result":"agree"}]}'
        )
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "explanation-no-verifier-text")
        assert lineage["mappings"][0]["verification_records"][0]["explanation"] == (
            "No explanation provided by model."
        )

    def test_low_confidence_mapping_remains_explainable_in_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.state.update(confidence=0.4)
        result = process_scan_run(
            ai_quality_db,
            target_environment="explanation-manual-review",
            findings=[ai_quality_finding()],
        )
        lineage = get_finding_lineage(ai_quality_db, result["normalized_findings"][0].id)
        assert lineage["mappings"][0]["mapping_status"] == "manual_review"
        assert lineage["mappings"][0]["rationale"]

    def test_raw_evidence_is_unchanged_after_mapping(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        finding = ai_quality_finding()
        original = dict(finding["raw_json"])
        result, _, _ = _process(ai_quality_db, finding, provider_response_clients)
        assert result["raw_findings"][0].raw_json == original

    def test_lineage_query_is_read_only(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result, normalized, _ = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        before = result["mappings"][0].rationale
        get_finding_lineage(ai_quality_db, normalized.id)
        ai_quality_db.expire_all()
        assert ai_quality_db.query(type(result["mappings"][0])).one().rationale == before

    def test_lineage_exposes_one_mapping_for_one_test_finding(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert len(lineage["mappings"]) == 1

    def test_lineage_does_not_replace_provider_names_with_claimed_live_models(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _, _, lineage = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert lineage["mappings"][0]["verification_records"][0]["verification_model"] == "mock-groq"
