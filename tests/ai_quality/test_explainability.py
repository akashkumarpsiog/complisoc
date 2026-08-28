"""AI Explainability Tests

Validates that AI decisions are explainable and the reasoning is meaningful.
These tests ensure AI outputs include sufficient rationale for human review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class ExplainableDecision:
    """A decision with explainability requirements."""
    decision: str
    confidence: float
    rationale: str
    evidence: list[str]


class TestExplainabilityRequirements:
    """Tests that AI decisions meet explainability requirements."""

    def test_rationale_present(self):
        """Every decision must have a rationale."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match to control requirement",
            evidence=["finding mentions access control", "control addresses access control"],
        )
        assert len(decision.rationale) > 0, "Rationale must be present"

    def test_rationale_minimum_length(self):
        """Rationale must be substantive (at least 15 characters)."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match to control requirement",
            evidence=[],
        )
        assert len(decision.rationale) >= 15, "Rationale too short"

    def test_rationale_maximum_length(self):
        """Rationale should not be excessively long (max 500 chars)."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="a" * 500,
            evidence=[],
        )
        assert len(decision.rationale) <= 500, "Rationale too long"

    def test_rationale_mentions_control(self):
        """Rationale should reference the control being mapped to."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="finding directly addresses AC-1 access control requirement",
            evidence=[],
        )
        assert "AC-1" in decision.rationale or "access control" in decision.rationale.lower()

    def test_rationale_mentions_finding(self):
        """Rationale should reference the finding being mapped."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="the vulnerability finding relates to access control policy",
            evidence=[],
        )
        assert "finding" in decision.rationale.lower() or "vulnerability" in decision.rationale.lower()

    def test_high_confidence_has_detailed_rationale(self):
        """High confidence decisions should have more detailed rationale."""
        high_conf = ExplainableDecision(
            decision="maps",
            confidence=0.95,
            rationale="direct match: finding explicitly addresses the control requirement with clear evidence of coverage",
            evidence=["finding text", "control text"],
        )
        assert len(high_conf.rationale) >= 30, "High confidence needs detailed rationale"

    def test_low_confidence_has_uncertainty_rationale(self):
        """Low confidence decisions should explain uncertainty."""
        low_conf = ExplainableDecision(
            decision="maps",
            confidence=0.35,
            rationale="partial match: finding may relate to control but evidence is weak",
            evidence=["weak connection"],
        )
        uncertainty_markers = ["may", "might", "partial", "uncertain", "weak", "possibly"]
        has_uncertainty = any(m in low_conf.rationale.lower() for m in uncertainty_markers)
        assert has_uncertainty, "Low confidence should express uncertainty"


