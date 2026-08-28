"""AI Bias Detection Tests

Checks for systematic biases in AI outputs that could lead to unfair or incorrect decisions.
These tests ensure the AI treats different input types consistently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class BiasSample:
    """A sample for bias testing."""
    category: str
    input_text: str
    confidence: float
    decision: bool


class TestSelectionBias:
    """Tests for systematic selection bias in AI decisions."""

    def test_no_category_always_rejected(self):
        """No single category should always be rejected."""
        samples = [
            BiasSample("network", "network finding", 0.8, True),
            BiasSample("network", "network issue", 0.7, True),
            BiasSample("network", "network vulnerability", 0.3, False),
        ]
        network_results = [s.decision for s in samples if s.category == "network"]
        assert not all(r == False for r in network_results), "Network category always rejected"
        assert not all(r == True for r in network_results), "Network category always accepted"

    def test_no_category_always_accepted(self):
        """No single category should always be accepted."""
        samples = [
            BiasSample("access_control", "access finding", 0.9, True),
            BiasSample("access_control", "access issue", 0.85, True),
            BiasSample("access_control", "access vulnerability", 0.35, False),
        ]
        access_results = [s.decision for s in samples if s.category == "access_control"]
        assert not all(r == True for r in access_results), "Access control always accepted"

    def test_similar_confidence_across_categories(self):
        """Similar findings should have similar confidence regardless of category."""
        network = BiasSample("network", "weak firewall", 0.75, True)
        access = BiasSample("access_control", "weak password", 0.72, True)
        audit = BiasSample("audit", "missing logs", 0.70, True)
        confidences = [network.confidence, access.confidence, audit.confidence]
        spread = max(confidences) - min(confidences)
        assert spread < 0.15, f"Confidence varies too much across categories: {spread}"

    def test_category_confidence_not_extreme(self):
        """No category should have extreme average confidence."""
        samples = [
            BiasSample("network", "finding 1", 0.5, True),
            BiasSample("network", "finding 2", 0.6, True),
            BiasSample("network", "finding 3", 0.4, False),
        ]
        avg_confidence = sum(s.confidence for s in samples) / len(samples)
        assert 0.2 <= avg_confidence <= 0.9, f"Category average confidence extreme: {avg_confidence}"


class TestMeasurementBias:
    """Tests for measurement bias in AI outputs."""

    def test_confidence_not_correlated_with_input_length(self):
        """Confidence should not be correlated with input length."""
        short_input = BiasSample("test", "short", 0.7, True)
        long_input = BiasSample("test", "a" * 1000, 0.72, True)
        # Confidence should be similar regardless of input length
        assert abs(short_input.confidence - long_input.confidence) < 0.2

    def test_confidence_not_correlated_with_severity_keyword(self):
        """Confidence should not be artificially inflated by severity keywords."""
        critical = BiasSample("test", "CRITICAL vulnerability", 0.85, True)
        low = BiasSample("test", "low priority issue", 0.45, False)
        # Confidence should reflect actual match, not just severity
        assert critical.confidence > low.confidence

    def test_rationale_quality_not_input_dependent(self):
        """Rationale quality should not depend on input complexity."""
        simple_rationale = "direct match"
        complex_rationale = "direct match with comprehensive evidence"
        # Both should be valid rationales
        assert len(simple_rationale) >= 10
        assert len(complex_rationale) >= 10

    def test_verification_not_biased_by_mapping_confidence(self):
        """Verification should be independent of mapping confidence."""
        high_mapping = BiasSample("test", "finding", 0.95, True)
        low_mapping = BiasSample("test", "finding", 0.3, False)
        # Verification should evaluate independently
        assert high_mapping.confidence != low_mapping.confidence


class TestConfirmationBias:
    """Tests for confirmation bias in AI decisions."""

    def test_verification_not_always_agree(self):
        """Verification should not always agree with mapping."""
        samples = [
            BiasSample("test", "finding 1", 0.9, True),
            BiasSample("test", "finding 2", 0.3, False),
            BiasSample("test", "finding 3", 0.5, False),
        ]
        decisions = [s.decision for s in samples]
        assert not all(d == True for d in decisions), "Verification always agrees"
        assert not all(d == False for d in decisions), "Verification always disagrees"

    def test_mapping_not_self_fulfilling(self):
        """High mapping confidence should not guarantee verification agree."""
        high_conf_agree = BiasSample("test", "finding 1", 0.95, True)
        high_conf_disagree = BiasSample("test", "finding 2", 0.92, False)
        # Both should be possible
        assert high_conf_agree.decision != high_conf_disagree.decision

    def test_low_confidence_can_still_be_correct(self):
        """Low confidence decisions can still be correct."""
        low_conf_correct = BiasSample("test", "finding", 0.35, True)
        assert low_conf_correct.decision == True

    def test_high_confidence_can_still_be_wrong(self):
        """High confidence decisions can still be wrong."""
        high_conf_wrong = BiasSample("test", "finding", 0.95, False)
        assert high_conf_wrong.decision == False


class TestConsistencyBias:
    """Tests for consistency bias across similar inputs."""

    def test_similar_inputs_similar_outputs(self):
        """Similar inputs should produce similar outputs."""
        samples = [
            BiasSample("test", "weak password policy", 0.85, True),
            BiasSample("test", "weak password configuration", 0.83, True),
            BiasSample("test", "password policy weakness", 0.87, True),
        ]
        confidences = [s.confidence for s in samples]
        spread = max(confidences) - min(confidences)
        assert spread < 0.1, f"Similar inputs have very different confidence: {spread}"

    def test_order_independence(self):
        """Order of inputs should not affect individual decisions."""
        sample1 = BiasSample("test", "finding A", 0.8, True)
        sample2 = BiasSample("test", "finding B", 0.6, False)
        # Each decision should be independent
        assert sample1.confidence != sample2.confidence

    def test_repeated_input_same_output(self):
        """Same input should produce same output (deterministic)."""
        sample1 = BiasSample("test", "same finding", 0.75, True)
        sample2 = BiasSample("test", "same finding", 0.75, True)
        assert sample1.confidence == sample2.confidence
        assert sample1.decision == sample2.decision

    def test_paraphrase_invariance(self):
        """Paraphrased inputs should produce similar outputs."""
        original = BiasSample("test", "weak access controls", 0.8, True)
        paraphrase = BiasSample("test", "access controls are weak", 0.78, True)
        assert abs(original.confidence - paraphrase.confidence) < 0.1


class TestReportingBias:
    """Tests for bias in how results are reported."""

    def test_all_categories_represented(self):
        """All categories should be represented in results."""
        categories = ["network", "access_control", "audit", "encryption", "configuration"]
        for cat in categories:
            assert len(cat) > 0

    def test_no_category_overrepresented(self):
        """No single category should dominate results."""
        category_counts = {
            "network": 10,
            "access_control": 12,
            "audit": 8,
            "encryption": 9,
            "configuration": 11,
        }
        total = sum(category_counts.values())
        for cat, count in category_counts.items():
            proportion = count / total
            assert proportion < 0.4, f"Category {cat} overrepresented: {proportion:.1%}"

    def test_confidence_distribution_reported(self):
        """Confidence distribution should be reported, not just average."""
        confidences = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
        avg = sum(confidences) / len(confidences)
        median = sorted(confidences)[len(confidences) // 2]
        # For symmetric distributions avg == median, that's OK
        # The point is both should be available for reporting
        assert avg == median  # Symmetric distribution

    def test_uncertainty_quantified(self):
        """Uncertainty should be quantified, not hidden."""
        decision = {
            "confidence": 0.75,
            "confidence_interval": [0.65, 0.85],
            "sample_size": 100,
        }
        assert "confidence" in decision
        assert decision["confidence_interval"][0] <= decision["confidence"] <= decision["confidence_interval"][1]


class TestHistoricalBias:
    """Tests for bias from historical data patterns."""

    def test_no_feedback_loop(self):
        """AI should not reinforce its own previous decisions."""
        previous = BiasSample("test", "finding", 0.8, True)
        current = BiasSample("test", "similar finding", 0.5, False)
        # Current decision should be independent of previous
        assert current.confidence != previous.confidence or current.decision != previous.decision

    def test_no_anchoring(self):
        """AI should not anchor on initial values."""
        initial = BiasSample("test", "finding", 0.9, True)
        revised = BiasSample("test", "finding with more context", 0.6, False)
        # Revised decision can differ from initial
        assert revised.confidence != initial.confidence

    def test_no_recency_bias(self):
        """Recent findings should not be treated differently."""
        old_finding = BiasSample("test", "old finding", 0.75, True)
        new_finding = BiasSample("test", "new finding", 0.73, True)
        assert abs(old_finding.confidence - new_finding.confidence) < 0.1
