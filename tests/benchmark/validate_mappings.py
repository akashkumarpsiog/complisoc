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
from complisoc.backend.core.config import PROMPT_VERSION  # noqa: E402
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


def run_pipeline(db, gold: dict, live: bool = False) -> None:
    """Run the production pipeline against the gold dataset.

    When ``live`` is False (default, CI-safe), the Gemini and Groq steps
    are patched with a deterministic oracle. When ``live`` is True, the
    real ``GeminiMapper`` and ``GroqVerifier`` classes are used, so this
    path actually exercises the cross-model verification that earned the
    proposal its approval. The live path requires ``GEMINI_API_KEY`` and
    ``GROQ_API_KEY`` to be set in the environment.
    """
    findings = [
        {
            "scanner_name": entry["scanner_name"],
            "scanner_finding_id": entry["scanner_finding_id"],
            "raw_json": entry["raw_json"],
        }
        for entry in gold["mappings"]
    ]
    if live:
        process_scan_run(db, target_environment="gold-benchmark-live", findings=findings)
        return
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


def compute_f1(metrics: dict) -> float:
    """F1 score from a metrics dict produced by evaluate()."""
    p = metrics["precision"]
    r = metrics["recall"]
    return 2 * p * r / (p + r) if (p + r) else 0.0


def write_snapshot(path: pathlib.Path, gold: dict, predicted: dict, metrics: dict) -> None:
    """Serialize the current benchmark run as a snapshot file.

    Snapshot schema:
        {
          "version": "mvp-v1",
          "gold_path": "<source gold_standard.json>",
          "gold_count": 30,
          "metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0, ...},
          "predictions": {
              "GOLD-1": {"control_id": "A.5.15", "status": "published", "final_confidence": 0.95},
              ...
          }
        }
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PROMPT_VERSION,
        "gold_path": str(_GOLD_PATH_DEFAULT),
        "gold_count": len(gold["mappings"]),
        "metrics": {
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": compute_f1(metrics),
            "tp": metrics["tp"],
            "fp": metrics["fp"],
            "fn": metrics["fn"],
            "total_gold": metrics["total_gold"],
            "total_predicted": metrics["total_predicted"],
        },
        "predictions": {
            sfid: {
                "control_id": pred["control_id"],
                "status": pred["status"],
                "final_confidence": pred["final_confidence"],
            }
            for sfid, pred in sorted(predicted.items())
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_snapshot(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compute_f1_delta(snapshot: dict, current_metrics: dict, current_predictions: dict | None = None) -> dict:
    """Compare current run against a committed snapshot.

    Returns a dict with:
        - snapshot_f1: the F1 from the snapshot
        - current_f1: the F1 from the current run
        - f1_delta: |current - snapshot|
        - snapshot_metrics: full metrics from the snapshot
        - current_metrics: full metrics from the current run
        - changed_findings: list of (scanner_finding_id, snapshot_control, current_control)
                             for findings whose control mapping changed.

    If ``current_predictions`` is not provided, only metric-level deltas
    are reported (no per-finding change list).
    """
    snapshot_f1 = snapshot["metrics"]["f1"]
    current_f1 = compute_f1(current_metrics)
    changed: list[dict] = []
    if current_predictions is not None:
        snapshot_preds = snapshot.get("predictions", {})
        all_ids = sorted(set(snapshot_preds.keys()) | set(current_predictions.keys()))
        for sfid in all_ids:
            snap_pred = snapshot_preds.get(sfid)
            curr_pred = current_predictions.get(sfid)
            snap_ctrl = snap_pred.get("control_id") if snap_pred else None
            curr_ctrl = curr_pred.get("control_id") if curr_pred else None
            if snap_ctrl != curr_ctrl:
                changed.append(
                    {
                        "scanner_finding_id": sfid,
                        "snapshot_control": snap_ctrl,
                        "current_control": curr_ctrl,
                    }
                )
    return {
        "snapshot_f1": snapshot_f1,
        "current_f1": current_f1,
        "f1_delta": abs(current_f1 - snapshot_f1),
        "snapshot_metrics": snapshot["metrics"],
        "current_metrics": {
            "precision": current_metrics["precision"],
            "recall": current_metrics["recall"],
            "f1": current_f1,
            "tp": current_metrics["tp"],
            "fp": current_metrics["fp"],
            "fn": current_metrics["fn"],
        },
        "changed_findings": changed,
    }


# Path to the default gold-standard file, used when serialising snapshots.
_GOLD_PATH_DEFAULT = pathlib.Path(__file__).with_name("gold_standard.json")


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
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
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


def validate(gold_path: pathlib.Path, live: bool = False) -> dict:
    """Run the benchmark on a gold file and return the metrics dict.

    Returns ``metrics`` (precision, recall, f1, tp, fp, fn, totals).
    """
    gold = load_gold(gold_path)
    db = build_db(gold)
    try:
        run_pipeline(db, gold, live=live)
        predicted = collect_predictions(db)
    finally:
        db.close()
    metrics = evaluate(gold, predicted)
    return metrics


def run_and_capture(gold_path: pathlib.Path, live: bool = False) -> tuple:
    """Run the benchmark and return ``(gold, predicted, metrics)``.

    The full output is needed by callers that need per-finding
    predictions (snapshot diff, F1-delta computation). Most callers
    should use :func:`validate` instead.
    """
    gold = load_gold(gold_path)
    db = build_db(gold)
    try:
        run_pipeline(db, gold, live=live)
        predicted = collect_predictions(db)
    finally:
        db.close()
    metrics = evaluate(gold, predicted)
    return gold, predicted, metrics


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
    parser.add_argument(
        "--snapshot",
        type=pathlib.Path,
        default=pathlib.Path(__file__).parent / "snapshots" / "mvp-v1.json",
        help="Path to the F1-delta snapshot file (defaults to tests/benchmark/snapshots/mvp-v1.json)",
    )
    parser.add_argument(
        "--update-snapshot",
        action="store_true",
        help="Regenerate the snapshot from the current run and exit (skips threshold check).",
    )
    parser.add_argument(
        "--check-snapshot",
        action="store_true",
        help="Run, load the committed snapshot, and fail if F1-delta exceeds 0.05.",
    )
    parser.add_argument(
        "--max-f1-delta",
        type=float,
        default=0.05,
        help="Maximum allowed F1-delta vs the committed snapshot (default 0.05).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run against the real Gemini and Groq APIs (the cross-model "
            "verification path from the approved proposal). Requires "
            "GEMINI_API_KEY and GROQ_API_KEY in the environment. The "
            "default (no --live) uses a deterministic oracle for CI safety."
        ),
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("evidence/benchmark_live_results.json"),
        help=(
            "Where to write the live-mode JSON result file "
            "(only used when --live is set)."
        ),
    )
    args = parser.parse_args(argv)

    gold = load_gold(args.gold)
    db = build_db(gold)
    try:
        run_pipeline(db, gold, live=args.live)
        predicted = collect_predictions(db)
    finally:
        db.close()
    metrics = evaluate(gold, predicted)
    print_report(gold, metrics)

    if args.update_snapshot:
        write_snapshot(args.snapshot, gold, predicted, metrics)
        print(f"Snapshot updated: {args.snapshot}")
        return 0

    if args.check_snapshot:
        if not args.snapshot.exists():
            print(
                f"FAIL: snapshot not found at {args.snapshot}. "
                "Generate it with --update-snapshot first."
            )
            return 1
        snapshot = load_snapshot(args.snapshot)
        delta = compute_f1_delta(snapshot, metrics, current_predictions=predicted)
        print(
            f"Snapshot F1={delta['snapshot_f1']:.3f} | "
            f"Current F1={delta['current_f1']:.3f} | "
            f"delta={delta['f1_delta']:.3f}"
        )
        if delta["changed_findings"]:
            print(f"Changed findings: {len(delta['changed_findings'])}")
            for change in delta["changed_findings"][:10]:
                print(
                    f"  {change['scanner_finding_id']}: "
                    f"{change['snapshot_control']} -> {change['current_control']}"
                )
        if delta["f1_delta"] > args.max_f1_delta:
            print(
                f"FAIL: F1-delta {delta['f1_delta']:.3f} > {args.max_f1_delta:.3f}"
            )
            return 1
        print("PASS: F1-delta within threshold.")
        return 0

    if metrics["precision"] < args.min_precision or metrics["recall"] < args.min_recall:
        print(
            f"FAIL: precision {metrics['precision']:.3f} < {args.min_precision} "
            f"or recall {metrics['recall']:.3f} < {args.min_recall}"
        )
        return 1
    print("PASS: gold-standard mapping validation succeeded.")

    if args.live:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "mode": "live",
                    "prompt_version": "mvp-v1",
                    "framework": gold["framework"],
                    "framework_version": gold["framework_version"],
                    "gold_count": len(gold["mappings"]),
                    "metrics": {
                        "precision": metrics["precision"],
                        "recall": metrics["recall"],
                        "f1": compute_f1(metrics),
                        "tp": metrics["tp"],
                        "fp": metrics["fp"],
                        "fn": metrics["fn"],
                    },
                    "per_finding": [
                        {
                            "scanner_finding_id": sfid,
                            "expected_control_id": entry["expected_control_id"],
                            "predicted_control_id": predicted[sfid]["control_id"] if sfid in predicted else None,
                            "mapping_status": predicted[sfid]["status"] if sfid in predicted else None,
                            "final_confidence": predicted[sfid]["final_confidence"] if sfid in predicted else None,
                            "result": (
                                "OK"
                                if sfid in predicted
                                and predicted[sfid]["control_id"] == entry["expected_control_id"]
                                else "WRONG"
                            ),
                        }
                        for entry in gold["mappings"]
                        for sfid in [entry["scanner_finding_id"]]
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Live results written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