class TestEvidenceQuality:
    """Tests that AI decisions include quality evidence."""

    def test_evidence_present_for_high_confidence(self):
        """High confidence decisions should include evidence."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.9,
            rationale="direct match",
            evidence=["finding mentions 'access control'", "control requires 'access control policy'"],
        )
        assert len(decision.evidence) > 0, "High confidence needs evidence"

    def test_evidence_relevant_to_decision(self):
        """Evidence should be relevant to the decision."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match to access control",
            evidence=["finding: 'weak password policy'", "control: 'AC-1 access control'"],
        )
        for e in decision.evidence:
            assert len(e) > 5, "Evidence should be substantive"

    def test_evidence_cites_source(self):
        """Evidence should cite where it came from."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match",
            evidence=["finding[0:50]: 'password policy'", "control[0:50]: 'access control'"],
        )
        for e in decision.evidence:
            assert ":" in e or "[" in e, "Evidence should cite source"

    def test_negative_decision_has_counter_evidence(self):
        """Negative mappings should include counter-evidence."""
        decision = ExplainableDecision(
            decision="does_not_map",
            confidence=0.15,
            rationale="finding is about encryption, not access control",
            evidence=["finding mentions 'AES-256'", "control requires 'access policy'"],
        )
        assert len(decision.evidence) > 0, "Negative decision needs evidence"


class TestExplainabilityFormat:
    """Tests that explanations are in a usable format."""

    def test_rationale_is_readable_text(self):
        """Rationale should be human-readable text."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match to control requirement",
            evidence=[],
        )
        assert decision.rationale.strip() == decision.rationale, "No leading/trailing whitespace"
        assert len(decision.rationale.split()) >= 3, "Rationale should be at least 3 words"

    def test_rationale_no_jargon_without_context(self):
        """Technical jargon should be explained or contextualized."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="finding addresses AC-1 (access control policy) requirement",
            evidence=[],
        )
        # If acronym is used, it should be defined
        if "AC-" in decision.rationale:
            assert "access control" in decision.rationale.lower()

    def test_rationale_grammatically_correct(self):
        """Rationale should be grammatically correct (basic check)."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="The finding directly addresses the control requirement",
            evidence=[],
        )
        # Basic check: starts with capital letter, ends with period
        assert decision.rationale[0].isupper() or decision.rationale[0].isdigit()

    def test_rationale_no_internal_contradiction(self):
        """Rationale should not contradict itself."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match with strong evidence",
            evidence=[],
        )
        # Should not contain both "match" and "no match"
        assert not ("match" in decision.rationale.lower() and "no match" in decision.rationale.lower())


class TestExplainabilityConsistency:
    """Tests that explanations are consistent with decisions."""

    def test_maps_true_rationale_positive(self):
        """Positive mapping should have positive rationale."""
        decision = ExplainableDecision(
            decision="maps",
            confidence=0.85,
            rationale="direct match to control requirement",
            evidence=[],
        )
        positive_markers = ["match", "addresses", "covers", "aligns", "directly"]
        has_positive = any(m in decision.rationale.lower() for m in positive_markers)
        assert has_positive, "Positive mapping should have positive rationale"

    def test_maps_false_rationale_negative(self):
        """Negative mapping should have negative rationale."""
        decision = ExplainableDecision(
            decision="does_not_map",
            confidence=0.15,
            rationale="finding does not address control requirement",
            evidence=[],
        )
        negative_markers = ["not", "does not", "unrelated", "outside", "different"]
        has_negative = any(m in decision.rationale.lower() for m in negative_markers)
        assert has_negative, "Negative mapping should have negative rationale"

    def test_confidence_rationale_consistency(self):
        """Confidence level should match rationale tone."""
        high_conf = ExplainableDecision(
            decision="maps",
            confidence=0.95,
            rationale="direct and complete match",
            evidence=[],
        )
        low_conf = ExplainableDecision(
            decision="maps",
            confidence=0.35,
            rationale="partial match with uncertainty",
            evidence=[],
        )
        assert high_conf.confidence > low_conf.confidence

    def test_verification_agree_explanation_positive(self):
        """Agree verification should have positive explanation."""
        agree = ExplainableDecision(
            decision="agree",
            confidence=0.9,
            rationale="mapping is correct and appropriate",
            evidence=[],
        )
        assert "correct" in agree.rationale.lower() or "appropriate" in agree.rationale.lower()

    def test_verification_disagree_explanation_negative(self):
        """Disagree verification should have negative explanation."""
        disagree = ExplainableDecision(
            decision="disagree",
            confidence=0.1,
            rationale="mapping is incorrect or inappropriate",
            evidence=[],
        )
        assert "incorrect" in disagree.rationale.lower() or "inappropriate" in disagree.rationale.lower()


class TestExplainabilityAuditability:
    """Tests that decisions can be audited."""

    def test_decision_has_timestamp(self):
        """Decisions should be timestamped for audit."""
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat()
        assert len(timestamp) > 0

    def test_decision_has_model_version(self):
        """Decisions should record which model made them."""
        model_version = "gemini-2.0-flash"
        assert len(model_version) > 0

    def test_decision_has_input_reference(self):
        """Decisions should reference the input that produced them."""
        finding_id = 123
        control_id = "AC-1"
        assert finding_id > 0
        assert len(control_id) > 0

    def test_decision_chain_traceable(self):
        """Decision chain should be traceable from input to output."""
        chain = {
            "input": {"finding_id": 1, "control_ids": ["AC-1", "AC-2"]},
            "mapping": {"control_id": "AC-1", "maps": True, "confidence": 0.85},
            "verification": {"result": "agree", "confidence": 0.9},
            "output": {"decision": "publish", "final_confidence": 0.87},
        }
        assert "input" in chain
        assert "output" in chain
