"""15-control gold-standard mapping validator.

Deterministic benchmark that proves the production mapping pipeline selects
the canonical compliance control for each of 15 curated findings.

How it works (no production code is modified):
1. Load ``gold_standard.json`` (controls + 15 canonical mappings).
2. Build a fresh in-memory SQLite database and seed the gold controls.
3. Run the *real* ``process_scan_run`` pipeline, but patch the two AI
   steps (Gemini mapping, Groq verification) with a faithful oracle:
     * the Gemini oracle accepts the candidate that the deterministic
       ``narrow_candidates`` pre-filter ranked first (this is what we are
       measuring - whether narrowing + workflow pick the right control),
     * the Groq oracle agrees (so the mapping is published, not dropped).
4. Compare each predicted control id with the gold expectation and report
   precision / recall.

Usage:
    python tests/benchmark/validate_mappings.py
    python tests/benchmark/validate_mappings.py --gold <path> --min-recall 1.0

Exit code is 0 only when the configured thresholds are met.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make the ``complisoc`` package importable regardless of CWD.
_THIS = pathlib.Path(__file__).resolve()
for _cand in _THIS.parents:
    if (_cand / "complisoc" / "backend" / "__init__.py").exists():
        if str(_cand) not in sys.path:
            sys.path.insert(0, str(_cand))
        break

from complisoc.backend.compliance.mapping import CandidateDecision  # noqa: E402
from complisoc.backend.compliance.verification import VerificationDecision  # noqa: E402
from complisoc.backend.database.base import Base  # noqa: E402
from complisoc.backend.models import (  # noqa: E402
    ControlCatalog,
    ControlMapping,
    NormalizedFinding,
    RawFinding,
)
from complisoc.backend.compliance.workflow import process_scan_run  # noqa: E402


def _oracle_mapper_side_effect(items):
    """Accept only the first-ranked candidate for every finding.

    Returns a decision per candidate: ``maps=True`` for the top candidate
    (the one deterministic narrowing ranked first) and ``maps=False`` for
    the rest. This isolates the measurement to the narrowing + workflow
    selection logic rather than the LLM.
    """
    out: dict[int, list[CandidateDecision]] = {}
    for finding, candidates in items:
        decisions = []
        for rank, candidate in enumerate(candidates):
            control = candidate.control_catalog
            if control is None:
                continue
            decisions.append(
                CandidateDecision(
                    control_id=control.control_id,
                    maps=rank == 0,
                    confidence=0.95 if rank == 0 else 0.10,
                    rationale="oracle: accept top deterministic candidate" if rank == 0 else "oracle: reject lower-ranked candidate",
                )
            )
        out[finding.id] = decisions
    return out


def _oracle_verifier_side_effect(items):
    return {
        item.ref: VerificationDecision(
            result="agree",
            agreement_value=1.0,
            explanation="oracle: agree",
            model="groq",
            prompt_version="gold-v1",
        )
        for item in items
    }


def load_gold(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_db(gold: dict):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()

    seen = set()
    for control in gold["controls"]:
        key = (gold["framework"], control["control_id"])
        if key in seen:
            continue
        seen.add(key)
        db.add(
            ControlCatalog(
                framework_name=gold["framework"],
                framework_version=gold["framework_version"],
                control_id=control["control_id"],
                control_family=control["control_family"],
                title=control["title"],
                description=control["description"],
                objective=control.get("objective"),
                evidence_examples=control.get("evidence_examples"),
                scanner_signals=control.get("scanner_signals"),
                keywords=control.get("keywords"),
                source_url=control["source_url"],
                active_status=True,
            )
        )
    db.commit()
    return db


def run_pipeline(db, gold: dict) -> None:
    findings = [
        {
            "scanner_name": entry["scanner_name"],
            "scanner_finding_id": entry["scanner_finding_id"],
            "raw_json": entry["raw_json"],
        }
        for entry in gold["mappings"]
    ]
    with patch(
        "complisoc.backend.compliance.langchain_pipeline.GeminiMapper"
    ) as MockMapper, patch(
        "complisoc.backend.compliance.langchain_pipeline.GroqVerifier"
    ) as MockVerifier:
        MockMapper.return_value.map_batch.side_effect = _oracle_mapper_side_effect
        MockVerifier.return_value.verify_batch.side_effect = _oracle_verifier_side_effect
        process_scan_run(db, target_environment="gold-benchmark", findings=findings)


def collect_predictions(db) -> dict[str, dict]:
    rows = (
        db.query(ControlMapping)
        .join(ControlMapping.normalized_finding)
        .join(RawFinding, NormalizedFinding.raw_finding_id == RawFinding.id)
        .join(ControlMapping.control_catalog)
        .all()
    )
    predicted: dict[str, dict] = {}
    for mapping in rows:
        sfid = mapping.normalized_finding.raw_finding.scanner_finding_id
        predicted[sfid] = {
            "control_id": mapping.control_catalog.control_id,
            "framework": mapping.control_catalog.framework_name,
            "status": mapping.mapping_status,
            "final_confidence": mapping.final_confidence,
        }
    return predicted


def evaluate(gold: dict, predicted: dict) -> dict:
    tp = fp = fn = 0
    per_item = []
    gold_by_id = {entry["scanner_finding_id"]: entry for entry in gold["mappings"]}

    for entry in gold["mappings"]:
        sfid = entry["scanner_finding_id"]
        expected = entry["expected_control_id"]
        pred = predicted.get(sfid)
        if pred is None:
            fn += 1
            per_item.append((sfid, expected, None, "MISSING"))
        elif pred["control_id"] == expected:
            tp += 1
            per_item.append((sfid, expected, pred["control_id"], "OK"))
        else:
            fn += 1
            fp += 1
            per_item.append((sfid, expected, pred["control_id"], "WRONG"))

    # Predictions not present in the gold set count as false positives.
    for sfid, pred in predicted.items():
        if sfid not in gold_by_id:
            fp += 1
            per_item.append((sfid, None, pred["control_id"], "EXTRA"))

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "total_gold": len(gold["mappings"]),
        "total_predicted": len(predicted),
        "per_item": per_item,
    }


def print_report(gold: dict, metrics: dict) -> None:
    print("=" * 72)
    print("Complisoc 15-control gold-standard mapping validation")
    print("=" * 72)
    print(f"{'finding_id':<12}{'expected':<12}{'predicted':<12}{'result'}")
    print("-" * 72)
    for sfid, expected, predicted, status in metrics["per_item"]:
        print(f"{sfid:<12}{str(expected):<12}{str(predicted):<12}{status}")
    print("-" * 72)
    print(f"Gold mappings      : {metrics['total_gold']}")
    print(f"Pipeline mappings : {metrics['total_predicted']}")
    print(f"True positives    : {metrics['tp']}")
    print(f"False positives   : {metrics['fp']}")
    print(f"False negatives   : {metrics['fn']}")
    print(f"Precision          : {metrics['precision']:.3f}")
    print(f"Recall             : {metrics['recall']:.3f}")
    print("=" * 72)


def validate(gold_path: pathlib.Path) -> dict:
    gold = load_gold(gold_path)
    db = build_db(gold)
    try:
        run_pipeline(db, gold)
        predicted = collect_predictions(db)
    finally:
        db.close()
    metrics = evaluate(gold, predicted)
    print_report(gold, metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate 15-control gold-standard mappings.")
    parser.add_argument(
        "--gold",
        type=pathlib.Path,
        default=pathlib.Path(__file__).with_name("gold_standard.json"),
        help="Path to gold_standard.json",
    )
    parser.add_argument("--min-precision", type=float, default=1.0)
    parser.add_argument("--min-recall", type=float, default=1.0)
    args = parser.parse_args(argv)

    metrics = validate(args.gold)
    if metrics["precision"] < args.min_precision or metrics["recall"] < args.min_recall:
        print(
            f"FAIL: precision {metrics['precision']:.3f} < {args.min_precision} "
            f"or recall {metrics['recall']:.3f} < {args.min_recall}"
        )
        return 1
    print("PASS: gold-standard mapping validation succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
