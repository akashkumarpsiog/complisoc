"""Pytest entry point for the 32-mapping audited benchmark.

Runs ``validate_mappings.validate`` against ``gold_standard.json`` so the
benchmark is exercised by the normal test runner (and CI).

The benchmark covers 15 controls with at least two curated examples each.
It checks deterministic pipeline agreement, not model accuracy.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

_THIS_DIR = str(pathlib.Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from validate_mappings import live_provider_failures, validate  # noqa: E402
from catalog_validation import validate_gold_catalog  # noqa: E402
from generate_dataset import expand_benchmark  # noqa: E402

_GOLD = pathlib.Path(__file__).with_name("gold_standard.json")


@pytest.mark.benchmark
def test_gold_standard_mappings_meet_threshold():
    assert _GOLD.exists(), "gold_standard.json must exist next to this test"
    metrics = validate(_GOLD)
    assert metrics["total_gold"] == 32, f"benchmark must contain 32 mappings, got {metrics['total_gold']}"
    assert metrics["recall"] >= 1.0, f"recall {metrics['recall']} < 1.0"
    assert metrics["precision"] >= 1.0, f"precision {metrics['precision']} < 1.0"
    assert metrics["fn"] == 0, "gold-standard has false negatives"
    assert metrics["fp"] == 0, "gold-standard has false positives"


def test_gold_catalog_matches_production_control_metadata():
    gold = json.loads(_GOLD.read_text(encoding="utf-8"))
    validate_gold_catalog(gold)


def test_live_evaluation_requires_both_provider_results():
    gold = {"mappings": [{"scanner_finding_id": "GOLD-1"}]}
    prediction = {
        "GOLD-1": {
            "gemini_confidence": 0.9,
            "verification_status": "agree",
            "groq_agreement_value": 1.0,
        }
    }

    assert live_provider_failures(gold, prediction) == []


@pytest.mark.parametrize(
    "prediction",
    [
        {"GOLD-1": {"gemini_confidence": None, "verification_status": None}},
        {"GOLD-1": {"gemini_confidence": 0.9, "verification_status": None}},
        {},
    ],
)
def test_live_evaluation_rejects_missing_provider_results(prediction):
    gold = {"mappings": [{"scanner_finding_id": "GOLD-1"}]}

    assert live_provider_failures(gold, prediction)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("control_id", "A.9.1", "not present in the production"),
        ("title", "Encryption of information", "title does not match"),
        ("source_url", "https://example.test/placeholder", "source_url does not match"),
    ],
)
def test_gold_catalog_rejects_noncanonical_metadata(field, value, message):
    gold = copy.deepcopy(json.loads(_GOLD.read_text(encoding="utf-8")))
    gold["controls"][1][field] = value
    with pytest.raises(ValueError, match=message):
        validate_gold_catalog(gold)


def test_generator_preserves_audited_control_ids():
    gold = json.loads(_GOLD.read_text(encoding="utf-8"))
    expanded = expand_benchmark(gold, target_count=40)

    validate_gold_catalog(expanded)
    assert len(expanded["mappings"]) == 40
    assert {
        mapping["expected_control_id"] for mapping in expanded["mappings"]
    } <= {control["control_id"] for control in expanded["controls"]}


def test_generator_rejects_noncanonical_controls_even_when_not_expanding():
    gold = copy.deepcopy(json.loads(_GOLD.read_text(encoding="utf-8")))
    gold["controls"][0]["description"] = "Outdated description"

    with pytest.raises(ValueError, match="description does not match"):
        expand_benchmark(gold, target_count=len(gold["mappings"]) - 1)
