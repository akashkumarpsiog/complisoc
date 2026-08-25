"""Regression coverage for Gemini batch JSON configuration."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from complisoc.backend.compliance.mapping import GeminiMapper
from complisoc.backend.models import CandidateControl, ControlCatalog, NormalizedFinding


def test_gemini_batch_uses_json_mime_type_without_version_fragile_response_schema():
    """Regression for BUG-004 (../../BUG_REGISTRY.md#bug-004--gemini-batch-mapping-call-failing-across-all-retries)."""
    control = ControlCatalog(control_id="A.5.15", framework_name="ISO 27001", framework_version="2022", control_family="Access", title="Access control", description="Limit access.", source_url="https://example.test/control", active_status=True)
    finding = NormalizedFinding(id=42, scanner_name="trivy", finding_type="public-access", resource_type="aws_s3_bucket", resource_identifier="main.tf::aws_s3_bucket.public", severity="high", title="Public S3 bucket")
    candidate = CandidateControl(control_catalog=control, match_score=0.9)
    response = {"results": [{"finding_id": 42, "candidates": [{"control_id": "A.5.15", "maps": True, "confidence": 0.93, "rationale": "Public access violates access control."}]}]}
    client = MagicMock()
    client.models.generate_content.return_value.text = json.dumps(response)

    with patch("complisoc.backend.compliance.mapping.GEMINI_API_KEY", "test-key"), patch(
        "complisoc.backend.compliance.mapping.genai.Client", return_value=client
    ), patch("complisoc.backend.compliance.mapping.types.GenerateContentConfig") as config_factory:
        # Avoid response_schema: SDK Schema/Type construction is version-fragile.
        result = GeminiMapper().map_batch([(finding, [candidate])])

    assert result[42][0].control_id == "A.5.15"
    assert result[42][0].maps is True
    assert result[42][0].confidence == 0.93
    config_kwargs = config_factory.call_args.kwargs
    assert config_kwargs["response_mime_type"] == "application/json"
    assert "response_schema" not in config_kwargs
