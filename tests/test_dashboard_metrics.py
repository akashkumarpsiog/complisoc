from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from complisoc.backend.api import main as api_main
from complisoc.backend.database.base import Base
from complisoc.backend.models import (
    CandidateControl,
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
    ScanRun,
    ScannerExecution,
)


def _build_db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_dashboard_metric_helpers_are_accurate():
    db = _build_db_session()

    scan_run = ScanRun(target_environment="demo", status="completed")
    db.add(scan_run)
    db.flush()

    scanner = ScannerExecution(scan_run_id=scan_run.id, scanner_name="trivy", status="completed")
    db.add(scanner)
    db.flush()

    raw_high_1 = RawFinding(
        scanner_execution_id=scanner.id,
        scanner_finding_id="raw-high-1",
        scanner_name="trivy",
        raw_json={"id": "raw-high-1"},
    )
    raw_high_2 = RawFinding(
        scanner_execution_id=scanner.id,
        scanner_finding_id="raw-high-2",
        scanner_name="trivy",
        raw_json={"id": "raw-high-2"},
    )
    raw_medium = RawFinding(
        scanner_execution_id=scanner.id,
        scanner_finding_id="raw-medium-1",
        scanner_name="trivy",
        raw_json={"id": "raw-medium-1"},
    )
    db.add_all([raw_high_1, raw_high_2, raw_medium])
    db.flush()

    nf_high_1 = NormalizedFinding(
        raw_finding_id=raw_high_1.id,
        scanner_name="trivy",
        finding_type="misconfiguration",
        resource_type="aws_s3_bucket",
        resource_identifier="bucket-a",
        severity="high",
        title="Public bucket",
        description="Public bucket found",
    )
    nf_high_2 = NormalizedFinding(
        raw_finding_id=raw_high_2.id,
        scanner_name="trivy",
        finding_type="misconfiguration",
        resource_type="aws_iam_policy",
        resource_identifier="policy-b",
        severity="high",
        title="Public policy",
        description="Public policy found",
    )
    nf_medium = NormalizedFinding(
        raw_finding_id=raw_medium.id,
        scanner_name="trivy",
        finding_type="misconfiguration",
        resource_type="aws_vpc",
        resource_identifier="vpc-c",
        severity="medium",
        title="Weak network exposure",
        description="Network exposure found",
    )
    db.add_all([nf_high_1, nf_high_2, nf_medium])
    db.flush()

    catalog_a = ControlCatalog(
        framework_name="SOC2",
        framework_version="2022",
        control_id="CC8.1",
        control_family="Security",
        title="Access controls",
        description="Ensure controlled access",
        source_url="https://example.com/cc8.1",
        active_status=True,
        scanner_signals=["public bucket"],
        keywords=["public", "bucket"],
        evidence_examples=["bucket policy"],
    )
    catalog_b = ControlCatalog(
        framework_name="ISO27001",
        framework_version="2022",
        control_id="A.5.15",
        control_family="Access Control",
        title="Access management",
        description="Establish access management",
        source_url="https://example.com/a.5.15",
        active_status=True,
        scanner_signals=["public policy"],
        keywords=["public", "policy"],
        evidence_examples=["iam policy"],
    )
    catalog_c = ControlCatalog(
        framework_name="SOC2",
        framework_version="2022",
        control_id="CC6.1",
        control_family="Network Security",
        title="Network protection",
        description="Protect network",
        source_url="https://example.com/cc6.1",
        active_status=False,
        scanner_signals=["network exposure"],
        keywords=["network"],
        evidence_examples=["vpc"],
    )
    db.add_all([catalog_a, catalog_b, catalog_c])
    db.flush()

    candidate_a = CandidateControl(
        normalized_finding_id=nf_high_1.id,
        control_catalog_id=catalog_a.id,
        source="deterministic",
        match_score=0.94,
        rank=1,
    )
    candidate_b = CandidateControl(
        normalized_finding_id=nf_high_2.id,
        control_catalog_id=catalog_b.id,
        source="deterministic",
        match_score=0.89,
        rank=1,
    )
    candidate_c = CandidateControl(
        normalized_finding_id=nf_medium.id,
        control_catalog_id=catalog_c.id,
        source="deterministic",
        match_score=0.73,
        rank=1,
    )
    db.add_all([candidate_a, candidate_b, candidate_c])
    db.flush()

    mapping_published = ControlMapping(
        normalized_finding_id=nf_high_1.id,
        candidate_control_id=candidate_a.id,
        control_catalog_id=catalog_a.id,
        rank=1,
        mapping_model="test",
        prompt_version="v1",
        rationale="Matches the exposure",
        gemini_confidence=0.95,
        verification_status="agree",
        final_confidence=0.95,
        groq_agreement_value=1.0,
        mapping_status="published",
    )
    mapping_manual = ControlMapping(
        normalized_finding_id=nf_high_2.id,
        candidate_control_id=candidate_b.id,
        control_catalog_id=catalog_b.id,
        rank=1,
        mapping_model="test",
        prompt_version="v1",
        rationale="Needs review",
        gemini_confidence=0.60,
        verification_status="pending",
        final_confidence=0.60,
        groq_agreement_value=0.0,
        mapping_status="manual_review",
    )
    mapping_rejected = ControlMapping(
        normalized_finding_id=nf_medium.id,
        candidate_control_id=candidate_c.id,
        control_catalog_id=catalog_c.id,
        rank=1,
        mapping_model="test",
        prompt_version="v1",
        rationale="Rejected",
        gemini_confidence=0.20,
        verification_status="disagree",
        final_confidence=0.20,
        groq_agreement_value=0.0,
        mapping_status="rejected",
    )
    db.add_all([mapping_published, mapping_manual, mapping_rejected])
    db.commit()

    gap_summary = api_main._dashboard_gap_summary(db)
    assert gap_summary["manual_review_mappings"] == 1
    assert gap_summary["rejected_mappings"] == 1
    assert gap_summary["failed_controls"] == [
        {
            "control_id": "A.5.15",
            "control_title": "Access management",
            "count": 1,
            "status": "manual_review",
            "control_catalog_id": 2,
        },
        {
            "control_id": "CC6.1",
            "control_title": "Network protection",
            "count": 1,
            "status": "rejected",
            "control_catalog_id": 3,
        },
    ]

    assert api_main._dashboard_control_coverage(db) == {"covered_controls": 1, "total_controls": 2}
    assert api_main._dashboard_severity_distribution(db) == {"severity_counts": {"high": 2, "medium": 1}}


