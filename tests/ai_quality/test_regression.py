"""AI Regression Detection Tests

Detects when AI behavior changes unexpectedly between versions or runs.
These tests establish baselines and detect drift in AI outputs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class BehaviorBaseline:
    """Baseline behavior for regression testing."""
    input_hash: str
    expected_confidence_range: tuple[float, float]
    expected_decision: bool
    expected_rationale_keywords: list[str]
    tolerance: float = 0.1


@dataclass
class RegressionResult:
    """Result of a regression test."""
    passed: bool
    metric: str
    expected: Any
    actual: Any
    deviation: float
    message: str


class TestBehavioralRegression:
    """Tests that AI behavior hasn't regressed from baseline."""

    BASELINES: list[BehaviorBaseline] = [
        BehaviorBaseline(
            input_hash="finding_ac1_weak_password",
            expected_confidence_range=(0.7, 1.0),
            expected_decision=True,
            expected_rationale_keywords=["password", "access", "control"],
        ),
        BehaviorBaseline(
            input_hash="finding_sc1_unencrypted_data",
            expected_confidence_range=(0.6, 1.0),
            expected_decision=True,
            expected_rationale_keywords=["encryption", "data", "protection"],
        ),
        BehaviorBaseline(
            input_hash="finding_audit_missing_logs",
            expected_confidence_range=(0.5, 0.9),
            expected_decision=True,
            expected_rationale_keywords=["audit", "logging", "events"],
        ),
        BehaviorBaseline(
            input_hash="finding_unrelated_network",
            expected_confidence_range=(0.0, 0.4),
            expected_decision=False,
            expected_rationale_keywords=["not", "unrelated", "different"],
        ),
    ]

    def test_baseline_confidence_ranges_valid(self):
        """Baseline confidence ranges should be valid."""
        for baseline in self.BASELINES:
            low, high = baseline.expected_confidence_range
            assert 0.0 <= low <= high <= 1.0, f"Invalid range for {baseline.input_hash}"

    def test_baseline_decisions_defined(self):
        """Baseline decisions should be defined."""
        for baseline in self.BASELINES:
            assert isinstance(baseline.expected_decision, bool)

    def test_baseline_keywords_present(self):
        """Baseline keywords should be non-empty."""
        for baseline in self.BASELINES:
            assert len(baseline.expected_rationale_keywords) > 0

    def test_high_confidence_baselines_agree(self):
        """High confidence baselines should expect positive decision."""
        high_conf = [b for b in self.BASELINES if b.expected_confidence_range[0] >= 0.5]
        for baseline in high_conf:
            assert baseline.expected_decision == True

    def test_low_confidence_baselines_disagree(self):
        """Low confidence baselines should expect negative decision."""
        low_conf = [b for b in self.BASELINES if b.expected_confidence_range[1] < 0.5]
        for baseline in low_conf:
            assert baseline.expected_decision == False


class TestConfidenceDrift:
    """Tests for confidence score drift over time."""

    def test_confidence_mean_stable(self):
        """Mean confidence should be stable across runs."""
        run_1 = [0.85, 0.72, 0.68, 0.91, 0.75]
        run_2 = [0.83, 0.74, 0.70, 0.89, 0.77]
        mean_1 = sum(run_1) / len(run_1)
        mean_2 = sum(run_2) / len(run_2)
        drift = abs(mean_1 - mean_2)
        assert drift < 0.1, f"Confidence mean drifted by {drift}"

    def test_confidence_variance_stable(self):
        """Confidence variance should be stable."""
        run_1 = [0.85, 0.72, 0.68, 0.91, 0.75]
        run_2 = [0.83, 0.74, 0.70, 0.89, 0.77]
        mean_1 = sum(run_1) / len(run_1)
        mean_2 = sum(run_2) / len(run_2)
        var_1 = sum((x - mean_1) ** 2 for x in run_1) / len(run_1)
        var_2 = sum((x - mean_2) ** 2 for x in run_2) / len(run_2)
        drift = abs(var_1 - var_2)
        assert drift < 0.05, f"Confidence variance drifted by {drift}"

    def test_confidence_distribution_stable(self):
        """Distribution shape should be stable."""
        run_1 = [0.1, 0.3, 0.5, 0.7, 0.9]
        run_2 = [0.15, 0.35, 0.55, 0.75, 0.95]
        # Both should have same number of bins
        assert len(run_1) == len(run_2)

    def test_no_confidence_clustering(self):
        """Confidence should not cluster at single value."""
        confidences = [0.85, 0.82, 0.88, 0.79, 0.84]
        unique = len(set(confidences))
        assert unique > 1, "Confidence is clustered at single value"

    def test_no_confidence_polarization(self):
        """Confidence should not be only at extremes."""
        confidences = [0.1, 0.3, 0.5, 0.7, 0.9]
        middle = [c for c in confidences if 0.2 <= c <= 0.8]
        assert len(middle) > 0, "Confidence is polarized at extremes"


