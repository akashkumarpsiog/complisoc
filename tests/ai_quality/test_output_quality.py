"""Provider-output parsing and persisted workflow contract tests.

The provider payloads are controlled fixtures; these tests do not score live
model semantic quality.
"""
from __future__ import annotations

import json

from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.models import ControlMapping, VerificationRecord


def _process(db, finding, provider_response_clients, target="output-quality"):
    provider_response_clients.install_pipeline_clients()
    return process_scan_run(
        db,
        target_environment=target,
        findings=[finding],
    )


def _gemini_response(provider_response_clients) -> dict:
    return json.loads(provider_response_clients.state["gemini"])


def _groq_response(provider_response_clients) -> dict:
    return json.loads(provider_response_clients.state["groq"])


class TestOutputProcessing:
    def test_mapping_response_is_processed_by_real_pipeline(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].control_catalog.control_id == "A.5.15"

    def test_mapping_confidence_is_persisted(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].gemini_confidence == 0.95

    def test_mapping_rationale_is_persisted(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].rationale == "The finding identifies public IAM access."

    def test_verification_result_is_persisted(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].verification_status == "agree"

    def test_verification_explanation_is_associated_with_mapping(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        record = ai_quality_db.query(VerificationRecord).filter_by(
            control_mapping_id=result["mappings"][0].id
        ).one()
        assert record.explanation == "The control addresses the finding's access permissions."

    def test_final_confidence_uses_parsed_provider_values(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].final_confidence == 0.97

    def test_valid_mapping_is_published_by_workflow(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert result["mappings"][0].mapping_status == "published"

    def test_mapping_and_verification_records_are_persisted(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        _process(ai_quality_db, ai_quality_finding(), provider_response_clients)
        assert ai_quality_db.query(ControlMapping).count() == 1
        assert ai_quality_db.query(VerificationRecord).count() == 1

    def test_unknown_control_does_not_become_a_successful_mapping(
        self, ai_quality_db, ai_quality_finding, provider_response_clients, monkeypatch
    ):
        from complisoc.backend.compliance import mapping as mapping_module

        payload = _gemini_response(provider_response_clients)
        payload["results"][0]["candidates"][0]["control_id"] = "A.99.99"
        provider_response_clients.state["gemini"] = json.dumps(payload)
        monkeypatch.setattr(mapping_module, "call_with_retry", lambda fn, **_: fn())
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-invalid-id")
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_confidence_string_is_parsed_by_mapper(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        payload = _gemini_response(provider_response_clients)
        payload["results"][0]["candidates"][0]["confidence"] = "0.91"
        provider_response_clients.state["gemini"] = json.dumps(payload)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-string-confidence")
        assert result["mappings"][0].gemini_confidence == 0.91

    def test_string_boolean_is_parsed_by_mapper(self, ai_quality_db, ai_quality_finding, provider_response_clients):
        payload = _gemini_response(provider_response_clients)
        payload["results"][0]["candidates"][0]["maps"] = "yes"
        provider_response_clients.state["gemini"] = json.dumps(payload)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-string-bool")
        assert result["mappings"][0].mapping_status == "published"

    def test_negative_mapping_decision_is_not_published(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        payload = _gemini_response(provider_response_clients)
        payload["results"][0]["candidates"][0]["maps"] = False
        provider_response_clients.state["gemini"] = json.dumps(payload)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-negative")
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_missing_rationale_uses_mapper_fallback(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        payload = _gemini_response(provider_response_clients)
        del payload["results"][0]["candidates"][0]["rationale"]
        provider_response_clients.state["gemini"] = json.dumps(payload)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-no-rationale")
        assert result["mappings"][0].rationale == "No rationale provided by model."

    def test_missing_verification_explanation_uses_verifier_fallback(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        payload = _groq_response(provider_response_clients)
        del payload["results"][0]["explanation"]
        provider_response_clients.state["groq"] = json.dumps(payload)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-no-explanation")
        record = ai_quality_db.query(VerificationRecord).filter_by(
            control_mapping_id=result["mappings"][0].id
        ).one()
        assert record.explanation == "No explanation provided by model."

    def test_disagree_verification_is_persisted_and_reviewed(
        self, ai_quality_db, ai_quality_finding, provider_response_clients
    ):
        payload = _groq_response(provider_response_clients)
        payload["results"][0]["result"] = "disagree"
        provider_response_clients.state["groq"] = json.dumps(payload)
        result = _process(ai_quality_db, ai_quality_finding(), provider_response_clients, "output-disagree")
        assert result["mappings"][0].verification_status == "disagree"
        assert result["mappings"][0].mapping_status == "manual_review"

    def test_mapping_response_is_serializable_through_api(
        self, ai_quality_client, ai_quality_finding, provider_response_clients
    ):
        provider_response_clients.install_pipeline_clients()
        created = ai_quality_client.post(
            "/api/v1/scan-runs",
            json={
                "target_environment": "output-api-serialization",
                "findings": [ai_quality_finding()],
            },
        )
        assert created.status_code == 201
        listed = ai_quality_client.get("/api/v1/mappings")
        assert listed.status_code == 200
        assert listed.json()[0]["final_confidence"] == 0.97

    def test_lineage_endpoint_associates_explanation_with_finding(
        self, ai_quality_client, ai_quality_finding, provider_response_clients
    ):
        provider_response_clients.install_pipeline_clients()
        ai_quality_client.post(
            "/api/v1/scan-runs",
            json={
                "target_environment": "output-lineage",
                "findings": [ai_quality_finding()],
            },
        )
        findings = ai_quality_client.get("/api/v1/findings")
        finding_id = findings.json()[0]["id"]
        lineage = ai_quality_client.get(f"/api/v1/findings/{finding_id}/lineage")
        assert lineage.status_code == 200
        assert lineage.json()["mappings"][0]["verification_records"][0]["explanation"] == (
            "The control addresses the finding's access permissions."
        )
