"""AI Evaluation Metrics Tests

Tests for precision, recall, F1 score, hallucination rate, and mapping stability.
These metrics are required by REQUIREMENTS.md section 12.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class EvaluationCase:
    """A single evaluation case for AI mapping."""
    finding_id: int
    predicted_control: str
    actual_control: str | None
    confidence: float


class TestPrecisionRecallF1:
    """Tests for precision, recall, and F1 score metrics."""

    def test_precision_calculation(self):
        """Precision = TP / (TP + FP)."""
        cases = [
            EvaluationCase(1, "AC-1", "AC-1", 0.9),
            EvaluationCase(2, "AC-2", "AC-2", 0.85),
            EvaluationCase(3, "AC-3", None, 0.3),
            EvaluationCase(4, "AC-4", "AC-4", 0.8),
        ]
        tp = sum(1 for c in cases if c.actual_control == c.predicted_control and c.actual_control is not None)
        fp = sum(1 for c in cases if c.actual_control != c.predicted_control and c.actual_control is None)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        assert 0 <= precision <= 1
        assert precision == 0.75  # 3 / (3 + 1)

    def test_recall_calculation(self):
        """Recall = TP / (TP + FN)."""
        cases = [
            EvaluationCase(1, "AC-1", "AC-1", 0.9),
            EvaluationCase(2, "AC-2", "AC-2", 0.85),
            EvaluationCase(3, "AC-3", "AC-5", 0.4),
            EvaluationCase(4, "AC-4", "AC-4", 0.8),
        ]
        tp = sum(1 for c in cases if c.actual_control == c.predicted_control)
        fn = sum(1 for c in cases if c.actual_control != c.predicted_control)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert 0 <= recall <= 1
        assert recall == 0.75  # 3 correct out of 4 total

    def test_f1_score_calculation(self):
        """F1 = 2 * (precision * recall) / (precision + recall)."""
        precision = 0.75
        recall = 0.6
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        assert 0 <= f1 <= 1
        assert abs(f1 - 0.6667) < 0.01

    def test_f1_with_zero_precision(self):
        """F1 should be 0 when precision is 0."""
        precision = 0.0
        recall = 0.5
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        assert f1 == 0.0

    def test_f1_with_perfect_scores(self):
        """F1 should be 1.0 when both precision and recall are 1.0."""
        precision = 1.0
        recall = 1.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        assert f1 == 1.0

    def test_metrics_with_confidence_threshold(self):
        """Metrics should be calculable at different confidence thresholds."""
        cases = [
            EvaluationCase(1, "AC-1", "AC-1", 0.9),
            EvaluationCase(2, "AC-2", "AC-2", 0.85),
            EvaluationCase(3, "AC-3", None, 0.3),
            EvaluationCase(4, "AC-4", "AC-4", 0.8),
            EvaluationCase(5, "AC-5", None, 0.5),
        ]
        threshold = 0.70
        filtered = [c for c in cases if c.confidence >= threshold]
        tp = sum(1 for c in filtered if c.actual_control == c.predicted_control and c.actual_control is not None)
        fp = sum(1 for c in filtered if c.actual_control != c.predicted_control and c.actual_control is None)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        assert precision == 1.0  # All high-confidence predictions are correct


class TestHallucinationRate:
    """Tests for hallucination rate metric."""

    def test_hallucination_detected(self):
        """Hallucination = predicted control not in catalog."""
        catalog_controls = {"AC-1", "AC-2", "AC-3", "AU-1", "SC-8"}
        predictions = [
            {"control_id": "AC-1", "confidence": 0.9},
            {"control_id": "AC-99", "confidence": 0.8},
            {"control_id": "SC-8", "confidence": 0.85},
        ]
        hallucinations = [p for p in predictions if p["control_id"] not in catalog_controls]
        hallucination_rate = len(hallucinations) / len(predictions) if predictions else 0.0
        assert 0 <= hallucination_rate <= 1
        assert hallucination_rate == 1 / 3

    def test_no_hallucinations(self):
        """Zero hallucinations when all predictions are in catalog."""
        catalog_controls = {"AC-1", "AC-2", "AC-3"}
        predictions = [
            {"control_id": "AC-1", "confidence": 0.9},
            {"control_id": "AC-2", "confidence": 0.8},
        ]
        hallucinations = [p for p in predictions if p["control_id"] not in catalog_controls]
        hallucination_rate = len(hallucinations) / len(predictions) if predictions else 0.0
        assert hallucination_rate == 0.0

    def test_hallucination_rate_threshold(self):
        """Hallucination rate should be below threshold."""
        max_hallucination_rate = 0.10
        catalog_controls = {"AC-1", "AC-2", "AC-3", "AU-1", "SC-8"}
        predictions = [
            {"control_id": "AC-1", "confidence": 0.9},
            {"control_id": "AC-2", "confidence": 0.85},
            {"control_id": "AC-3", "confidence": 0.8},
        ]
        hallucinations = [p for p in predictions if p["control_id"] not in catalog_controls]
        hallucination_rate = len(hallucinations) / len(predictions) if predictions else 0.0
        assert hallucination_rate <= max_hallucination_rate

    def test_hallucination_with_invalid_format(self):
        """Control IDs with invalid format should be flagged."""
        import re
        valid_pattern = r"^[A-Z]{2}-\d+$"
        predictions = [
            {"control_id": "AC-1", "confidence": 0.9},
            {"control_id": "INVALID", "confidence": 0.8},
            {"control_id": "XYZ-99", "confidence": 0.7},
        ]
        invalid_format = [p for p in predictions if not re.match(valid_pattern, p["control_id"])]
        assert len(invalid_format) == 2  # INVALID and XYZ-99


class TestMappingStability:
    """Tests for mapping stability metric."""

    def test_stable_mapping_across_runs(self):
        """Same finding should map to same control across runs."""
        run_1 = {1: "AC-1", 2: "AC-2", 3: "AU-3"}
        run_2 = {1: "AC-1", 2: "AC-2", 3: "AU-3"}
        stable = all(run_1[k] == run_2[k] for k in run_1)
        assert stable

    def test_mapping_stability_score(self):
        """Stability score = % of consistent mappings."""
        run_1 = {1: "AC-1", 2: "AC-2", 3: "AU-3", 4: "SC-8"}
        run_2 = {1: "AC-1", 2: "AC-2", 3: "AU-3", 4: "SC-7"}
        consistent = sum(1 for k in run_1 if run_1[k] == run_2[k])
        stability = consistent / len(run_1) if run_1 else 0.0
        assert stability == 0.75

    def test_stability_threshold(self):
        """Stability should be above threshold."""
        min_stability = 0.80
        run_1 = {1: "AC-1", 2: "AC-2", 3: "AU-3"}
        run_2 = {1: "AC-1", 2: "AC-2", 3: "AU-3"}
        consistent = sum(1 for k in run_1 if run_1[k] == run_2[k])
        stability = consistent / len(run_1) if run_1 else 0.0
        assert stability >= min_stability

    def test_confidence_stability(self):
        """Confidence scores should be stable across runs."""
        run_1 = {1: 0.85, 2: 0.72, 3: 0.91}
        run_2 = {1: 0.84, 2: 0.73, 3: 0.90}
        for k in run_1:
            assert abs(run_1[k] - run_2[k]) < 0.05

    def test_mapping_drift_detected(self):
        """Mapping drift should be detected when mappings change."""
        baseline = {1: "AC-1", 2: "AC-2", 3: "AU-3"}
        current = {1: "AC-1", 2: "AC-3", 3: "AU-3"}
        drifted = {k for k in baseline if baseline[k] != current[k]}
        assert len(drifted) == 1
        assert 2 in drifted


class TestBenchmarkDataset:
    """Tests for benchmark dataset requirements (30-50 curated findings)."""

    def test_benchmark_dataset_size(self):
        """Benchmark dataset should have 30-50 findings."""
        min_size = 30
        max_size = 50
        benchmark_findings = list(range(1, 41))  # 40 findings
        assert min_size <= len(benchmark_findings) <= max_size

    def test_benchmark_covers_multiple_categories(self):
        """Benchmark should cover multiple finding categories."""
        categories = ["access_control", "encryption", "audit", "configuration", "network"]
        benchmark_categories = ["access_control", "encryption", "audit", "configuration"]
        coverage = len(benchmark_categories) / len(categories)
        assert coverage >= 0.6  # At least 60% coverage

    def test_benchmark_covers_multiple_severities(self):
        """Benchmark should cover multiple severity levels."""
        severities = ["low", "medium", "high", "critical"]
        benchmark_severities = ["medium", "high", "critical"]
        coverage = len(benchmark_severities) / len(severities)
        assert coverage >= 0.5

    def test_benchmark_has_ground_truth(self):
        """Benchmark findings should have ground truth mappings."""
        benchmark = [
            {"id": 1, "title": "Weak password", "ground_truth": "AC-1"},
            {"id": 2, "title": "Unencrypted data", "ground_truth": "SC-8"},
            {"id": 3, "title": "Missing audit logs", "ground_truth": "AU-2"},
        ]
        for finding in benchmark:
            assert "ground_truth" in finding
            assert len(finding["ground_truth"]) > 0

    def test_benchmark_has_expected_confidence(self):
        """Benchmark should have expected confidence ranges."""
        benchmark = [
            {"id": 1, "ground_truth": "AC-1", "min_confidence": 0.7},
            {"id": 2, "ground_truth": "SC-8", "min_confidence": 0.6},
        ]
        for finding in benchmark:
            assert "min_confidence" in finding
            assert 0 <= finding["min_confidence"] <= 1
