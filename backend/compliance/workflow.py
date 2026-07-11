"""Compliance orchestration entry point.

The orchestration logic lives in a single place:
``complisoc.backend.compliance.langchain_pipeline`` (a LangChain / LCEL
chain). This module preserves the historical ``process_scan_run`` name as a
thin, non-duplicating alias so existing callers (the API and the test
suite) keep working without changes.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from complisoc.backend.compliance.langchain_pipeline import run_pipeline


def process_scan_run(
    db: Session,
    *,
    target_environment: str,
    findings: list[dict],
    scanner_failures: list[dict] | None = None,
    framework: str | None = None,
) -> dict:
    return run_pipeline(
        db,
        target_environment=target_environment,
        findings=findings,
        scanner_failures=scanner_failures,
        framework=framework,
    )
