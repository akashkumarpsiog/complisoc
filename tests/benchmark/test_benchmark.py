"""Pytest entry point for the 30-mapping gold-standard benchmark.

Runs ``validate_mappings.validate`` against ``gold_standard.json`` so the
benchmark is exercised by the normal test runner (and CI).

Week 15 scale target: 30 canonical mappings (15 controls x 2 finding variants)
with precision >= 1.0, recall >= 1.0, and zero hallucinations.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_THIS_DIR = str(pathlib.Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from validate_mappings import validate  # noqa: E402

_GOLD = pathlib.Path(__file__).with_name("gold_standard.json")


@pytest.mark.benchmark
def test_gold_standard_mappings_meet_threshold():
    assert _GOLD.exists(), "gold_standard.json must exist next to this test"
    metrics = validate(_GOLD)
    assert metrics["total_gold"] >= 30, f"benchmark must contain >=30 mappings, got {metrics['total_gold']}"
    assert metrics["recall"] >= 1.0, f"recall {metrics['recall']} < 1.0"
    assert metrics["precision"] >= 1.0, f"precision {metrics['precision']} < 1.0"
    assert metrics["fn"] == 0, "gold-standard has false negatives"
    assert metrics["fp"] == 0, "gold-standard has false positives"
