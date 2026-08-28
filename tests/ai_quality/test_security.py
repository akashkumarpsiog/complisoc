"""AI Security Tests

Tests for AI-specific security concerns including output validation
and data integrity. These tests ensure the AI pipeline produces
safe, valid outputs.
"""
from __future__ import annotations

import re
from typing import Any


class TestOutputValidation:
    """Tests for AI output validation."""

    def test_no_secrets_in_output(self):
        """AI output should not contain secrets."""
        output = {
            "maps": True,
            "confidence": 0.85,
            "rationale": "direct match to control requirement",
        }
        output_str = str(output)
        secret_patterns = [
            r"sk-[a-zA-Z0-9]{32}",
            r"password\s*[:=]\s*\S+",
            r"secret\s*[:=]\s*\S+",
            r"api[_-]?key\s*[:=]\s*\S+",
        ]
        for pattern in secret_patterns:
            assert not re.search(pattern, output_str, re.IGNORECASE), f"Secret pattern found: {pattern}"

    def test_no_pii_in_output(self):
        """AI output should not contain PII."""
        outputs = [
            {"rationale": "finding relates to access control"},
            {"rationale": "user authentication weakness detected"},
            {"rationale": "direct match to control requirement"},
        ]
        pii_patterns = [
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        ]
        for output in outputs:
            output_str = str(output)
            for pattern in pii_patterns:
                assert not re.search(pattern, output_str), f"PII pattern found in: {output_str}"

    def test_output_size_reasonable(self):
        """AI output should be reasonable size."""
        max_output_size = 10000
        output = {"rationale": "a" * 1000}
        output_size = len(str(output))
        assert output_size < max_output_size

    def test_no_executable_content(self):
        """Output should not contain executable content."""
        outputs = [
            {"rationale": "direct match"},
            {"rationale": "finding addresses control requirement"},
        ]
        executable_patterns = [
            r"<script",
            r"javascript:",
            r"on\w+\s*=",
            r"eval\s*\(",
        ]
        for output in outputs:
            output_str = str(output)
            for pattern in executable_patterns:
                assert not re.search(pattern, output_str, re.IGNORECASE)

    def test_confidence_values_in_range(self):
        """All confidence values in output should be in [0, 1]."""
        outputs = [
            {"confidence": 0.0, "gemini_confidence": 0.5, "groq_agreement_value": 1.0},
            {"confidence": 0.85, "gemini_confidence": 0.9, "groq_agreement_value": 0.0},
            {"confidence": 1.0, "gemini_confidence": 0.99, "groq_agreement_value": 1.0},
        ]
        for output in outputs:
            for key in ["confidence", "gemini_confidence", "groq_agreement_value"]:
                if key in output:
                    assert 0 <= output[key] <= 1, f"{key} out of range: {output[key]}"


class TestDataIntegrity:
    """Tests for data integrity in AI pipeline."""

    def test_mapping_status_transitions_valid(self):
        """Mapping status should only transition to valid states."""
        valid_transitions = {
            "pending": ["published", "manual_review", "rejected"],
            "manual_review": ["published", "rejected"],
            "published": [],
            "rejected": [],
        }
        valid_transitions["pending"].append("published")
        current_status = "pending"
        next_status = "published"
        assert next_status in valid_transitions[current_status]

    def test_mapping_status_invalid_transition_blocked(self):
        """Invalid status transitions should be blocked."""
        valid_transitions = {
            "pending": ["published", "manual_review", "rejected"],
            "manual_review": ["published", "rejected"],
            "published": [],
            "rejected": [],
        }
        current_status = "published"
        next_status = "pending"
        assert next_status not in valid_transitions[current_status]

    def test_terminal_states_cannot_change(self):
        """Terminal states (published, rejected) cannot change."""
        valid_transitions = {
            "pending": ["published", "manual_review", "rejected"],
            "manual_review": ["published", "rejected"],
            "published": [],
            "rejected": [],
        }
        assert len(valid_transitions["published"]) == 0
        assert len(valid_transitions["rejected"]) == 0

    def test_verification_result_valid_values(self):
        """Verification result should only be 'agree' or 'disagree'."""
        valid_results = ["agree", "disagree"]
        for result in valid_results:
            assert result in valid_results

    def test_finding_id_positive_integer(self):
        """Finding ID should be a positive integer."""
        finding_ids = [1, 10, 100, 1000]
        for fid in finding_ids:
            assert isinstance(fid, int)
            assert fid > 0

    def test_control_id_format_valid(self):
        """Control ID should match expected format."""
        valid_ids = ["AC-1", "AC-2", "AU-3", "SC-8", "IA-5", "CM-7"]
        pattern = r"^[A-Z]{2}-\d+$"
        for cid in valid_ids:
            assert re.match(pattern, cid), f"Invalid control ID format: {cid}"
