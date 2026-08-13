"""Week 15 scale test: runs the full compliance pipeline on the 30-mapping
benchmark dataset and measures precision, recall, hallucination rate, and
mapping stability.

Uses an oracle-mocked harness (deterministic narrowing + Gemini accept-top +
Groq agree) so results are reproducible in CI without live model calls.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

_THIS_DIR = str(pathlib.Path(__file__).resolve().parent / "benchmark")
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from validate_mappings import build_db, run_pipeline, collect_predictions, evaluate, load_gold  # noqa: E402

_GOLD = pathlib.Path(__file__).resolve().parent / "benchmark" / "gold_standard.json"


@pytest.mark.benchmark
def test_scale_30_mappings_precision_recall_no_hallucinations():
    from validate_mappings import build_db, run_pipeline, collect_predictions, evaluate, load_gold

    gold = load_gold(_GOLD)
    db = build_db(gold)
    try:
        run_pipeline(db, gold)
        predicted = collect_predictions(db)
    finally:
        db.close()

    metrics = evaluate(gold, predicted)

    assert metrics["total_gold"] >= 30, f"Scale test requires >=30 gold mappings, got {metrics['total_gold']}"
    assert metrics["recall"] >= 1.0, f"Scale recall {metrics['recall']} < 1.0"
    assert metrics["precision"] >= 1.0, f"Scale precision {metrics['precision']} < 1.0"
    assert metrics["fp"] == 0, f"Hallucination: {metrics['fp']} false-positive mappings"
    assert metrics["fn"] == 0, f"Coverage gap: {metrics['fn']} false-negative mappings"


@pytest.mark.benchmark
def test_scale_mapping_stability_across_repeated_runs():
    """Running the pipeline a second time on the same data must yield
    identical precision / recall (deterministic stability)."""
    from validate_mappings import build_db, run_pipeline, collect_predictions, evaluate, load_gold

    gold = load_gold(_GOLD)

    db1 = build_db(gold)
    try:
        run_pipeline(db1, gold)
        m1 = evaluate(gold, collect_predictions(db1))
    finally:
        db1.close()

    db2 = build_db(gold)
    try:
        run_pipeline(db2, gold)
        m2 = evaluate(gold, collect_predictions(db2))
    finally:
        db2.close()

    assert m1["precision"] == m2["precision"], "Precision not stable across runs"
    assert m1["recall"] == m2["recall"], "Recall not stable across runs"
    assert m1["tp"] == m2["tp"], "True positive count not stable across runs"