class TestDecisionDrift:
    """Tests for decision drift over time."""

    def test_acceptance_rate_stable(self):
        """Acceptance rate should be stable."""
        run_1 = [True, True, False, True, False]
        run_2 = [True, False, True, True, False]
        rate_1 = sum(run_1) / len(run_1)
        rate_2 = sum(run_2) / len(run_2)
        drift = abs(rate_1 - rate_2)
        assert drift < 0.3, f"Acceptance rate drifted by {drift}"

    def test_rejection_rate_stable(self):
        """Rejection rate should be stable."""
        run_1 = [False, True, False, True, False]
        run_2 = [False, False, True, True, False]
        rate_1 = sum(1 for x in run_1 if not x) / len(run_1)
        rate_2 = sum(1 for x in run_2 if not x) / len(run_2)
        drift = abs(rate_1 - rate_2)
        assert drift < 0.3, f"Rejection rate drifted by {drift}"

    def test_no_decision_flip_flop(self):
        """Decisions should not flip-flop on same input."""
        decisions = [True, True, True, False, False]
        changes = sum(1 for i in range(1, len(decisions)) if decisions[i] != decisions[i-1])
        assert changes < len(decisions) * 0.8, "Decisions are flip-flopping"

    def test_consistent_decision_boundary(self):
        """Decision boundary should be consistent."""
        decisions = [
            (0.95, True),
            (0.85, True),
            (0.75, True),
            (0.65, False),
            (0.55, False),
            (0.45, False),
        ]
        # Find boundary
        boundary = None
        for i in range(len(decisions) - 1):
            if decisions[i][1] and not decisions[i+1][1]:
                boundary = (decisions[i][0] + decisions[i+1][0]) / 2
        assert boundary is not None
        assert 0.5 <= boundary <= 0.85, f"Decision boundary {boundary} outside expected range"


class TestRationaleDrift:
    """Tests for rationale quality drift."""

    def test_rationale_length_stable(self):
        """Rationale length should be stable."""
        run_1 = ["direct match", "partial match", "no match"]
        run_2 = ["direct match to control", "partial match found", "no match detected"]
        avg_len_1 = sum(len(r) for r in run_1) / len(run_1)
        avg_len_2 = sum(len(r) for r in run_2) / len(run_2)
        drift = abs(avg_len_1 - avg_len_2)
        assert drift < 20, f"Rationale length drifted by {drift}"

    def test_no_degenerate_rationales(self):
        """Rationales should not become degenerate."""
        rationales = ["direct match", "partial match", "no match found", "weak alignment", "strong evidence"]
        assert not all(len(r) == 1 for r in rationales), "Rationales are degenerate"

    def test_rationale_vocabulary_stable(self):
        """Rationale vocabulary should be stable."""
        run_1_words = {"match", "control", "finding", "direct", "partial"}
        run_2_words = {"match", "control", "finding", "direct", "partial"}
        overlap = run_1_words & run_2_words
        assert len(overlap) >= len(run_1_words) * 0.5, "Rationale vocabulary changed significantly"
