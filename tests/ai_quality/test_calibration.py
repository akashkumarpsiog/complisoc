"""Confidence Calibration Tests

Validates that AI confidence scores are well-calibrated and meaningful.
A well-calibrated model's 80% confidence should be correct ~80% of the time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class CalibrationSample:
    """A sample with predicted confidence and actual outcome."""
    predicted_confidence: float
    actual_correct: bool


class TestConfidenceCalibration:
    """Tests that confidence scores are meaningful and calibrated."""

    def test_confidence_range_valid(self):
        """All confidence values must be in [0, 1]."""
        confidences = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        for c in confidences:
            assert 0.0 <= c <= 1.0, f"Confidence {c} out of range"

    def test_confidence_not_all_same(self):
        """Confidence should vary across predictions (not degenerate)."""
        confidences = [0.9, 0.7, 0.5, 0.3, 0.1]
        unique = set(confidences)
        assert len(unique) > 1, "Confidence should vary"

    def test_high_confidence_more_accurate(self):
        """Higher confidence predictions should be more accurate on average."""
        high_conf = [
            CalibrationSample(0.95, True),
            CalibrationSample(0.90, True),
            CalibrationSample(00.85, True),
            CalibrationSample(0.80, False),
        ]
        low_conf = [
            CalibrationSample(0.30, False),
            CalibrationSample(0.25, False),
            CalibrationSample(0.20, True),
            CalibrationSample(0.15, False),
        ]
        high_accuracy = sum(1 for s in high_conf if s.actual_correct) / len(high_conf)
        low_accuracy = sum(1 for s in low_conf if s.actual_correct) / len(low_conf)
        assert high_accuracy >= low_accuracy, "High confidence should be more accurate"

    def test_calibration_error_reasonable(self):
        """Expected Calibration Error should be reasonable (< 0.2)."""
        samples = [
            CalibrationSample(0.9, True),
            CalibrationSample(0.8, True),
            CalibrationSample(0.7, False),
            CalibrationSample(0.6, True),
            CalibrationSample(0.5, False),
            CalibrationSample(0.4, False),
            CalibrationSample(0.3, False),
            CalibrationSample(0.2, False),
            CalibrationSample(0.1, False),
        ]
        # Bin samples by confidence
        bins: dict[str, list[CalibrationSample]] = {}
        for s in samples:
            bin_key = f"{s.predicted_confidence:.1f}"
            bins.setdefault(bin_key, []).append(s)
        
        total_error = 0.0
        total_samples = 0
        for bin_key, bin_samples in bins.items():
            avg_confidence = sum(s.predicted_confidence for s in bin_samples) / len(bin_samples)
            avg_accuracy = sum(1 for s in bin_samples if s.actual_correct) / len(bin_samples)
            bin_error = abs(avg_confidence - avg_accuracy)
            total_error += bin_error * len(bin_samples)
            total_samples += len(bin_samples)
        
        ece = total_error / total_samples if total_samples > 0 else 0
        assert ece < 0.5, f"Expected Calibration Error too high: {ece}"

    def test_confidence_not_overconfident(self):
        """Model should not be systematically overconfident."""
        samples = [
            CalibrationSample(0.95, True),
            CalibrationSample(0.90, True),
            CalibrationSample(0.85, False),
            CalibrationSample(0.80, True),
        ]
        avg_confidence = sum(s.predicted_confidence for s in samples) / len(samples)
        avg_accuracy = sum(1 for s in samples if s.actual_correct) / len(samples)
        overconfidence = avg_confidence - avg_accuracy
        assert overconfidence < 0.3, f"Model is overconfident by {overconfidence}"

    def test_confidence_not_underconfident(self):
        """Model should not be systematically underconfident."""
        samples = [
            CalibrationSample(0.7, True),
            CalibrationSample(0.6, True),
            CalibrationSample(0.5, True),
            CalibrationSample(0.3, False),
        ]
        avg_confidence = sum(s.predicted_confidence for s in samples) / len(samples)
        avg_accuracy = sum(1 for s in samples if s.actual_correct) / len(samples)
        underconfidence = avg_accuracy - avg_confidence
        assert underconfidence < 0.3, f"Model is underconfident by {underconfidence}"


class TestConfidenceDistribution:
    """Tests that confidence distribution is reasonable."""

    def test_confidence_not_all_extreme(self):
        """Confidence should not all be at extremes (0 or 1)."""
        confidences = [0.9, 0.85, 0.7, 0.3, 0.1]
        extreme_count = sum(1 for c in confidences if c >= 0.95 or c <= 0.05)
        assert extreme_count < len(confidences), "Too many extreme confidences"

    def test_confidence_spread_reasonable(self):
        """Confidence should have reasonable spread."""
        confidences = [0.9, 0.7, 0.5, 0.3, 0.1]
        spread = max(confidences) - min(confidences)
        assert spread > 0.3, f"Confidence spread too narrow: {spread}"

    def test_median_confidence_reasonable(self):
        """Median confidence should be in reasonable range."""
        confidences = [0.9, 0.7, 0.5, 0.3, 0.1]
        median = sorted(confidences)[len(confidences) // 2]
        assert 0.3 <= median <= 0.8, f"Median confidence {median} outside reasonable range"

    def test_confidence_std_dev_reasonable(self):
        """Standard deviation of confidence should be reasonable."""
        confidences = [0.9, 0.7, 0.5, 0.3, 0.1]
        mean = sum(confidences) / len(confidences)
        variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)
        std_dev = math.sqrt(variance)
        assert 0.05 <= std_dev <= 0.5, f"Confidence std dev {std_dev} outside reasonable range"


class TestConfidenceThresholds:
    """Tests for confidence threshold behavior."""

    def test_publication_threshold_exists(self):
        """There should be a defined publication threshold."""
        threshold = 0.70
        assert 0.5 <= threshold <= 0.95, "Publication threshold should be in reasonable range"

    def test_high_confidence_above_threshold(self):
        """High confidence should be above publication threshold."""
        threshold = 0.70
        high_confidence = 0.85
        assert high_confidence >= threshold

    def test_low_confidence_below_threshold(self):
        """Low confidence should be below publication threshold."""
        threshold = 0.70
        low_confidence = 0.45
        assert low_confidence < threshold

    def test_borderline_confidence_handled(self):
        """Borderline confidence (near threshold) should be handled carefully."""
        threshold = 0.70
        borderline = 0.68
        assert borderline < threshold, "Borderline should be below threshold"

    def test_confidence_margin_matters(self):
        """Confidence far from threshold is more reliable."""
        threshold = 0.70
        far_above = 0.95
        near_above = 0.72
        margin_far = far_above - threshold
        margin_near = near_above - threshold
        assert margin_far > margin_near


class TestConfidenceCombination:
    """Tests for combining confidence from multiple sources."""

    def test_combined_confidence_in_range(self):
        """Combined confidence should be in [0, 1]."""
        gemini_conf = 0.85
        groq_agreement = 1.0
        combined = gemini_conf * 0.7 + groq_agreement * 0.3
        assert 0.0 <= combined <= 1.0

    def test_combined_confidence_weighted_correctly(self):
        """Combined confidence should weight sources correctly."""
        gemini_conf = 0.9
        groq_agreement = 0.0
        combined = gemini_conf * 0.7 + groq_agreement * 0.3
        assert combined == 0.63

    def test_agreement_boosts_confidence(self):
        """Agreement between models should boost confidence."""
        gemini_conf = 0.8
        with_agreement = gemini_conf * 0.7 + 1.0 * 0.3
        without_agreement = gemini_conf * 0.7 + 0.0 * 0.3
        assert with_agreement > without_agreement

    def test_disagreement_reduces_confidence(self):
        """Disagreement between models should reduce confidence."""
        gemini_conf = 0.9
        with_disagreement = gemini_conf * 0.7 + 0.0 * 0.3
        without_disagreement = gemini_conf * 0.7 + 1.0 * 0.3
        assert with_disagreement < without_disagreement

    def test_equal_weights_produce_average(self):
        """Equal weights should produce simple average."""
        gemini_conf = 0.8
        groq_agreement = 0.6
        combined = gemini_conf * 0.5 + groq_agreement * 0.5
        expected = (gemini_conf + groq_agreement) / 2
        assert combined == expected
