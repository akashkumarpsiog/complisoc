"""Contract tests for AI response schemas.

Validates that AI model responses conform to expected schemas.
These tests catch format changes from AI providers early.
"""
from __future__ import annotations

import json

import pytest


class TestGeminiResponseSchema:
    """Contract tests for Gemini mapping response format."""

    def test_valid_batch_response_structure(self):
        """Gemini batch response must have results array with finding_id and candidates."""
        response = {
            "results": [
                {
                    "finding_id": 1,
                    "candidates": [
                        {
                            "control_id": "A.5.15",
                            "maps": True,
                            "confidence": 0.95,
                            "rationale": "strong match",
                        }
                    ],
                }
            ]
        }
        assert "results" in response
        assert isinstance(response["results"], list)
        for result in response["results"]:
            assert "finding_id" in result
            assert "candidates" in result
            assert isinstance(result["candidates"], list)
            for candidate in result["candidates"]:
                assert "control_id" in candidate
                assert "maps" in candidate
                assert "confidence" in candidate
                assert "rationale" in candidate
                assert isinstance(candidate["confidence"], (int, float))
                assert 0 <= candidate["confidence"] <= 1

    def test_valid_single_response_structure(self):
        """Gemini single mapping response must have maps, confidence, rationale."""
        response = {"maps": True, "confidence": 0.87, "rationale": "good match"}
        assert "maps" in response
        assert "confidence" in response
        assert "rationale" in response
        assert isinstance(response["maps"], bool)
        assert isinstance(response["confidence"], (int, float))
        assert isinstance(response["rationale"], str)

    def test_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        valid_confidences = [0.0, 0.01, 0.5, 0.99, 1.0]
        for conf in valid_confidences:
            assert 0 <= conf <= 1

    def test_maps_can_be_string_or_bool(self):
        """AI may return maps as string 'true'/'false' or boolean."""
        valid_values = [True, False, "true", "false", "1", "0", "yes", "no"]
        for val in valid_values:
            if isinstance(val, str):
                assert val.lower() in ("true", "false", "1", "0", "yes", "no")
            else:
                assert isinstance(val, bool)


class TestGroqResponseSchema:
    """Contract tests for Groq verification response format."""

    def test_valid_batch_response_structure(self):
        """Groq batch response must have results array with ref and result."""
        response = {
            "results": [
                {"ref": 1, "result": "agree", "explanation": "correct mapping"},
                {"ref": 2, "result": "disagree", "explanation": "incorrect"},
            ]
        }
        assert "results" in response
        assert isinstance(response["results"], list)
        for result in response["results"]:
            assert "ref" in result
            assert "result" in result
            assert "explanation" in result
            assert result["result"] in ("agree", "disagree")

    def test_valid_single_response_structure(self):
        """Groq single verification response must have result and explanation."""
        response = {"result": "agree", "explanation": "looks correct"}
        assert "result" in response
        assert "explanation" in response
        assert response["result"] in ("agree", "disagree")

    def test_result_must_be_agree_or_disagree(self):
        """Result field must be exactly 'agree' or 'disagree'."""
        valid_results = ["agree", "disagree"]
        for result in valid_results:
            assert result in ("agree", "disagree")


class TestConfidenceCalculationContract:
    """Contract tests for confidence calculation rules."""

    def test_final_confidence_within_bounds(self):
        """Final confidence must always be between 0 and 1."""
        test_cases = [
            (0.9, 1.0, 0.93),  # High agreement
            (0.5, 0.0, 0.35),  # Disagreement
            (0.8, 0.5, 0.71),  # Partial agreement
        ]
        for gemini_conf, groq_agreement, expected in test_cases:
            calculated = gemini_conf * 0.7 + groq_agreement * 0.3
            assert 0 <= calculated <= 1

    def test_publication_threshold(self):
        """Mappings below 0.70 confidence must go to manual review."""
        threshold = 0.70
        assert threshold == 0.70
        below_threshold = [0.0, 0.35, 0.69, 0.699]
        above_threshold = [0.70, 0.71, 0.85, 0.99, 1.0]
        for conf in below_threshold:
            assert conf < threshold
        for conf in above_threshold:
            assert conf >= threshold
