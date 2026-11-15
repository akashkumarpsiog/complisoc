"""Confidence workflow tests; these do not measure statistical calibration."""
from __future__ import annotations

from complisoc.backend.compliance.confidence import (
    PUBLICATION_THRESHOLD,
    calculate_final_confidence,
    publication_status,
)


class TestConfidenceCombination:
    def test_confidence_is_within_range_for_valid_provider_values(self):
        for gemini, groq in ((0.0, 0.0), (0.25, 0.75), (0.5, 0.5), (1.0, 1.0)):
            result = calculate_final_confidence(gemini, groq)
            assert 0.0 <= result <= 1.0

    def test_confidence_uses_production_weights(self):
        assert calculate_final_confidence(0.9, 0.0) == 0.54

    def test_groq_agreement_contributes_forty_percent(self):
        assert calculate_final_confidence(0.0, 1.0) == 0.4

    def test_gemini_confidence_contributes_sixty_percent(self):
        assert calculate_final_confidence(1.0, 0.0) == 0.6

    def test_confidence_is_rounded_to_four_decimal_places(self):
        assert calculate_final_confidence(0.123456, 0.654321) == 0.3358

    def test_agreement_increases_final_confidence(self):
        assert calculate_final_confidence(0.8, 1.0) > calculate_final_confidence(0.8, 0.0)

    def test_disagreement_reduces_final_confidence(self):
        assert calculate_final_confidence(0.9, 0.0) < calculate_final_confidence(0.9, 1.0)

    def test_zero_provider_confidence_produces_zero(self):
        assert calculate_final_confidence(0.0, 0.0) == 0.0

    def test_full_provider_confidence_produces_one(self):
        assert calculate_final_confidence(1.0, 1.0) == 1.0

    def test_low_mapping_confidence_is_not_hidden_by_agreement(self):
        assert calculate_final_confidence(0.2, 1.0) == 0.52


class TestPublicationThreshold:
    def test_threshold_matches_documented_value(self):
        assert PUBLICATION_THRESHOLD == 0.70

    def test_at_threshold_is_published(self):
        assert publication_status(PUBLICATION_THRESHOLD) == "published"

    def test_below_threshold_requires_manual_review(self):
        assert publication_status(0.6999) == "manual_review"

    def test_above_threshold_is_published(self):
        assert publication_status(0.7001) == "published"

    def test_low_confidence_is_manual_review(self):
        assert publication_status(0.45) == "manual_review"

    def test_high_confidence_is_published(self):
        assert publication_status(0.95) == "published"

    def test_agreement_can_cross_publication_threshold(self):
        assert publication_status(calculate_final_confidence(0.5, 1.0)) == "published"

    def test_disagreement_can_require_manual_review(self):
        assert publication_status(calculate_final_confidence(0.9, 0.0)) == "manual_review"

    def test_status_uses_final_confidence_not_raw_gemini_confidence(self):
        final_confidence = calculate_final_confidence(0.95, 0.0)
        assert final_confidence < PUBLICATION_THRESHOLD
        assert publication_status(final_confidence) == "manual_review"

    def test_publication_status_is_consistent_at_boundary(self):
        assert publication_status(0.70) == publication_status(PUBLICATION_THRESHOLD)
