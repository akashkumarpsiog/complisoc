"""LangChain vs direct-path equivalence (Week 7 gap #5).

Proves the LangChain/LCEL pipeline (``complisoc.backend.compliance.langchain_pipeline``)
produces output equivalent to the direct ``process_scan_run`` workflow.

Both paths reuse the same deterministic + AI building blocks, so with
the *same* mocked Gemini/Groq behaviour they must yield the same
set of control mappings (same findings mapped, same control ids, same
final confidence, same publication status).
"""
from __future__ import annotations

import pathlib
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_THIS_DIR = str(pathlib.Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from complisoc.backend.api.main import process_scan_run  # noqa: E402
from complisoc.backend.compliance.langchain_pipeline import (  # noqa: E402
    is_langchain_available,
    run_pipeline,
)
from complisoc.backend.compliance.mapping import CandidateDecision  # noqa: E402
from complisoc.backend.compliance.verification import VerificationDecision  # noqa: E402
from complisoc.backend.database.base import Base  # noqa: E402
from complisoc.backend.models import (  # noqa: E402
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
)


def _seed_controls(db) -> None:
    db.add_all(
        [
            ControlCatalog(
                framework_name="ISO/IEC 27001:2022 Annex A",
                framework_version="2022",
                control_id="A.5.15",
                control_family="Organizational",
                title="Access Control",
                description="Limit access to information and systems.",
                objective="Prevent unauthorized access.",
                evidence_examples=["access_review_report"],
                scanner_signals=["iam", "public_access", "permission"],
                keywords=["access", "iam", "permission", "public"],
                source_url="https://example.test/iso-a-5-15",
                active_status=True,
            ),
            ControlCatalog(
                framework_name="SOC 2 Trust Services Criteria (TSC) 2022",
                framework_version="2017 (Revised Points of Focus - 2022)",
                control_id="CC6.6",
                control_family="Logical and Physical Access Controls",
                title="Protection Against External Threats",
                description="Restrict inbound and outbound network traffic.",
                objective="Limit external exposure.",
                evidence_examples=["firewall_rules"],
                scanner_signals=["security_group", "open_ingress", "0.0.0.0/0"],
                keywords=["network", "firewall", "public", "ingress"],
                source_url="https://example.test/soc2-cc6-6",
                active_status=True,
            ),
        ]
    )
    db.commit()


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return engine


def _sample_findings():
    return [
        {
            "scanner_name": "checkov",
            "scanner_finding_id": "CKV_AWS_1",
            "raw_json": {
                "finding_type": "iam public access permission",
                "resource_type": "aws_iam_policy",
                "resource_identifier": "aws_iam_policy.public_admin",
                "severity": "high",
                "title": "IAM policy allows public access permission",
                "description": "iam public access permission public iam access permission",
            },
        },
        {
            "scanner_name": "checkov",
            "scanner_finding_id": "CKV_NET_1",
            "raw_json": {
                "finding_type": "network",
                "resource_type": "aws_security_group",
                "resource_identifier": "sg-open",
                "severity": "medium",
                "title": "Network issue",
                "description": "network",
            },
        },
        {
            "scanner_name": "sonarqube",
            "scanner_finding_id": "SQ_1",
            "raw_json": {
                "finding_type": "iam public access permission",
                "resource_type": "aws_iam_role",
                "resource_identifier": "aws_iam_role.over_permissive",
                "severity": "high",
                "title": "IAM role grants public access permission",
                "description": "iam public access permission grants broad access",
            },
        },
    ]


def _oracle_mapper(items):
    out = {}
    for finding, candidates in items:
        out[finding.id] = [
            CandidateDecision(
                control_id=candidate.control_catalog.control_id,
                maps=(rank == 0),
                confidence=0.95 if rank == 0 else 0.10,
                rationale="oracle",
            )
            for rank, candidate in enumerate(candidates)
        ]
    return out


def _oracle_verifier(items):
    return {
        item.ref: VerificationDecision(result="agree", agreement_value=1.0, explanation="oracle")
        for item in items
    }


def _summarize(db):
    rows = (
        db.query(ControlMapping)
        .join(ControlMapping.normalized_finding)
        .join(RawFinding, NormalizedFinding.raw_finding_id == RawFinding.id)
        .join(ControlMapping.control_catalog)
        .all()
    )
    return {
        (r.normalized_finding.raw_finding.scanner_finding_id): {
            "control_id": r.control_catalog.control_id,
            "status": r.mapping_status,
            "final_confidence": round(r.final_confidence, 4) if r.final_confidence is not None else None,
            "gemini_confidence": r.gemini_confidence,
            "groq_agreement_value": r.groq_agreement_value,
        }
        for r in rows
    }


@pytest.mark.skipif(
    not is_langchain_available(),
    reason="langchain-core not installed",
)
def test_langchain_path_equivalent_to_direct_for_three_scans():
    findings = _sample_findings()

    # Direct path.
    engine_d = _engine()
    Local = sessionmaker(bind=engine_d, autoflush=False, autocommit=False, future=True)
    db_d = Local()
    _seed_controls(db_d)
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as M1, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as V1:
        M1.return_value.map_batch.side_effect = _oracle_mapper
        V1.return_value.verify_batch.side_effect = _oracle_verifier
        process_scan_run(db_d, target_environment="equivalence", findings=findings)
    direct = _summarize(db_d)
    db_d.close()

    # LangChain path (same inputs, same oracle).
    engine_l = _engine()
    Local = sessionmaker(bind=engine_l, autoflush=False, autocommit=False, future=True)
    db_l = Local()
    _seed_controls(db_l)
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as M2, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as V2:
        M2.return_value.map_batch.side_effect = _oracle_mapper
        V2.return_value.verify_batch.side_effect = _oracle_verifier
        run_pipeline(
            db_l,
            target_environment="equivalence",
            findings=findings,
        )
    langchain = _summarize(db_l)
    db_l.close()

    assert set(direct.keys()) == set(langchain.keys()), "different findings were mapped"
    for key in direct:
        d = direct[key]
        l = langchain[key]
        assert l["control_id"] == d["control_id"], f"{key}: control mismatch {l} vs {d}"
        assert l["status"] == d["status"], f"{key}: status mismatch {l} vs {d}"
        assert l["final_confidence"] == d["final_confidence"], f"{key}: confidence mismatch"
        assert l["gemini_confidence"] == d["gemini_confidence"]
        assert l["groq_agreement_value"] == d["groq_agreement_value"]


@pytest.mark.skipif(
    not is_langchain_available(),
    reason="langchain-core not installed",
)
def test_langchain_path_shape_matches_workflow_contract():
    engine = _engine()
    Local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Local()
    _seed_controls(db)
    with patch("complisoc.backend.compliance.langchain_pipeline.GeminiMapper") as M, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as V:
        M.return_value.map_batch.side_effect = _oracle_mapper
        V.return_value.verify_batch.side_effect = _oracle_verifier
        result = run_pipeline(
            db,
            target_environment="shape",
            findings=_sample_findings(),
        )
    db.close()

    # The same dict contract the API relies on.
    assert set(result.keys()) == {
        "scan_run",
        "raw_findings",
        "normalized_findings",
        "mappings",
        "review_items",
        "failures",
    }
    assert result["scan_run"] is not None
    assert len(result["raw_findings"]) == 3
    assert len(result["normalized_findings"]) == 3
    assert len(result["mappings"]) == 3
