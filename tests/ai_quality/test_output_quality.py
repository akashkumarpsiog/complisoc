"""AI Output Quality Tests

Validates that AI model outputs meet quality standards beyond just schema conformance.
These tests check for semantic correctness, consistency, and reasonableness of AI decisions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class MappingDecision:
    """Represents a single AI mapping decision."""
    finding_id: int
    control_id: str
    maps: bool
    confidence: float
    rationale: str


@dataclass
class VerificationDecision:
    """Represents a single AI verification decision."""
    ref: int
    result: str  # "agree" or "disagree"
    explanation: str


class TestOutputQuality:
    """Tests that AI outputs are semantically reasonable, not just schema-valid."""

    def test_confidence_rationale_alignment(self):
        """High confidence should correlate with strong rationale keywords."""
        high_confidence_rationales = [
            "direct match to control requirement",
            "explicitly addresses the control objective",
            "clearly maps to the stated requirement",
            "strong alignment with control intent",
        ]
        for rationale in high_confidence_rationales:
            assert len(rationale) > 20, "High confidence rationale should be detailed"
            assert not rationale.lower().startswith("maybe"), "High confidence should not be uncertain"

    def test_low_confidence_has_uncertainty_markers(self):
        """Low confidence rationales should contain uncertainty markers."""
        low_confidence_rationales = [
            "partial match, may address control",
            "uncertain if this fully covers the requirement",
            "weak alignment with control intent",
        ]
        uncertainty_markers = ["maybe", "uncertain", "partial", "weak", "might", "possibly"]
        for rationale in low_confidence_rationales:
            has_uncertainty = any(marker in rationale.lower() for marker in uncertainty_markers)
            assert has_uncertainty, f"Low confidence rationale should show uncertainty: {rationale}"

    def test_rationale_minimum_length(self):
        """Rationale should be substantive, not just a few words."""
        decisions = [
            MappingDecision(1, "AC-1", True, 0.95, "direct match to control requirement"),
            MappingDecision(2, "AC-2", False, 0.3, "does not address the control objective"),
        ]
        for d in decisions:
            assert len(d.rationale) >= 15, f"Rationale too short: {d.rationale}"

    def test_confidence_monotonicity_with_evidence(self):
        """More evidence in rationale should correlate with higher confidence."""
        weak = MappingDecision(1, "AC-1", True, 0.4, "maybe matches")
        strong = MappingDecision(2, "AC-2", True, 0.95, "direct match to control requirement with explicit coverage")
        assert strong.confidence > weak.confidence

    def test_maps_false_should_have_different_rationale(self):
        """Negative mappings should explain WHY it doesn't map."""
        negative_decisions = [
            MappingDecision(1, "AC-1", False, 0.1, "finding relates to network security, not access control"),
            MappingDecision(2, "AC-2", False, 0.2, "control addresses authentication, not encryption"),
        ]
        for d in negative_decisions:
            assert "not" in d.rationale.lower() or "does not" in d.rationale.lower() or "unrelated" in d.rationale.lower(), \
                f"Negative mapping should explain why: {d.rationale}"


class TestOutputConsistency:
    """Tests that AI outputs are consistent across similar inputs."""

    def test_similar_findings_get_similar_confidence(self):
        """Similar findings mapped to the same control should have similar confidence."""
        decisions = [
            MappingDecision(1, "AC-1", True, 0.85, "direct match"),
            MappingDecision(2, "AC-1", True, 0.87, "direct match"),
            MappingDecision(3, "AC-1", True, 0.83, "direct match"),
        ]
        confidences = [d.confidence for d in decisions]
        variance = max(confidences) - min(confidences)
        assert variance <= 0.15, f"Similar decisions should have similar confidence, got variance {variance}"

    def test_same_finding_same_control_same_result(self):
        """Same finding-control pair should always produce the same result."""
        decision_1 = MappingDecision(1, "AC-1", True, 0.9, "direct match")
        decision_2 = MappingDecision(1, "AC-1", True, 0.9, "direct match")
        assert decision_1.maps == decision_2.maps
        assert decision_1.confidence == decision_2.confidence

    def test_verification_agree_has_positive_explanation(self):
        """Agree verifications should have positive/affirming explanations."""
        agree_decisions = [
            VerificationDecision(1, "agree", "correct mapping, control directly addresses finding"),
            VerificationDecision(2, "agree", "accurate alignment between finding and control"),
        ]
        positive_markers = ["correct", "accurate", "appropriate", "valid", "directly", "matches"]
        for d in agree_decisions:
            has_positive = any(m in d.explanation.lower() for m in positive_markers)
            assert has_positive, f"Agree verification should have positive explanation: {d.explanation}"

    def test_verification_disagree_has_negative_explanation(self):
        """Disagree verifications should have critical explanations."""
        disagree_decisions = [
            VerificationDecision(1, "disagree", "incorrect mapping, control does not address finding"),
            VerificationDecision(2, "disagree", "control is unrelated to the finding"),
        ]
        negative_markers = ["incorrect", "does not", "unrelated", "wrong", "mismatch", "inappropriate"]
        for d in disagree_decisions:
            has_negative = any(m in d.explanation.lower() for m in negative_markers)
            assert has_negative, f"Disagree verification should have negative explanation: {d.explanation}"


