"""Mocked workflow checks, not measurements of Gemini/Groq model bias.

An independently labeled and representative fairness dataset does not exist
in the repository. These tests exercise Complisoc's real mapping pipeline
with controlled provider decisions; live bias claims remain unsupported.
"""
from __future__ import annotations

from complisoc.backend.models import VerificationRecord
from complisoc.backend.compliance.workflow import process_scan_run

_CATEGORY_FINDINGS = {
    "access_control": ("A.5.15", "IAM public access permission"),
    "encryption": ("A.8.24", "unencrypted data encryption key rotation"),
    "audit": ("A.8.15", "audit logging missing security event records"),
    "monitoring": ("A.8.16", "monitoring alert anomaly detection"),
    "network": ("A.8.20", "network firewall open ingress port"),
    "backup": ("A.8.13", "backup restore failover data recovery"),
    "configuration": ("A.8.9", "configuration baseline drift management"),
}


def _process(
    db,
    make_finding,
    mocked_ai_services,
    category: str = "access_control",
    index: int = 1,
):
    control_id, description = _CATEGORY_FINDINGS[category]
    finding = make_finding(index)
    finding["raw_json"].update(
        {
            "finding_type": category,
            "title": description,
            "description": description,
        }
    )
    result = process_scan_run(
        db,
        target_environment=f"ai-quality-{category}-{index}",
        findings=[finding],
    )
    assert result["scan_run"].status == "completed"
    assert len(result["mappings"]) == 1
    mapping = result["mappings"][0]
    assert mapping.control_catalog.control_id == control_id
    return result, mapping


class TestSelectionBias:
    def test_access_control_input_traverses_real_pipeline(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.mapping_status == "published"

    def test_encryption_input_uses_catalog_candidate(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services, "encryption")
        assert mapping.mapping_status == "published"

    def test_logging_input_uses_2022_control(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services, "audit")
        assert mapping.control_catalog.control_id == "A.8.15"

    def test_monitoring_input_uses_monitoring_control(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services, "monitoring")
        assert mapping.control_catalog.control_id == "A.8.16"

    def test_network_input_uses_network_control(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services, "network")
        assert mapping.control_catalog.control_id == "A.8.20"

    def test_backup_input_uses_backup_control(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services, "backup")
        assert mapping.control_catalog.control_id == "A.8.13"

    def test_configuration_input_uses_configuration_control(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services, "configuration")
        assert mapping.control_catalog.control_id == "A.8.9"


class TestControlledProviderProcessing:
    def test_provider_mapping_response_is_processed(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        mocked_ai_services.mapper.map_batch.assert_called_once()
        assert mapping.gemini_confidence == 0.95

    def test_provider_verification_response_is_processed(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        mocked_ai_services.verifier.verify_batch.assert_called_once()
        assert mapping.verification_status == "agree"

    def test_lower_mocked_confidence_routes_to_manual_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.state["confidence"] = 0.4
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.mapping_status == "manual_review"

    def test_verifier_disagreement_routes_to_manual_review(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.state.update(verification_result="disagree", agreement_value=0.0)
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.verification_status == "disagree"
        assert mapping.mapping_status == "manual_review"

    def test_rationale_is_associated_with_persisted_mapping(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        rationale = "The finding identifies public IAM access."
        mocked_ai_services.state["rationale"] = rationale
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.rationale == rationale

    def test_verifier_explanation_is_persisted_as_evidence(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        explanation = "The access control addresses the finding's public permissions."
        mocked_ai_services.state["explanation"] = explanation
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        record = ai_quality_db.query(VerificationRecord).filter_by(control_mapping_id=mapping.id).one()
        assert record.explanation == explanation

    def test_mapping_keeps_finding_lineage(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        result, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.normalized_finding_id == result["normalized_findings"][0].id

    def test_raw_finding_is_preserved(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        result, _ = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        raw = result["raw_findings"][0]
        assert raw.raw_json["description"] == "IAM public access permission"

    def test_provider_models_are_recorded(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.mapping_model
        record = ai_quality_db.query(VerificationRecord).filter_by(control_mapping_id=mapping.id).one()
        assert record.verification_model == "mock-groq"

    def test_distinct_findings_are_not_collapsed(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        first = ai_quality_finding(1)
        second = ai_quality_finding(2)
        result = process_scan_run(
            ai_quality_db,
            target_environment="ai-quality-distinct",
            findings=[first, second],
        )
        assert len(result["raw_findings"]) == 2
        assert len(result["normalized_findings"]) == 2

    def test_severity_survives_normalization(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        result, _ = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert result["normalized_findings"][0].severity == "high"

    def test_control_family_and_identifier_are_persisted(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.control_catalog.control_id == "A.5.15"
        assert mapping.control_catalog.title == "Access Control"

    def test_confidence_uses_provider_outputs(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        result, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert mapping.final_confidence == 0.97
        assert result["scan_run"].status == "completed"

    def test_low_confidence_creates_review_queue_item(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        mocked_ai_services.state["confidence"] = 0.4
        result, _ = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        assert len(result["review_items"]) == 1

    def test_mapping_and_verification_records_share_mapping_id(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        record = ai_quality_db.query(VerificationRecord).filter_by(control_mapping_id=mapping.id).one()
        assert record.control_mapping_id == mapping.id

    def test_mocked_verification_result_is_not_claimed_as_live(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, mapping = _process(ai_quality_db, ai_quality_finding, mocked_ai_services)
        record = ai_quality_db.query(VerificationRecord).filter_by(control_mapping_id=mapping.id).one()
        assert record.verification_model == "mock-groq"
