"""Regression coverage for Checkov report isolation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from complisoc.backend.scanners.runners import CheckovScanner


def test_checkov_second_run_has_no_self_referential_parse_errors(tmp_path):
    """Regression for BUG-002 (../../BUG_REGISTRY.md#bug-002--checkovs-own-stdout-banner-corrupted-its-json-output)."""
    terraform = tmp_path / "main.tf"
    terraform.write_text('resource "aws_s3_bucket" "public" { bucket = "regression-public-bucket" }\n', encoding="utf-8")
    reports = []

    def fake_checkov(command, **_kwargs):
        output_dir = Path(command[command.index("--output-file-path") + 1])
        assert not output_dir.is_relative_to(tmp_path), "Checkov output must never be placed in the scanned directory"
        parsing_errors = ["checkov-report.json"] if (tmp_path / "checkov-report.json").exists() else []
        report = {
            "parsing_errors": parsing_errors,
            "results": {"failed_checks": [{
                "check_id": "CKV_AWS_18", "check_name": "S3 bucket has logging enabled",
                "resource": "aws_s3_bucket.public", "file_path": str(terraform),
                "resource_type": "aws_s3_bucket", "severity": "HIGH", "description": "Enable logging.",
            }]},
        }
        reports.append(report)
        (output_dir / "results.json").write_text(json.dumps(report), encoding="utf-8")
        return type("Proc", (), {"returncode": 1, "stdout": "Checkov banner that is not JSON", "stderr": ""})()

    with patch("complisoc.backend.scanners.runners.subprocess.run", side_effect=fake_checkov) as run:
        first_findings, first_error = CheckovScanner().run(str(tmp_path))
        second_findings, second_error = CheckovScanner().run(str(tmp_path))

    commands = [call.args[0] for call in run.call_args_list]
    assert all("--output-file-path" in command and "--quiet" in command for command in commands)
    assert not list(tmp_path.glob("*.json")), "a report in the target would be scanned on the next CI run"
    assert all(not report["parsing_errors"] for report in reports)
    assert all("checkov-report.json" not in finding["raw_json"]["resource_identifier"] for finding in second_findings)
    assert first_error is second_error is None
    assert [f["raw_json"]["resource_identifier"] for f in second_findings] == [f"{terraform}::aws_s3_bucket.public"]
    assert len(first_findings) == len(second_findings) == 1
