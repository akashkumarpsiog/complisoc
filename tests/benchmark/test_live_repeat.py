"""Pytest wrapper for the multi-trial live-AI repeat evaluator.

The heavy lifting lives in ``repeat_live_runs.py``. This file is just a
test entry point so that pytest reports per-trial results in the same
JUnit XML as everything else. It is skipped by default in CI because
live AI runs need real API keys; the script can be invoked manually
when keys are present::

    set GEMINI_API_KEY=...
    set GROQ_API_KEY=...
    pytest tests/benchmark/test_live_repeat.py -v
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REPEAT_SCRIPT = pathlib.Path(__file__).resolve().parent / "repeat_live_runs.py"
OUTPUT_PATH = (
    REPO_ROOT
    / "tests"
    / "benchmark"
    / "snapshots"
    / "live_repeat_runs.json"
)


def _live_keys_present() -> bool:
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("GROQ_API_KEY"):
        return True
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return bool(os.environ.get("GEMINI_API_KEY")) and bool(os.environ.get("GROQ_API_KEY"))


@pytest.mark.skipif(
    not _live_keys_present(),
    reason="GEMINI_API_KEY and GROQ_API_KEY not set; live multi-trial run skipped",
)
def test_repeat_live_runs_meet_thresholds():
    """Run the repeat evaluator and assert all trials passed the threshold."""
    if not REPEAT_SCRIPT.exists():
        pytest.fail(f"repeat script not found: {REPEAT_SCRIPT}")

    cmd = [
        sys.executable,
        str(REPEAT_SCRIPT),
        "--trials", "3",
        "--min-f1", "0.85",
        "--max-f1-stddev", "0.10",
        "--output", str(OUTPUT_PATH),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=3600)
    assert result.returncode == 0, (
        f"repeat_live_runs.py failed (rc={result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
    )
    assert OUTPUT_PATH.exists(), f"repeat summary not produced at {OUTPUT_PATH}"
    summary = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert summary["all_run_passed"], f"some trials fell below threshold: {summary}"
    assert summary["f1_mean"] >= 0.85, f"mean F1 too low: {summary['f1_mean']}"
    assert summary["f1_stdev"] <= 0.10, f"F1 variance too high: {summary['f1_stdev']}"


@pytest.mark.skipif(
    not _live_keys_present(),
    reason="GEMINI_API_KEY and GROQ_API_KEY not set; live multi-trial summary skip",
)
def test_repeat_live_runs_summary_is_well_formed():
    """Validate the shape of the repeat-runs JSON summary file."""
    if not OUTPUT_PATH.exists():
        pytest.skip("repeat summary not produced yet; run test_repeat_live_runs_meet_thresholds first")
    summary = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    required = {"trials", "per_run", "f1_mean", "f1_stdev", "f1_min", "f1_max"}
    missing = required - set(summary.keys())
    assert not missing, f"summary missing keys: {missing}"
    assert summary["trials"] >= 1
    assert len(summary["per_run"]) == summary["trials"]
    for run in summary["per_run"]:
        assert {"precision", "recall", "f1"} <= set(run.keys()), run
