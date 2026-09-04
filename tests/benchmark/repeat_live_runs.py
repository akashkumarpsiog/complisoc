"""N-trial repeated live-AI evaluation.

The proposal §10.3 asks for *repeated* live evaluations to measure:

    * control agreement
    * confidence variance
    * abstention quality
    * publication-status drift

This script invokes ``validate_mappings.py --live`` N times in fresh
in-memory databases, captures per-run precision / recall / F1, and
asserts that:

* every individual run reaches a minimum F1,
* the mean F1 across runs is at or above the threshold,
* the standard deviation of F1 is below a stability ceiling.

Run:

    set GEMINI_API_KEY=...
    set GROQ_API_KEY=...
    python tests/benchmark/repeat_live_runs.py --trials 3 --min-f1 0.85

Exit code is 0 only when all checks pass.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import subprocess
import sys

_THIS = pathlib.Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "tests" / "benchmark" / "snapshots" / "live_repeat_runs.json"


def _parse_metrics(stdout: str) -> dict[str, float]:
    """Extract precision/recall/F1 from the validate_mappings.py CLI output.

    The validator prints metrics in the form::

        Precision          : 1.000
        Recall             : 1.000

    (F1 is computed in the JSON output file.) This function is used as
    a fallback when the JSON output file isn't produced.
    """
    import re
    metrics: dict[str, float] = {}
    for key, pattern in (
        ("precision", r"precision[^\d]*([0-9]*\.[0-9]+|[01])"),
        ("recall", r"recall[^\d]*([0-9]*\.[0-9]+|[01])"),
        ("f1", r"\bf1[^\d]*([0-9]*\.[0-9]+|[01])"),
    ):
        match = re.search(pattern, stdout, flags=re.IGNORECASE)
        if match:
            metrics[key] = float(match.group(1))
    return metrics


def run_live_trial(
    gold: pathlib.Path,
    min_precision: float,
    min_recall: float,
    output: pathlib.Path,
) -> dict[str, float]:
    """Invoke validate_mappings.py --live once and return its metrics."""
    cmd = [
        sys.executable,
        str(_THIS.parent / "validate_mappings.py"),
        "--gold", str(gold),
        "--min-precision", str(min_precision),
        "--min-recall", str(min_recall),
        "--output", str(output),
        "--live",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600)
    if result.returncode not in (0, 2):
        sys.stderr.write(
            f"validate_mappings.py --live failed (rc={result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )
        raise RuntimeError("validate_mappings.py --live failed")

    if output.exists():
        payload = json.loads(output.read_text(encoding="utf-8"))
        metrics_block = payload.get("metrics", payload)
        return {
            "precision": float(metrics_block.get("precision", 0.0)),
            "recall": float(metrics_block.get("recall", 0.0)),
            "f1": float(metrics_block.get("f1", 0.0)),
        }
    return _parse_metrics(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="N-trial repeated live-AI evaluator")
    parser.add_argument("--trials", type=int, default=3,
                        help="Number of repeated live trials (default 3)")
    parser.add_argument("--min-f1", type=float, default=0.85,
                        help="Minimum mean F1 across trials (default 0.85)")
    parser.add_argument("--max-f1-stddev", type=float, default=0.10,
                        help="Maximum F1 standard deviation across trials (default 0.10)")
    parser.add_argument("--gold", type=pathlib.Path,
                        default=_THIS.parent / "gold_standard.json")
    parser.add_argument("--min-precision", type=float, default=0.85)
    parser.add_argument("--min-recall", type=float, default=0.85)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--env-file", type=pathlib.Path, default=REPO_ROOT / ".env",
        help="Optional dotenv file to load (default .env in repo root)",
    )
    args = parser.parse_args()

    # Load .env if API keys aren't already exported.
    if (not os.environ.get("GEMINI_API_KEY")
            or not os.environ.get("GROQ_API_KEY")) and args.env_file.exists():
        for line in args.env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("GROQ_API_KEY"):
        sys.stderr.write(
            "ERROR: GEMINI_API_KEY and GROQ_API_KEY must be set in the environment\n"
        )
        return 2

    if args.trials < 1:
        sys.stderr.write("ERROR: --trials must be >= 1\n")
        return 2

    runs: list[dict[str, float]] = []
    for i in range(1, args.trials + 1):
        sys.stdout.write(f"\n=== trial {i}/{args.trials} ===\n")
        metrics = run_live_trial(
            args.gold, args.min_precision, args.min_recall, args.output,
        )
        sys.stdout.write(f"trial {i}: {metrics}\n")
        runs.append(metrics)

    f1s = [r["f1"] for r in runs]
    precisions = [r["precision"] for r in runs]
    recalls = [r["recall"] for r in runs]
    summary = {
        "trials": args.trials,
        "min_f1": args.min_f1,
        "max_f1_stddev": args.max_f1_stddev,
        "per_run": runs,
        "f1_mean": statistics.fmean(f1s),
        "f1_stdev": statistics.pstdev(f1s) if len(f1s) > 1 else 0.0,
        "f1_min": min(f1s),
        "f1_max": max(f1s),
        "precision_mean": statistics.fmean(precisions),
        "recall_mean": statistics.fmean(recalls),
        "all_run_passed": all(
            r["f1"] >= args.min_f1 and r["precision"] >= args.min_precision
            and r["recall"] >= args.min_recall
            for r in runs
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sys.stdout.write("\n=== summary ===\n")
    sys.stdout.write(json.dumps(summary, indent=2))
    sys.stdout.write("\n")

    if not summary["all_run_passed"]:
        sys.stderr.write(
            f"FAIL: at least one run below threshold F1={args.min_f1} "
            f"precision={args.min_precision} recall={args.min_recall}\n"
        )
        return 1
    if summary["f1_mean"] < args.min_f1:
        sys.stderr.write(
            f"FAIL: mean F1 {summary['f1_mean']:.4f} below {args.min_f1}\n"
        )
        return 1
    if len(f1s) > 1 and summary["f1_stdev"] > args.max_f1_stddev:
        sys.stderr.write(
            f"FAIL: F1 stdev {summary['f1_stdev']:.4f} above {args.max_f1_stddev}\n"
        )
        return 1
    sys.stdout.write("PASS: all live trials meet thresholds\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
