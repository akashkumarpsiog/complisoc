from collections import defaultdict

from sqlalchemy.orm import Session

from complisoc.backend.models import RawFinding, ScanRun, ScannerExecution


def ingest_findings(
    db: Session,
    *,
    target_environment: str,
    findings: list[dict],
    scanner_failures: list[dict] | None = None,
) -> tuple[ScanRun, list[RawFinding]]:
    scan_run = ScanRun(target_environment=target_environment, status="running")
    db.add(scan_run)
    db.flush()

    executions_by_scanner: dict[str, ScannerExecution] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    scanner_failures = scanner_failures or []

    try:
        for finding in findings:
            scanner_name = finding["scanner_name"]
            scanner_finding_id = finding["scanner_finding_id"]
            raw_json = finding["raw_json"]
            if not scanner_name or not scanner_finding_id or not isinstance(raw_json, dict):
                raise ValueError("Each raw finding requires scanner_name, scanner_finding_id, and object raw_json")
            grouped[scanner_name].append(finding)
    except Exception as exc:
        execution = ScannerExecution(
            scan_run_id=scan_run.id,
            scanner_name="unknown",
            status="failed",
            error_message=str(exc),
        )
        db.add(execution)
        scan_run.status = "failed"
        db.commit()
        raise

    raw_findings: list[RawFinding] = []
    for scanner_name, scanner_findings in grouped.items():
        execution = ScannerExecution(
            scan_run_id=scan_run.id,
            scanner_name=scanner_name,
            status="completed",
        )
        db.add(execution)
        db.flush()
        executions_by_scanner[scanner_name] = execution

        for finding in scanner_findings:
            raw_finding = RawFinding(
                scanner_execution_id=execution.id,
                scanner_finding_id=finding["scanner_finding_id"],
                scanner_name=scanner_name,
                raw_json=finding["raw_json"],
            )
            db.add(raw_finding)
            raw_findings.append(raw_finding)

    for failure in scanner_failures:
        scanner_name = str(failure.get("scanner_name") or "").strip()
        if not scanner_name:
            raise ValueError("Scanner failure requires scanner_name")
        execution = ScannerExecution(
            scan_run_id=scan_run.id,
            scanner_name=scanner_name,
            status="failed",
            error_message=str(failure.get("error_message") or "Scanner execution failed"),
        )
        db.add(execution)
        executions_by_scanner[scanner_name] = execution

    if not findings:
        execution = ScannerExecution(
            scan_run_id=scan_run.id,
            scanner_name="manual",
            status="completed" if not scanner_failures else "failed",
            error_message=None if not scanner_failures else "No findings were produced.",
        )
        db.add(execution)
        executions_by_scanner["manual"] = execution

    scan_run.status = "failed" if scanner_failures and not raw_findings else "completed"
    db.commit()
    db.refresh(scan_run)
    for raw_finding in raw_findings:
        db.refresh(raw_finding)
    return scan_run, raw_findings