def test_dashboard_backlog_includes_control_drilldown_metadata():
    db = _build_db_session()
    scan_run = ScanRun(target_environment="backlog-demo", status="completed")
    db.add(scan_run)
    db.flush()

    scanner = ScannerExecution(scan_run_id=scan_run.id, scanner_name="checkov", status="completed")
    db.add(scanner)
    db.flush()

    raw = RawFinding(
        scanner_execution_id=scanner.id,
        scanner_finding_id="raw-backlog-1",
        scanner_name="checkov",
        raw_json={"id": "raw-backlog-1"},
    )
    db.add(raw)
    db.flush()

    finding = NormalizedFinding(
        raw_finding_id=raw.id,
        scanner_name="checkov",
        finding_type="IAM",
        resource_type="aws_iam_policy",
        resource_identifier="arn:aws:iam::123:policy/demo",
        severity="high",
        title="Public IAM policy",
        description="IAM policy is public",
    )
    db.add(finding)
    db.flush()

    control = ControlCatalog(
        framework_name="SOC2",
        framework_version="2022",
        control_id="CC6.1",
        control_family="Access",
        title="Network protection",
        description="Protect network access",
        source_url="https://example.com/cc6.1",
        active_status=True,
        scanner_signals=["iam policy"],
        keywords=["iam", "public"],
        evidence_examples=["iam policy"],
    )
    db.add(control)
    db.flush()

    candidate = CandidateControl(
        normalized_finding_id=finding.id,
        control_catalog_id=control.id,
        source="deterministic",
        match_score=0.91,
        rank=1,
    )
    db.add(candidate)
    db.flush()

    mapping = ControlMapping(
        normalized_finding_id=finding.id,
        candidate_control_id=candidate.id,
        control_catalog_id=control.id,
        rank=1,
        mapping_model="test",
        prompt_version="v1",
        rationale="Public IAM policy requires review",
        gemini_confidence=0.58,
        verification_status="pending",
        final_confidence=0.58,
        groq_agreement_value=0.0,
        mapping_status="manual_review",
    )
    db.add(mapping)
    db.commit()

    backlog = api_main._dashboard_remediation_backlog(db)
    assert backlog["items"][0]["mapping_id"] == mapping.id
    assert backlog["items"][0]["status"] == "manual_review"
    assert backlog["items"][0]["control_id"] == "CC6.1"
    assert backlog["items"][0]["control_title"] == "Network protection"
    assert backlog["items"][0]["resource_identifier"] == "arn:aws:iam::123:policy/demo"
    assert backlog["items"][0]["severity"] == "high"

    assert "CC6.1" in backlog["items"][0]["suggested_remediation"]
    assert "arn:aws:iam::123:policy/demo" in backlog["items"][0]["suggested_remediation"]
