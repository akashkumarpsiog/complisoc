import pytest
from complisoc.backend.database.base import Base
from complisoc.backend import models  # noqa: F401


def get_constraint_names(table_name):
    table = Base.metadata.tables[table_name]
    return {c.name for c in table.constraints if c.name}


def get_index_names(table_name):
    table = Base.metadata.tables[table_name]
    return {idx.name for idx in table.indexes}


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


# ---------------------------
# Column Schema Tests
# ---------------------------

def test_scan_runs_schema():
    columns = set(Base.metadata.tables["scan_runs"].columns.keys())
    assert columns == {
        "id",
        "target_environment",
        "status",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }


def test_raw_findings_schema():
    columns = set(Base.metadata.tables["raw_findings"].columns.keys())
    assert columns == {
        "id",
        "scanner_execution_id",
        "scanner_finding_id",
        "scanner_name",
        "raw_json",
        "created_at",
    }


def test_normalized_findings_schema():
    columns = set(Base.metadata.tables["normalized_findings"].columns.keys())
    assert columns == {
        "id",
        "raw_finding_id",
        "scanner_name",
        "finding_type",
        "resource_type",
        "resource_identifier",
        "severity",
        "title",
        "description",
        "metadata_json",
        "timestamp",
        "created_at",
        "updated_at",
    }


def test_control_catalog_schema():
    columns = set(Base.metadata.tables["control_catalog"].columns.keys())
    assert columns == {
        "id",
        "framework_name",
        "framework_version",
        "control_id",
        "control_family",
        "title",
        "description",
        "objective",
        "evidence_examples",
        "scanner_signals",
        "keywords",
        "source_url",
        "active_status",
        "created_at",
        "updated_at",
    }


def test_candidate_controls_schema():
    columns = set(Base.metadata.tables["candidate_controls"].columns.keys())
    assert columns == {
        "id",
        "normalized_finding_id",
        "control_catalog_id",
        "source",
        "match_score",
        "rank",
        "created_at",
        "updated_at",
    }


def test_control_mappings_schema():
    columns = set(Base.metadata.tables["control_mappings"].columns.keys())
    assert columns == {
        "id",
        "normalized_finding_id",
        "candidate_control_id",
        "control_catalog_id",
        "rank",
        "mapping_model",
        "prompt_version",
        "rationale",
        "gemini_confidence",
        "verification_status",
        "final_confidence",
        "groq_agreement_value",
        "mapping_status",
        "created_at",
        "updated_at",
    }

    assert "status" not in columns


def test_verification_records_schema():
    columns = set(Base.metadata.tables["verification_records"].columns.keys())
    assert columns == {
        "id",
        "control_mapping_id",
        "verification_model",
        "prompt_version",
        "result",
        "explanation",
        "agreement_value",
        "timestamp",
        "created_at",
    }


def test_review_queue_items_schema():
    columns = set(Base.metadata.tables["review_queue_items"].columns.keys())
    assert columns == {
        "id",
        "control_mapping_id",
        "status",
        "reviewer_id",
        "review_reason_code",
        "comments",
        "reviewed_at",
        "created_at",
        "updated_at",
    }


def test_compliance_reports_schema():
    columns = set(Base.metadata.tables["compliance_reports"].columns.keys())
    assert columns == {
        "id",
        "scan_run_id",
        "report_type",
        "generated_by",
        "generated_at",
        "content_path",
        "content_hash",
        "created_at",
        "updated_at",
    }


def test_audit_bundles_schema():
    columns = set(Base.metadata.tables["audit_bundles"].columns.keys())
    assert columns == {
        "id",
        "scan_run_id",
        "generated_at",
        "bundle_path",
        "checksum",
        "created_at",
        "updated_at",
    }


# ---------------------------
# Constraint Tests
# ---------------------------

def test_scan_runs_constraints():
    constraints = get_constraint_names("scan_runs")
    assert "ck_scanrun_status" in constraints


def test_normalized_findings_constraints():
    constraints = get_constraint_names("normalized_findings")
    assert "ck_nf_severity" in constraints


def test_control_catalog_constraints():
    constraints = get_constraint_names("control_catalog")
    assert "uq_framework_control" in constraints


def test_candidate_controls_constraints():
    constraints = get_constraint_names("candidate_controls")
    assert "uq_candidate_control" in constraints


def test_control_mappings_constraints():
    constraints = get_constraint_names("control_mappings")
    assert "ck_mapping_status" in constraints
    assert "ck_verification_status" in constraints


def test_verification_records_constraints():
    constraints = get_constraint_names("verification_records")
    assert "ck_verification_result" in constraints


def test_raw_findings_constraints():
    constraints = get_constraint_names("raw_findings")
    assert "uq_raw_finding" in constraints


# ---------------------------
# Index Tests
# ---------------------------

def test_normalized_findings_indexes():
    indexes = get_index_names("normalized_findings")
    assert "idx_nf_finding_type" in indexes
    assert "idx_nf_severity" in indexes
    assert "idx_nf_scanner" in indexes


def test_candidate_controls_indexes():
    indexes = get_index_names("candidate_controls")
    assert "idx_candidate_match_score" in indexes


def test_control_mappings_indexes():
    indexes = get_index_names("control_mappings")
    assert "idx_mapping_status" in indexes
    assert "idx_final_confidence" in indexes


def test_review_queue_indexes():
    indexes = get_index_names("review_queue_items")
    assert "idx_review_status" in indexes