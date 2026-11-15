"""Offline pipeline throughput tests with provider calls mocked.

These measure the real SQLite-backed Complisoc workflow, not live model
latency or production infrastructure capacity.
"""
from __future__ import annotations

from time import perf_counter

from complisoc.backend.compliance.workflow import process_scan_run
from complisoc.backend.models import ScannerExecution


def _process_batch(db, make_finding, mocked_ai_services, count: int):
    findings = [make_finding(index) for index in range(1, count + 1)]
    started = perf_counter()
    result = process_scan_run(
        db,
        target_environment=f"ai-quality-load-{count}",
        findings=findings,
    )
    elapsed = perf_counter() - started
    assert len(result["raw_findings"]) == count
    assert len(result["normalized_findings"]) == count
    assert len(result["mappings"]) == count
    return elapsed, result


class TestAILoadRequirements:
    def test_500_findings_use_real_pipeline_within_local_safety_budget(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        elapsed, _ = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 500)
        assert elapsed < 180

    def test_1000_findings_use_real_pipeline_within_scaled_local_safety_budget(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        elapsed, _ = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 1000)
        assert elapsed < 360

    def test_batch_processing_persists_each_input_finding(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 40)
        assert len({finding.scanner_finding_id for finding in result["raw_findings"]}) == 40

    def test_batch_processing_creates_lineage_for_each_mapping(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 25)
        assert {
            mapping.normalized_finding_id for mapping in result["mappings"]
        } == {finding.id for finding in result["normalized_findings"]}

    def test_batch_failure_is_retained_in_pipeline_result(self, ai_quality_db):
        result = process_scan_run(
            ai_quality_db,
            target_environment="ai-quality-load-failure",
            findings=[],
            scanner_failures=[{"scanner_name": "trivy", "error_message": "scanner unavailable"}],
        )
        assert result["scan_run"].status == "failed"
        execution = ai_quality_db.query(ScannerExecution).filter_by(scanner_name="trivy").one()
        assert execution.error_message == "scanner unavailable"

    def test_empty_batch_completes_without_mapping_calls(self, ai_quality_db, mocked_ai_services):
        result = process_scan_run(ai_quality_db, target_environment="ai-quality-load-empty", findings=[])
        assert result["scan_run"].status == "completed"
        assert result["mappings"] == []
        mocked_ai_services.mapper.map_batch.assert_not_called()


class TestAIScalability:
    def test_small_batch_runs_through_pipeline(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 10)
        assert len(result["mappings"]) == 10

    def test_medium_batch_runs_through_pipeline(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 50)
        assert len(result["mappings"]) == 50

    def test_large_batch_runs_through_pipeline(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 100)
        assert len(result["mappings"]) == 100

    def test_measured_throughput_uses_elapsed_pipeline_time(
        self, ai_quality_db, ai_quality_finding, mocked_ai_services
    ):
        elapsed, _ = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 20)
        assert elapsed > 0

    def test_identical_scanner_ids_are_deduplicated_by_ingestion(self, ai_quality_db, mocked_ai_services):
        finding = {
            "scanner_name": "checkov",
            "scanner_finding_id": "AIQ-DUPLICATE",
            "raw_json": {
                "finding_type": "iam public access permission",
                "resource_type": "aws_iam_policy",
                "resource_identifier": "policy.duplicate",
                "severity": "high",
                "title": "Public IAM policy",
                "description": "IAM policy permits public access.",
            },
        }
        result = process_scan_run(
            ai_quality_db,
            target_environment="ai-quality-load-dedupe",
            findings=[finding, finding],
        )
        assert len(result["raw_findings"]) == 1


class TestAIResourceBehavior:
    def test_pipeline_returns_only_completed_mappings(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 5)
        assert all(mapping.mapping_status == "published" for mapping in result["mappings"])

    def test_pipeline_keeps_scanner_failures_with_findings(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        result = process_scan_run(
            ai_quality_db,
            target_environment="ai-quality-load-mixed",
            findings=[ai_quality_finding()],
            scanner_failures=[{"scanner_name": "trivy", "error_message": "timed out"}],
        )
        assert len(result["raw_findings"]) == 1
        assert result["scan_run"].status == "completed"
        execution = ai_quality_db.query(ScannerExecution).filter_by(scanner_name="trivy").one()
        assert execution.error_message == "timed out"

    def test_mapping_persistence_keeps_final_confidence(self, ai_quality_db, ai_quality_finding, mocked_ai_services):
        _, result = _process_batch(ai_quality_db, ai_quality_finding, mocked_ai_services, 3)
        assert all(mapping.final_confidence == 0.97 for mapping in result["mappings"])
