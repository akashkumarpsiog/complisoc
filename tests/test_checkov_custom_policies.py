from pathlib import Path

import pytest
from unittest.mock import patch

from complisoc.backend.scanners import runners


def test_checkov_command_includes_external_checks_dir_when_present():
    scanner = runners.CheckovScanner()
    expected = str(
        Path(__file__).resolve().parent.parent / "scan_targets" / "checkov_policies"
    )
    cmd = scanner._command(".")
    assert "--external-checks-dir" in cmd
    assert expected in cmd


def test_checkov_command_omits_external_checks_dir_when_missing():
    scanner = runners.CheckovScanner()
    with patch.object(runners.Path, "is_dir", return_value=False):
        cmd = scanner._command(".")
    assert "--external-checks-dir" not in cmd


def test_custom_policy_files_exist_and_have_required_metadata():
    policy_dir = Path(__file__).resolve().parent.parent / "scan_targets" / "checkov_policies"
    files = sorted(policy_dir.glob("*.yaml"))
    assert len(files) >= 3, f"expected >=3 custom policies, found {len(files)}"
    required_ids = {"CKV_COMPLISOC_001", "CKV_COMPLISOC_002", "CKV_COMPLISOC_003"}
    found_ids = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "metadata:" in text, f"{path.name} missing metadata"
        assert "definition:" in text, f"{path.name} missing definition"
        for line in text.splitlines():
            if line.strip().startswith("id:"):
                found_ids.add(line.split(":", 1)[1].strip())
    assert required_ids == found_ids, f"missing policies: {required_ids - found_ids}"
