"""Regression coverage for Trivy scan scope."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from complisoc.backend.scanners.runners import TrivyScanner


def test_trivy_reports_terraform_misconfiguration_when_misconfig_scanner_is_enabled(tmp_path):
    """Regression for BUG-001 (../../BUG_REGISTRY.md#bug-001--trivy-silently-omitted-iac-misconfigurations)."""
    terraform = tmp_path / "public_bucket.tf"
    terraform.write_text(
        'resource "aws_s3_bucket" "public" { bucket = "regression-public-bucket" }\n'
        'resource "aws_s3_bucket_public_access_block" "public" {\n'
        '  bucket = aws_s3_bucket.public.id\n'
        '  block_public_acls = false\n'
        '}\n',
        encoding="utf-8",
    )

    def fake_trivy(command, **_kwargs):
        scanners = command[command.index("--scanners") + 1] if "--scanners" in command else "vuln,secret"
        misconfigs = []
        if "misconfig" in scanners.split(","):
            misconfigs = [{
                "ID": "AVD-AWS-0088",
                "Type": "terraform",
                "Severity": "HIGH",
                "Title": "S3 bucket allows public ACLs",
                "Message": "Public ACLs must be blocked.",
                "CauseMetadata": {"Filepath": str(terraform), "Resource": "aws_s3_bucket_public_access_block.public"},
            }]
        return type("Proc", (), {"returncode": 0, "stdout": json.dumps({"Results": [{"Target": str(terraform), "Type": "terraform", "Misconfigurations": misconfigs}]}), "stderr": ""})()

    with patch("complisoc.backend.scanners.runners.subprocess.run", side_effect=fake_trivy) as run:
        findings, error = TrivyScanner().run(str(tmp_path))

    command = run.call_args.args[0]
    assert command[command.index("--scanners") + 1].split(",") == ["misconfig", "vuln"]
    assert error is None
    assert [finding["raw_json"]["finding_type"] for finding in findings] == ["AVD-AWS-0088"]
    assert findings[0]["raw_json"]["resource_identifier"] == f"{terraform}::aws_s3_bucket_public_access_block.public"