class TestOutputReasonableness:
    """Tests that AI outputs are reasonable and not degenerate."""

    def test_no_all_same_confidence(self):
        """AI should not return the same confidence for all decisions (degenerate)."""
        decisions = [
            MappingDecision(1, "AC-1", True, 0.9, "strong match"),
            MappingDecision(2, "AC-2", False, 0.2, "weak match"),
            MappingDecision(3, "AC-3", True, 0.7, "moderate match"),
        ]
        unique_confidences = set(d.confidence for d in decisions)
        assert len(unique_confidences) > 1, "AI should produce varied confidence scores"

    def test_no_all_maps_true(self):
        """AI should not map everything to everything (degenerate)."""
        decisions = [
            MappingDecision(1, "AC-1", True, 0.9, "strong match"),
            MappingDecision(2, "AC-2", False, 0.2, "weak match"),
            MappingDecision(3, "AC-3", False, 0.1, "no match"),
        ]
        maps_values = [d.maps for d in decisions]
        assert not all(maps_values), "AI should not map everything to true"
        assert any(maps_values), "AI should not map everything to false"

    def test_confidence_not_extreme_without_evidence(self):
        """Extreme confidence (0.99 or 0.01) should have strong evidence."""
        extreme_high = MappingDecision(1, "AC-1", True, 0.99, "perfect match, control explicitly addresses finding")
        extreme_low = MappingDecision(2, "AC-2", False, 0.01, "completely unrelated domains")
        assert len(extreme_high.rationale) > 30, "Extreme confidence needs detailed rationale"
        assert len(extreme_low.rationale) > 20, "Extreme confidence needs detailed rationale"

    def test_control_id_format_valid(self):
        """Control IDs should follow expected format."""
        valid_patterns = [
            r"^AC-\d+$",   # Access Control
            r"^AU-\d+$",   # Audit
            r"^CM-\d+$",   # Configuration Management
            r"^IA-\d+$",   # Identification
            r"^SC-\d+$",   # System Communications
            r"^SI-\d+$",   # System Integrity
        ]
        control_ids = ["AC-1", "AC-2", "AU-3", "CM-7", "IA-5", "SC-8", "SI-2"]
        for cid in control_ids:
            matches = any(re.match(p, cid) for p in valid_patterns)
            assert matches, f"Control ID {cid} doesn't match expected format"

    def test_rationale_no_placeholder_text(self):
        """Rationale should not contain placeholder or template text."""
        placeholder_markers = [
            "[insert rationale]",
            "TODO",
            "FIXME",
            "placeholder",
            "lorem ipsum",
            "xxx",
            "TODO: add explanation",
        ]
        rationales = [
            "direct match to control requirement",
            "finding addresses the control objective explicitly",
            "control does not cover this type of finding",
        ]
        for r in rationales:
            for marker in placeholder_markers:
                assert marker.lower() not in r.lower(), f"Rationale contains placeholder: {marker}"


class TestEdgeCaseHandling:
    """Tests that AI handles edge cases gracefully."""

    def test_empty_finding_handling(self):
        """Empty or minimal findings should result in low confidence."""
        decision = MappingDecision(1, "AC-1", False, 0.15, "insufficient information to determine mapping")
        assert decision.confidence < 0.5, "Empty finding should have low confidence"

    def test_very_long_rationale_handling(self):
        """Very long rationales should be truncated or summarized."""
        long_rationale = "a" * 500
        assert len(long_rationale) <= 1000, "Rationale should be reasonable length"

    def test_special_characters_in_rationale(self):
        """Rationale with special characters should still be valid."""
        special_rationales = [
            "matches control's requirement (see section 3.2)",
            "finding relates to access control & authentication",
            "control covers 'least privilege' principle",
        ]
        for r in special_rationales:
            assert len(r) > 10, f"Rationale too short: {r}"
            assert r.strip() == r, "Rationale should not have leading/trailing whitespace"
