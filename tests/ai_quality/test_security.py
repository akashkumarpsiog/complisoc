"""Security boundary tests for implemented API and workflow behavior."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from complisoc.backend.api.schemas import RawFindingInput
from complisoc.backend.compliance import mapping as mapping_module
from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.models import ControlCatalog, ControlMapping, ReviewQueueItem


class TestRequestBoundaries:
    def test_scanner_name_type_is_validated(self):
        payload = {
            "scanner_name": 123,
            "scanner_finding_id": "SEC-1",
            "raw_json": {"title": "finding"},
        }
        with pytest.raises(ValidationError):
            RawFindingInput.model_validate(payload)

    def test_scanner_name_length_is_enforced(self):
        payload = {
            "scanner_name": "s" * 129,
            "scanner_finding_id": "SEC-1",
            "raw_json": {"title": "finding"},
        }
        with pytest.raises(ValidationError):
            RawFindingInput.model_validate(payload)

    def test_malformed_nested_description_is_rejected_by_normalizer(
        self, ai_quality_db, ai_quality_finding
    ):
        finding = ai_quality_finding()
        finding["raw_json"]["description"] = ["unexpected", "list"]
        result = process_scan_run(
            ai_quality_db,
            target_environment="security-malformed-description",
            findings=[finding],
        )
        assert result["mappings"] == []
        assert result["normalized_findings"] == []
        assert any("description must be a string" in item["error"] for item in result["failures"])


class TestPersistedInputSafety:
    def test_xss_like_text_is_retained_as_literal_evidence(
        self, ai_quality_db, ai_quality_finding
    ):
        finding = ai_quality_finding()
        payload = "<script>alert('xss')</script>"
        finding["raw_json"]["description"] = payload
        result = process_scan_run(
            ai_quality_db,
            target_environment="security-xss-text",
            findings=[finding],
        )
        assert result["raw_findings"][0].raw_json["description"] == payload

    def test_sql_injection_text_does_not_change_control_catalog(
        self, ai_quality_db, ai_quality_finding
    ):
        finding = ai_quality_finding()
        payload = "'; DROP TABLE control_catalog; --"
        finding["raw_json"]["description"] = payload
        count = ai_quality_db.query(ControlCatalog).count()
        process_scan_run(
            ai_quality_db,
            target_environment="security-sql-text",
            findings=[finding],
        )
        assert ai_quality_db.query(ControlCatalog).count() == count

    def test_mapping_is_persisted_against_catalog_control(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        result = process_scan_run(
            ai_quality_db,
            target_environment="security-catalog-foreign-key",
            findings=[ai_quality_finding()],
        )
        mapping = result["mappings"][0]
        control = ai_quality_db.get(ControlCatalog, mapping.control_catalog_id)
        assert control is not None
        assert control.control_id == "A.5.15"

    def test_provider_cannot_publish_unknown_control_identifier(
        self,
        ai_quality_db,
        ai_quality_finding,
        provider_response_clients,
        monkeypatch,
    ):
        response = json.loads(provider_response_clients.state["gemini"])
        response["results"][0]["candidates"][0]["control_id"] = "A.99.99"
        provider_response_clients.state["gemini"] = json.dumps(response)
        provider_response_clients.install_pipeline_clients()
        monkeypatch.setattr(mapping_module, "call_with_retry", lambda fn, **_: fn())
        result = process_scan_run(
            ai_quality_db,
            target_environment="security-invalid-control",
            findings=[ai_quality_finding()],
        )
        assert result["mappings"][0].mapping_status == "manual_review"
        assert result["mappings"][0].gemini_confidence is None

class TestReviewWorkflowBoundary:
    def test_approval_updates_review_item_and_mapping(
        self, ai_quality_client, ai_quality_finding, ai_quality_db, mocked_ai_services
    ):
        mocked_ai_services.state["confidence"] = 0.4
        response = ai_quality_client.post(
            "/api/v1/scan-runs",
            json={
                "target_environment": "security-review-approval",
                "findings": [ai_quality_finding()],
            },
        )
        assert response.status_code == 201
        item = ai_quality_db.query(ReviewQueueItem).one()

        approved = ai_quality_client.post(
            f"/api/v1/review-queue/{item.id}/approve",
            json={"reviewer_id": "test-reviewer", "comments": "checked"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        mapping = ai_quality_db.get(ControlMapping, item.control_mapping_id)
        assert mapping.mapping_status == "published"

    def test_review_item_cannot_be_decided_twice(
        self, ai_quality_client, ai_quality_finding, ai_quality_db, mocked_ai_services
    ):
        mocked_ai_services.state["confidence"] = 0.4
        ai_quality_client.post(
            "/api/v1/scan-runs",
            json={
                "target_environment": "security-review-repeat",
                "findings": [ai_quality_finding()],
            },
        )
        item = ai_quality_db.query(ReviewQueueItem).one()
        first = ai_quality_client.post(f"/api/v1/review-queue/{item.id}/approve", json={})
        second = ai_quality_client.post(f"/api/v1/review-queue/{item.id}/reject", json={})
        assert first.status_code == 200
        assert second.status_code == 409

    def test_bulk_review_rejects_unknown_action(self, ai_quality_client):
        response = ai_quality_client.post(
            "/api/v1/review-queue/bulk-decide",
            json={"item_ids": [1], "action": "publish"},
        )
        assert response.status_code == 422


class TestUnimplementedSecurityTelemetry:
    @pytest.mark.skip(reason="The application has no output redaction or PII-scanning policy to exercise.")
    def test_generated_output_is_redacted_for_secrets_and_pii(self):
        pass
