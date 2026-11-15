"""HTTP integration tests against the documented FastAPI routes."""
from __future__ import annotations

from complisoc.backend.models import ControlCatalog, ReviewQueueItem

_API = "/api/v1"


def _create_scan(client, finding, target="api-quality"):
    response = client.post(
        f"{_API}/scan-runs",
        json={"target_environment": target, "findings": [finding]},
    )
    assert response.status_code == 201
    return response.json()


def _create_manual_review(client, finding, mocked_ai_services, target="api-quality-review"):
    mocked_ai_services.state["confidence"] = 0.4
    return _create_scan(client, finding, target)


class TestScanEndpoints:
    def test_health_endpoint_returns_service_status(self, ai_quality_client):
        response = ai_quality_client.get(f"{_API}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_endpoint_checks_database(self, ai_quality_client):
        response = ai_quality_client.get(f"{_API}/readiness")
        assert response.status_code == 200
        assert response.json()["database"] == "ok"

    def test_scanner_list_uses_scanner_registry(self, ai_quality_client):
        response = ai_quality_client.get(f"{_API}/scanners")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_scan_run_creation_processes_finding(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        assert scan["status"] == "completed"
        assert scan["id"] > 0

    def test_scan_run_creation_rejects_missing_environment(self, ai_quality_client):
        response = ai_quality_client.post(f"{_API}/scan-runs", json={"findings": []})
        assert response.status_code == 422

    def test_scan_run_creation_rejects_wrong_scanner_type(self, ai_quality_client):
        response = ai_quality_client.post(
            f"{_API}/scan-runs",
            json={
                "target_environment": "api-invalid-scanner",
                "findings": [
                    {
                        "scanner_name": 123,
                        "scanner_finding_id": "BAD-1",
                        "raw_json": {},
                    }
                ],
            },
        )
        assert response.status_code == 422

    def test_scan_endpoint_runs_scanners_and_pipeline(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services, monkeypatch
    ):
        from complisoc.backend.api import main as api_module

        finding = ai_quality_finding()
        monkeypatch.setattr(api_module, "run_scanners", lambda *_, **__: ([finding], []))
        monkeypatch.setattr(api_module, "resolve_scanners", lambda *_, **__: ["checkov"])
        response = ai_quality_client.post(
            f"{_API}/scans",
            json={"target": "example-repository", "scanners": ["checkov"]},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "running"
        scan_id = response.json()["id"]
        completed = ai_quality_client.get(f"{_API}/scan-runs/{scan_id}").json()
        assert completed["status"] == "completed"
        assert completed["ai_status"] == "ok"

    def test_scan_endpoint_rejects_missing_target(self, ai_quality_client):
        response = ai_quality_client.post(f"{_API}/scans", json={})
        assert response.status_code == 422

    def test_scan_runs_list_returns_database_rows(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.get(f"{_API}/scan-runs")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_scan_run_detail_returns_existing_record(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.get(f"{_API}/scan-runs/{scan['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == scan["id"]

    def test_missing_scan_run_returns_not_found(self, ai_quality_client):
        assert ai_quality_client.get(f"{_API}/scan-runs/999").status_code == 404

    def test_scan_run_summary_uses_persisted_findings(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.get(f"{_API}/scan-runs/{scan['id']}/summary")
        assert response.status_code == 200
        assert response.json()

    def test_scan_run_archive_mutates_lifecycle_state(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.post(f"{_API}/scan-runs/{scan['id']}/archive")
        assert response.status_code == 200
        assert response.json()["archived_at"] is not None

    def test_archived_scan_is_hidden_by_default(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        ai_quality_client.post(f"{_API}/scan-runs/{scan['id']}/archive")
        response = ai_quality_client.get(f"{_API}/scan-runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_archived_scan_can_be_restored(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        ai_quality_client.post(f"{_API}/scan-runs/{scan['id']}/archive")
        response = ai_quality_client.post(f"{_API}/scan-runs/{scan['id']}/restore")
        assert response.status_code == 200
        assert response.json()["archived_at"] is None


class TestFindingAndMappingEndpoints:
    def test_findings_list_returns_normalized_rows(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.get(f"{_API}/findings")
        assert response.status_code == 200
        assert response.json()[0]["severity"] == "high"

    def test_finding_detail_returns_requested_finding(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_scan(ai_quality_client, ai_quality_finding())
        finding = ai_quality_client.get(f"{_API}/findings").json()[0]
        response = ai_quality_client.get(f"{_API}/findings/{finding['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == finding["id"]
        assert ai_quality_client.get(f"{_API}/findings/999").status_code == 404

    def test_mappings_list_returns_persisted_decision(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.get(f"{_API}/mappings")
        assert response.status_code == 200
        assert response.json()[0]["control_catalog_id"] > 0

    def test_mapping_detail_and_verification_routes_return_lineage(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_scan(ai_quality_client, ai_quality_finding())
        mapping = ai_quality_client.get(f"{_API}/mappings").json()[0]
        detail = ai_quality_client.get(f"{_API}/mappings/{mapping['id']}")
        verification = ai_quality_client.get(f"{_API}/mappings/{mapping['id']}/verification")
        assert detail.status_code == 200
        assert verification.status_code == 200
        assert verification.json()[0]["result"] == "agree"

    def test_review_queue_lists_low_confidence_mapping(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_manual_review(ai_quality_client, ai_quality_finding(), mocked_ai_services)
        response = ai_quality_client.get(f"{_API}/review-queue")
        assert response.status_code == 200
        assert response.json()[0]["status"] == "pending"

    def test_review_item_detail_returns_persisted_item(
        self, ai_quality_client, ai_quality_finding, ai_quality_db, mocked_ai_services
    ):
        _create_manual_review(ai_quality_client, ai_quality_finding(), mocked_ai_services)
        item = ai_quality_db.query(ReviewQueueItem).one()
        response = ai_quality_client.get(f"{_API}/review-queue/{item.id}")
        assert response.status_code == 200
        assert response.json()["id"] == item.id

    def test_approval_updates_review_and_mapping(
        self, ai_quality_client, ai_quality_finding, ai_quality_db, mocked_ai_services
    ):
        _create_manual_review(ai_quality_client, ai_quality_finding(), mocked_ai_services)
        item = ai_quality_db.query(ReviewQueueItem).one()
        response = ai_quality_client.post(
            f"{_API}/review-queue/{item.id}/approve",
            json={"reviewer_id": "reviewer", "comments": "verified"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    def test_rejection_updates_review_item(
        self, ai_quality_client, ai_quality_finding, ai_quality_db, mocked_ai_services
    ):
        _create_manual_review(ai_quality_client, ai_quality_finding(), mocked_ai_services)
        item = ai_quality_db.query(ReviewQueueItem).one()
        response = ai_quality_client.post(f"{_API}/review-queue/{item.id}/reject", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_bulk_review_rejects_invalid_action(self, ai_quality_client):
        response = ai_quality_client.post(
            f"{_API}/review-queue/bulk-decide",
            json={"item_ids": [1], "action": "publish"},
        )
        assert response.status_code == 422

    def test_bulk_archive_returns_affected_count(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        scan = _create_scan(ai_quality_client, ai_quality_finding())
        response = ai_quality_client.post(
            f"{_API}/scan-runs/bulk-archive",
            json={"scan_run_ids": [scan["id"]]},
        )
        assert response.status_code == 200
        assert response.json()["archived_count"] == 1


class TestCatalogAndReportingEndpoints:
    def test_controls_route_filters_real_catalog(
        self, ai_quality_client, ai_quality_db
    ):
        control = ai_quality_db.query(ControlCatalog).first()
        response = ai_quality_client.get(
            f"{_API}/controls",
            params={"framework": control.framework_name},
        )
        assert response.status_code == 200
        assert all(item["framework_name"] == control.framework_name for item in response.json())

    def test_control_detail_uses_database_primary_key(self, ai_quality_client, ai_quality_db):
        control = ai_quality_db.query(ControlCatalog).first()
        response = ai_quality_client.get(f"{_API}/controls/{control.id}")
        assert response.status_code == 200
        assert response.json()["control_id"] == control.control_id

    def test_drift_and_lineage_routes_use_persisted_evidence(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        finding_payload = ai_quality_finding()
        previous_scan = _create_scan(ai_quality_client, finding_payload)
        current_scan = _create_scan(ai_quality_client, finding_payload)
        finding = ai_quality_client.get(f"{_API}/findings").json()[0]
        drift = ai_quality_client.get(
            f"{_API}/scan-runs/{current_scan['id']}/drift",
            params={"compare_to": previous_scan["id"]},
        )
        lineage = ai_quality_client.get(f"{_API}/findings/{finding['id']}/lineage")
        assert drift.status_code == 200
        assert drift.json()["unchanged_count"] == 1
        assert lineage.status_code == 200
        assert lineage.json()["mappings"][0]["control_id"] == "A.5.15"

    def test_dashboard_endpoints_return_database_aggregates(
        self, ai_quality_client, ai_quality_finding, mocked_ai_services
    ):
        _create_scan(ai_quality_client, ai_quality_finding())
        for endpoint in (
            "control-coverage",
            "severity-distribution",
            "gap-summary",
            "remediation-backlog",
            "trends",
            "cloud-findings",
            "ai-metrics",
        ):
            response = ai_quality_client.get(f"{_API}/dashboard/{endpoint}")
            assert response.status_code == 200, endpoint

    def test_report_and_audit_collection_routes_return_empty_database_state(self, ai_quality_client):
        reports = ai_quality_client.get(f"{_API}/reports")
        bundles = ai_quality_client.get(f"{_API}/audit-bundles")
        scenario = ai_quality_client.post(f"{_API}/reports/scenario", json={"scan_run_id": 1})
        missing_report = ai_quality_client.get(f"{_API}/reports/999")
        missing_bundle = ai_quality_client.get(f"{_API}/audit-bundles/999")
        assert reports.status_code == 200
        assert reports.json() == []
        assert bundles.status_code == 200
        assert bundles.json() == []
        assert scenario.status_code == 422
        assert missing_report.status_code == 404
        assert missing_bundle.status_code == 404
