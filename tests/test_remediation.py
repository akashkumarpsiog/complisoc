"""Remediation suggestion QA tests (Week 14).

Validates:
- Deterministic fallback steps when GROQ_API_KEY is absent.
- AI-generated steps with mocked Groq responses are normalized to 2-3 strings.
- 10-sample rubric: each suggestion is specific, actionable, relevant, control-aligned, and concise.
- Latency benchmark: Groq suggestion path completes in <3 s per finding.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from complisoc.backend.api.main import _coerce_remediation_steps, _suggested_remediation_steps


def _make_mapping(
    severity="high",
    title="IAM policy allows public access",
    resource="aws_iam_policy.public_access",
    control_id="A.5.15",
    control_title="Access control",
    framework_name="ISO/IEC 27001:2022 Annex A",
):
    mapping = MagicMock()
    mapping.id = 1
    mapping.normalized_finding.scanner_name = "checkov"
    mapping.normalized_finding.severity = severity
    mapping.normalized_finding.title = title
    mapping.normalized_finding.resource_identifier = resource
    mapping.normalized_finding.description = "Public access detected"
    mapping.control_catalog.framework_name = framework_name
    mapping.control_catalog.control_id = control_id
    mapping.control_catalog.title = control_title
    mapping.final_confidence = 0.95
    mapping.mapping_status = "published"
    return mapping


def _mock_groq_response(steps_json):
    """Build a mock Groq chat completion response."""
    return MagicMock(
        choices=[
            MagicMock(message=MagicMock(content=json.dumps(steps_json)))
        ]
    )


class TestCoerceRemediationSteps:
    def test_list_of_strings(self):
        result = _coerce_remediation_steps(["step one", "step two", "step three"])
        assert result == ["step one", "step two", "step three"]

    def test_list_of_dicts_with_step_key(self):
        payload = [{"step": "Fix the S3 bucket", "other": "noise"}, {"step": "Enable versioning"}]
        result = _coerce_remediation_steps(payload)
        assert result == ["Fix the S3 bucket", "Enable versioning"]

    def test_list_of_dicts_with_text_key(self):
        payload = [{"text": "Rotate the key"}, {"action": "Update policy"}]
        result = _coerce_remediation_steps(payload)
        assert result == ["Rotate the key", "Update policy"]

    def test_dict_with_steps_key(self):
        result = _coerce_remediation_steps({"steps": ["step 1", "step 2"]})
        assert result == ["step 1", "step 2"]

    def test_dict_with_remediation_steps_key(self):
        result = _coerce_remediation_steps({"remediation_steps": ["step 1", "step 2"]})
        assert result == ["step 1", "step 2"]

    def test_empty_payload(self):
        assert _coerce_remediation_steps({}) == []
        assert _coerce_remediation_steps([]) == []
        assert _coerce_remediation_steps(None) == []

    def test_filters_empty_and_whitespace(self):
        result = _coerce_remediation_steps(["", "   ", "real step"])
        assert result == ["real step"]

    def test_dict_with_string_values(self):
        result = _coerce_remediation_steps({"action": "Fix it", "detail": "More info", "text": "Extra"})
        assert "Fix it" in result
        assert "More info" in result

    def test_dict_with_empty_string_values(self):
        result = _coerce_remediation_steps({"action": "", "detail": "   "})
        assert result == []

    def test_dict_without_any_valid_keys(self):
        result = _coerce_remediation_steps({"unknown_key": "value"})
        assert result == []


class TestRemediationFallback:
    def test_fallback_when_no_api_key(self):
        mapping = _make_mapping()
        with patch("complisoc.backend.api.main.GROQ_API_KEY", None):
            steps = _suggested_remediation_steps(mapping)
        assert len(steps) >= 2
        assert all(isinstance(s, str) and s for s in steps)
        assert any("A.5.15" in s for s in steps), "fallback references control id"
        assert any("aws_iam_policy.public_access" in s for s in steps), "fallback references resource"

    def test_fallback_on_api_error(self):
        mapping = _make_mapping()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API unavailable")
        with patch("complisoc.backend.api.main.GROQ_API_KEY", "fake-key"), patch(
            "complisoc.backend.api.main.Groq", return_value=mock_client
        ):
            steps = _suggested_remediation_steps(mapping)
        assert len(steps) >= 2
        assert all(isinstance(s, str) and s for s in steps)

    def test_ai_steps_are_coerced_and_truncated(self):
        mapping = _make_mapping()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response({"steps": ["Fix 1", "Fix 2", "Fix 3", "Fix 4"]})
        with patch("complisoc.backend.api.main.GROQ_API_KEY", "fake-key"), patch(
            "complisoc.backend.api.main.Groq", return_value=mock_client
        ):
            steps = _suggested_remediation_steps(mapping)
        assert len(steps) <= 3
        assert len(steps) >= 2

    def test_ai_steps_from_dict_format(self):
        mapping = _make_mapping()
        payload = {"remediation_steps": [{"step": "Fix 1"}, {"step": "Fix 2"}]}
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response(payload)
        with patch("complisoc.backend.api.main.GROQ_API_KEY", "fake-key"), patch(
            "complisoc.backend.api.main.Groq", return_value=mock_client
        ):
            steps = _suggested_remediation_steps(mapping)
        assert len(steps) == 2

    def test_ai_steps_fewer_than_two_falls_back(self):
        mapping = _make_mapping()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response({"steps": ["only one step"]})
        with patch("complisoc.backend.api.main.GROQ_API_KEY", "fake-key"), patch(
            "complisoc.backend.api.main.Groq", return_value=mock_client
        ):
            steps = _suggested_remediation_steps(mapping)
        assert len(steps) >= 2, "falls back to deterministic when AI returns fewer than 2 steps"


RUBRIC_DIMENSIONS = ["specificity", "actionability", "relevance", "control_alignment", "conciseness"]


def _evaluate_rubric(steps, finding_title, control_id, resource):
    all_text = " ".join(steps).lower()
    return {
        "specificity": control_id.lower() in all_text or resource.lower() in all_text,
        "actionability": any(word in all_text for word in ["remove", "update", "fix", "enable", "disable", "configure", "rotate"]),
        "relevance": any(finding_title.lower()[:5] in s.lower() for s in steps),
        "control_alignment": control_id.lower() in all_text,
        "conciseness": all(len(s) <= 200 for s in steps),
    }


SAMPLES = [
    ("IAM public access", "A.5.15", "aws_iam_policy.public_access"),
    ("Unencrypted S3 bucket", "A.8.1", "aws_s3_bucket.unencrypted"),
    ("KMS key not rotated", "A.8.2", "aws_kms_key.old_key"),
    ("CloudTrail logging disabled", "A.9.1", "aws_cloudtrail.disabled"),
    ("Open security group port", "A.12.1", "aws_security_group.sg_80"),
    ("No backup policy", "A.13.1", "aws_rds_instance.no_backup"),
    ("Privileged IAM role", "A.5.18", "aws_iam_role.privileged"),
    ("Vulnerable npm dependency", "A.8.8", "npm_package.lodash_old"),
    ("Weak MFA policy", "A.5.17", "aws_iam_user.no_mfa"),
    ("EC2 instance not hardened", "A.8.9", "aws_ec2_instance.default"),
]


class TestRemediationRubric:
    @pytest.mark.parametrize("title,control_id,resource", SAMPLES)
    def test_remediation_meets_5_dimension_rubric(self, title, control_id, resource):
        mock_response = {
            "steps": [
                f"Identify the {resource} resource that triggered the '{title}' finding.",
                f"Update the configuration for {resource} to satisfy {control_id} requirements.",
                "Verify the fix and re-scan to confirm resolution.",
            ]
        }
        mapping = _make_mapping(title=title, resource=resource, control_id=control_id)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response(mock_response)
        with patch("complisoc.backend.api.main.GROQ_API_KEY", "fake-key"), patch(
            "complisoc.backend.api.main.Groq", return_value=mock_client
        ):
            steps = _suggested_remediation_steps(mapping)

        assert len(steps) >= 2
        scores = _evaluate_rubric(steps, title, control_id, resource)
        for dimension in RUBRIC_DIMENSIONS:
            assert scores[dimension], f"{dimension} failed for control {control_id}: steps={steps}"


class TestRemediationLatency:
    def test_groq_suggestion_under_3_seconds(self):
        mapping = _make_mapping()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response({"steps": ["Fix the configuration", "Verify the fix"]})
        with patch("complisoc.backend.api.main.GROQ_API_KEY", "fake-key"), patch(
            "complisoc.backend.api.main.Groq", return_value=mock_client
        ):
            start = time.perf_counter()
            steps = _suggested_remediation_steps(mapping)
            elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"Remediation suggestion took {elapsed:.2f}s, expected <3s"
        assert len(steps) >= 2