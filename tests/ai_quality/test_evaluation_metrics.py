"""Tests for the benchmark's mapping metrics and curated dataset."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

_BENCHMARK_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "benchmark")
if _BENCHMARK_DIR not in sys.path:
    sys.path.insert(0, _BENCHMARK_DIR)

from catalog_validation import validate_gold_catalog  # noqa: E402
from validate_mappings import evaluate  # noqa: E402

_GOLD_PATH = pathlib.Path(_BENCHMARK_DIR) / "gold_standard.json"


def _gold(expected: str | None = "A.5.15") -> dict:
    return {
        "controls": [{"control_id": "A.5.15"}, {"control_id": "A.8.13"}],
        "mappings": [{"scanner_finding_id": "F-1", "expected_control_id": expected}],
    }


def _metrics(expected: str | None, predicted_control: str | None) -> dict:
    predicted = {} if predicted_control is None else {"F-1": {"control_id": predicted_control}}
    return evaluate(_gold(expected), predicted)


class TestPrecisionRecallF1:
    def test_precision_counts_incorrect_valid_control_as_false_positive(self):
        metrics = _metrics("A.5.15", "A.8.13")
        assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (0, 1, 1)
        assert metrics["precision"] == 0.0

    def test_recall_counts_incorrect_valid_control_as_false_negative(self):
        metrics = _metrics("A.5.15", "A.8.13")
        assert metrics["recall"] == 0.0

    def test_f1_is_exact_match_score(self):
        metrics = _metrics("A.5.15", "A.5.15")
        assert metrics["f1"] == 1.0

    def test_wrong_prediction_has_zero_f1(self):
        assert _metrics("A.5.15", "A.8.13")["f1"] == 0.0

    def test_correct_prediction_is_true_positive(self):
        metrics = _metrics("A.5.15", "A.5.15")
        assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (1, 0, 0)

    def test_missing_prediction_is_false_negative(self):
        metrics = _metrics("A.5.15", None)
        assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (0, 0, 1)

    def test_unexpected_prediction_for_unmapped_finding_is_false_positive(self):
        metrics = _metrics(None, "A.5.15")
        assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (0, 1, 0)

    def test_unmapped_finding_without_prediction_is_not_a_false_negative(self):
        metrics = _metrics(None, None)
        assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (0, 0, 0)


class TestHallucinationRate:
    def test_invalid_control_id_is_reported_separately(self):
        metrics = _metrics("A.5.15", "A.9.1")
        assert metrics["fp"] == 1
        assert metrics["fn"] == 1
        assert metrics["invalid_control_predictions"] == 1
        assert metrics["per_item"][0][3] == "INVALID_CONTROL"

    def test_valid_but_wrong_control_is_not_a_hallucinated_id(self):
        gold = _gold()
        metrics = evaluate(gold, {"F-1": {"control_id": "A.8.13"}})
        assert (metrics["fp"], metrics["fn"]) == (1, 1)
        assert metrics["invalid_control_predictions"] == 0
        assert metrics["per_item"][0][3] == "WRONG"

    def test_unexpected_valid_control_prediction_counts_as_false_positive(self):
        metrics = _metrics(None, "A.5.15")
        assert metrics["fp"] == 1
        assert metrics["invalid_control_predictions"] == 0
        assert metrics["per_item"][0][3] == "UNEXPECTED"

    def test_extra_invalid_control_is_reported(self):
        metrics = evaluate(_gold(), {"EXTRA": {"control_id": "A.9.1"}})
        assert metrics["fp"] == 1
        assert metrics["fn"] == 1
        assert metrics["invalid_control_predictions"] == 1


class TestMappingStability:
    def test_same_predictions_produce_same_metrics(self):
        gold = _gold()
        predictions = {"F-1": {"control_id": "A.5.15"}}
        assert evaluate(gold, predictions) == evaluate(gold, predictions)

    def test_per_item_status_exposes_wrong_mapping(self):
        metrics = _metrics("A.5.15", "A.8.13")
        assert metrics["per_item"] == [("F-1", "A.5.15", "A.8.13", "WRONG")]

    def test_extra_prediction_does_not_inflate_recall(self):
        metrics = evaluate(
            _gold(),
            {"F-1": {"control_id": "A.5.15"}, "EXTRA": {"control_id": "A.5.15"}},
        )
        assert metrics["recall"] == 1.0
        assert metrics["precision"] == pytest.approx(0.5)


class TestBenchmarkDataset:
    def test_curated_dataset_contains_expected_mapping_count(self):
        gold = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
        assert len(gold["mappings"]) == 32

    def test_dataset_control_metadata_matches_production_catalog(self):
        gold = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
        validate_gold_catalog(gold)

    def test_dataset_covers_multiple_control_families(self):
        gold = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
        assert {"Organizational", "Technological", "Physical"} <= {
            control["control_family"] for control in gold["controls"]
        }

    def test_dataset_has_valid_severities(self):
        gold = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
        allowed = {"critical", "high", "medium", "low", "info"}
        assert {item["raw_json"]["severity"] for item in gold["mappings"]} <= allowed

    def test_dataset_finding_ids_are_unique_and_labeled(self):
        gold = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
        finding_ids = [item["scanner_finding_id"] for item in gold["mappings"]]
        control_ids = {item["control_id"] for item in gold["controls"]}
        assert len(finding_ids) == len(set(finding_ids))
        assert all(item["expected_control_id"] in control_ids for item in gold["mappings"])
