from complisoc.backend.database.base import Base
from complisoc.backend import models


def test_metadata_contains_expected_tables():
    expected_tables = {
        "scan_runs",
        "scanner_executions",
        "raw_findings",
        "normalized_findings",
        "control_catalog",
        "candidate_controls",
        "control_mappings",
        "verification_records",
        "review_queue_items",
        "compliance_reports",
        "audit_bundles",
    }

    assert set(Base.metadata.tables.keys()) == expected_tables


def test_scan_runs_match_schema_fields():
    columns = set(Base.metadata.tables["scan_runs"].columns.keys())
    assert "target_environment" in columns
    assert "name" not in columns


def test_raw_findings_have_only_raw_fields():
    columns = set(Base.metadata.tables["raw_findings"].columns.keys())
    assert columns == {
        "id",
        "scanner_execution_id",
        "scanner_finding_id",
        "scanner_name",
        "raw_json",
        "created_at",
    }


def test_control_mappings_match_schema_fields():
    columns = set(Base.metadata.tables["control_mappings"].columns.keys())
    assert "rank" in columns
    assert "mapping_model" in columns
    assert "prompt_version" in columns
    assert "verification_status" not in columns
    assert "final_confidence" not in columns
    assert "scan_run_id" not in columns
    assert "status" in columns


def test_verification_records_match_schema_fields():
    columns = set(Base.metadata.tables["verification_records"].columns.keys())
    assert "verification_model" in columns
    assert "prompt_version" in columns


def test_review_queue_items_match_schema_fields():
    columns = set(Base.metadata.tables["review_queue_items"].columns.keys())
    assert "review_reason_code" in columns
    assert "reviewed_at" in columns


def test_compliance_reports_use_content_path_and_hash():
    columns = set(Base.metadata.tables["compliance_reports"].columns.keys())
    assert "payload" not in columns
    assert "generated_by" in columns
    assert "content_path" in columns
    assert "content_hash" in columns


def test_audit_bundles_use_checksum():
    columns = set(Base.metadata.tables["audit_bundles"].columns.keys())
    assert "checksum" in columns
    assert "bundle_metadata" not in columns


def test_normalized_findings_use_metadata_json():
    columns = set(Base.metadata.tables["normalized_findings"].columns.keys())
    assert "metadata_json" in columns
    assert "normalized_data" not in columns
