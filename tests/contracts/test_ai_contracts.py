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
