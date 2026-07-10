import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fpdf import FPDF
from groq import Groq
from sqlalchemy.orm import Session

from complisoc.backend.core.config import GROQ_API_KEY, GROQ_MODEL
from complisoc.backend.models import AuditBundle, ComplianceReport, ControlMapping, NormalizedFinding, RawFinding, ScanRun, ScannerExecution


ARTIFACT_ROOT = Path("artifacts")


def _write_artifact(kind: str, name: str, payload: dict[str, Any]) -> tuple[str, str]:
    directory = ARTIFACT_ROOT / kind
    directory.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, default=str, indent=2)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    path = directory / f"{name}-{digest[:12]}.json"
    path.write_text(encoded, encoding="utf-8")
    return str(path), digest


def _stable_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _scan_mappings(db: Session, scan_run_id: int) -> list[ControlMapping]:
    return (
        db.query(ControlMapping)
        .join(ControlMapping.normalized_finding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )


def _mapping_payload(mapping: ControlMapping) -> dict[str, Any]:
    finding = mapping.normalized_finding
    control = mapping.control_catalog
    raw_finding = finding.raw_finding
    return {
        "mapping_id": mapping.id,
        "status": mapping.mapping_status,
        "final_confidence": mapping.final_confidence,
        "verification_status": mapping.verification_status,
        "rationale": mapping.rationale,
        "finding": {
            "id": finding.id,
            "raw_finding_id": raw_finding.id,
            "scanner_name": finding.scanner_name,
            "severity": finding.severity,
            "finding_type": finding.finding_type,
            "resource_type": finding.resource_type,
            "resource_identifier": finding.resource_identifier,
            "title": finding.title,
            "description": finding.description,
        },
        "control": {
            "id": control.id,
            "framework_name": control.framework_name,
            "control_id": control.control_id,
            "title": control.title,
            "family": control.control_family,
        },
        "verification_records": [
            {
                "id": record.id,
                "result": record.result,
                "explanation": record.explanation,
                "timestamp": record.timestamp,
            }
            for record in mapping.verification_records
        ],
        "remediation": _remediation_text(mapping),
    }


def _remediation_text(mapping: ControlMapping) -> str:
    finding = mapping.normalized_finding
    control = mapping.control_catalog
    return (
        f"Review {finding.resource_identifier} for {finding.title}. "
        f"Prioritize remediation against {control.framework_name} {control.control_id}: {control.title}."
    )


def _severity_counts(mappings: list[ControlMapping]) -> dict[str, int]:
    severities: dict[str, int] = {}
    for mapping in mappings:
        severity = mapping.normalized_finding.severity
        severities[severity] = severities.get(severity, 0) + 1
    return severities


def _framework_counts(mappings: list[ControlMapping]) -> dict[str, int]:
    frameworks: dict[str, int] = {}
    for mapping in mappings:
        framework = mapping.control_catalog.framework_name
        frameworks[framework] = frameworks.get(framework, 0) + 1
    return frameworks


def _safe_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _top_mappings(mappings: list[ControlMapping], limit: int = 8) -> list[ControlMapping]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return sorted(
        mappings,
        key=lambda mapping: (
            severity_rank.get(mapping.normalized_finding.severity, 99),
            mapping.mapping_status != "manual_review",
            -(mapping.final_confidence or mapping.gemini_confidence or 0),
        ),
    )[:limit]


def _deterministic_narrative(scan_run_id: int, mappings: list[ControlMapping], report_type: str) -> dict[str, str]:
    published = [m for m in mappings if m.mapping_status == "published"]
    manual_review = [m for m in mappings if m.mapping_status == "manual_review"]
    critical_high = [m for m in mappings if m.normalized_finding.severity in {"critical", "high"}]
    audience_note = (
        "Engineering readers should use the appendix for remediation detail."
        if report_type == "engineering"
        else "Leadership readers should focus on posture, trend readiness, and high-severity exposure."
    )
    return {
        "executive_summary": (
            f"Scan run {scan_run_id} produced {len(mappings)} compliance mappings, "
            f"including {len(published)} published mappings and {len(manual_review)} requiring manual review."
        ),
        "risk_summary": (
            f"{len(critical_high)} critical or high severity findings should be prioritized. "
            "Manual review items should be resolved before relying on this report for audit evidence."
        ),
        "recommended_actions": (
            "Prioritize critical and high severity findings, collect remediation evidence for mapped controls, "
            "and close manual review decisions before the next audit checkpoint."
        ),
        "audience_note": audience_note,
    }


def _generate_report_narrative(scan_run_id: int, mappings: list[ControlMapping], report_type: str) -> dict[str, str]:
    fallback = _deterministic_narrative(scan_run_id, mappings, report_type)
    if not GROQ_API_KEY:
        return fallback

    client = Groq(api_key=GROQ_API_KEY)
    published = [m for m in mappings if m.mapping_status == "published"]
    manual_review = [m for m in mappings if m.mapping_status == "manual_review"]
    finding_summaries = []
    for mapping in mappings[:20]:
        finding = mapping.normalized_finding
        control = mapping.control_catalog
        finding_summaries.append(
            f"- [{finding.severity.upper()}] {finding.title} -> {control.framework_name} {control.control_id} "
            f"({mapping.mapping_status}, confidence={_safe_percent(mapping.final_confidence)})"
        )

    prompt = (
        f"Generate concise narrative snippets for a {report_type} compliance report for scan run {scan_run_id}.\n\n"
        f"Summary:\n"
        f"- Total mappings: {len(mappings)}\n"
        f"- Published: {len(published)}\n"
        f"- Manual review: {len(manual_review)}\n"
        f"- Severity counts: {_severity_counts(mappings)}\n\n"
        f"Findings mapped to controls:\n{chr(10).join(finding_summaries)}\n\n"
        "Return ONLY JSON with these string keys: executive_summary, risk_summary, recommended_actions, audience_note. "
        "Each value must be concise and professional."
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a compliance report writer. Produce short, structured JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        text = response.choices[0].message.content.strip()
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
        return {key: str(data.get(key) or fallback[key]).strip() for key in fallback}
    except Exception as exc:
        narrative = fallback.copy()
        narrative["audience_note"] = f"{fallback['audience_note']} AI narrative unavailable: {exc}"
        return narrative


def _pdf_heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _pdf_body(pdf: FPDF, text: str, size: int = 10) -> None:
    pdf.set_font("Helvetica", "", size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 6, str(text or "n/a"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _pdf_kv(pdf: FPDF, label: str, value: object) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 6, f"{label}: {value if value is not None else 'n/a'}", new_x="LMARGIN", new_y="NEXT")


def _generate_pdf(
    path: Path,
    title: str,
    narrative: dict[str, str],
    mappings: list[ControlMapping],
    report_type: str,
    scan_run_id: int,
) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Scan run {scan_run_id} | Generated {datetime.utcnow().isoformat(timespec='seconds')} UTC", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    published = [mapping for mapping in mappings if mapping.mapping_status == "published"]
    manual_review = [mapping for mapping in mappings if mapping.mapping_status == "manual_review"]

    _pdf_heading(pdf, "Executive Summary")
    _pdf_body(pdf, narrative["executive_summary"], 11)

    _pdf_heading(pdf, "Summary Metrics")
    _pdf_kv(pdf, "Total mappings", len(mappings))
    _pdf_kv(pdf, "Published", len(published))
    _pdf_kv(pdf, "Manual review", len(manual_review))
    _pdf_kv(pdf, "Severity", _severity_counts(mappings))
    _pdf_kv(pdf, "Frameworks", _framework_counts(mappings))
    pdf.ln(3)

    _pdf_heading(pdf, "Risk and Compliance Impact")
    _pdf_body(pdf, narrative["risk_summary"])
    _pdf_body(pdf, narrative["audience_note"])

    _pdf_heading(pdf, "Recommended Actions")
    _pdf_body(pdf, narrative["recommended_actions"])

    _pdf_heading(pdf, "Key Findings")
    cell_width = pdf.w - pdf.l_margin - pdf.r_margin
    for mapping in _top_mappings(mappings):
        finding = mapping.normalized_finding
        control = mapping.control_catalog
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(cell_width, 7, f"{finding.severity.upper()} - {finding.title}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(cell_width, 6, f"Resource: {finding.resource_identifier}", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(cell_width, 6, f"Control: {control.framework_name} {control.control_id} - {control.title}", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(cell_width, 6, f"Status: {mapping.mapping_status} | Confidence: {_safe_percent(mapping.final_confidence)}", new_x="LMARGIN", new_y="NEXT")
        if report_type == "engineering":
            pdf.multi_cell(cell_width, 6, f"Remediation: {_remediation_text(mapping)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    if manual_review:
        _pdf_heading(pdf, "Manual Review Required")
        for mapping in manual_review[:12]:
            finding = mapping.normalized_finding
            control = mapping.control_catalog
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(
                cell_width,
                6,
                f"Mapping #{mapping.id}: {finding.title} -> {control.framework_name} {control.control_id} "
                f"({_safe_percent(mapping.final_confidence)})",
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.ln(2)

    _pdf_heading(pdf, "Mapping Appendix")
    for mapping in mappings:
        finding = mapping.normalized_finding
        control = mapping.control_catalog
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(
            cell_width,
            5,
            f"#{mapping.id} | {finding.severity.upper()} | {finding.title} | "
            f"{control.framework_name} {control.control_id} | {mapping.mapping_status} | "
            f"{_safe_percent(mapping.final_confidence)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    pdf.output(str(path))


def generate_compliance_report(db: Session, *, scan_run_id: int, report_type: str) -> ComplianceReport:
    if report_type not in {"engineering", "leadership"}:
        raise ValueError("report_type must be engineering or leadership")

    recent = (
        db.query(ComplianceReport)
        .filter(
            ComplianceReport.scan_run_id == scan_run_id,
            ComplianceReport.report_type == report_type,
            ComplianceReport.generated_at >= datetime.utcnow() - timedelta(seconds=10),
        )
        .order_by(ComplianceReport.generated_at.desc())
        .first()
    )
    if recent is not None:
        return recent

    mappings = _scan_mappings(db, scan_run_id)
    published = [mapping for mapping in mappings if mapping.mapping_status == "published"]
    manual_review = [mapping for mapping in mappings if mapping.mapping_status == "manual_review"]
    narrative = _generate_report_narrative(scan_run_id, mappings, report_type)

    directory = ARTIFACT_ROOT / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    pdf_path = directory / f"{report_type}-scan-{scan_run_id}.pdf"
    _generate_pdf(
        pdf_path,
        f"{report_type.title()} Compliance Report - Scan #{scan_run_id}",
        narrative,
        mappings,
        report_type,
        scan_run_id,
    )

    payload = {
        "scan_run_id": scan_run_id,
        "report_type": report_type,
        "summary": {
            "total_mappings": len(mappings),
            "published_mappings": len(published),
            "manual_review_mappings": len(manual_review),
            "severity_counts": _severity_counts(mappings),
            "framework_counts": _framework_counts(mappings),
        },
        "narrative": narrative,
    }
    if report_type == "engineering":
        payload["findings"] = [_mapping_payload(mapping) for mapping in mappings]
    else:
        coverage = _framework_counts(published)
        payload["posture"] = {
            "published_decisions": len(published),
            "manual_review_count": len(manual_review),
            "severity_counts": _severity_counts(published),
            "framework_coverage": coverage,
            "trend_ready_aggregates": {
                "scan_run_id": scan_run_id,
                "mapped_controls": len({mapping.control_catalog_id for mapping in published}),
                "manual_review_mappings": len(manual_review),
            },
        }
        payload["published_mappings"] = [_mapping_payload(mapping) for mapping in published]

    _, digest = _write_artifact("reports", f"{report_type}-scan-{scan_run_id}", payload)
    report = ComplianceReport(
        scan_run_id=scan_run_id,
        report_type=report_type,
        generated_by="complisoc-ai-report",
        content_path=str(pdf_path),
        content_hash=digest,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def generate_audit_bundle(db: Session, *, scan_run_id: int) -> AuditBundle:
    scan_run = db.get(ScanRun, scan_run_id)
    if scan_run is None:
        raise ValueError("scan_run_id must reference an existing ScanRun")

    mappings = _scan_mappings(db, scan_run_id)
    raw_findings = (
        db.query(RawFinding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )
    normalized_findings = (
        db.query(NormalizedFinding)
        .join(NormalizedFinding.raw_finding)
        .join(RawFinding.scanner_execution)
        .filter(ScannerExecution.scan_run_id == scan_run_id)
        .all()
    )
    payload = {
        "scan_run": {
            "id": scan_run.id,
            "target_environment": scan_run.target_environment,
            "status": scan_run.status,
            "started_at": scan_run.started_at,
            "completed_at": scan_run.completed_at,
            "created_at": scan_run.created_at,
        },
        "raw_finding_ids": [finding.id for finding in raw_findings],
        "raw_finding_checksums": {
            str(finding.id): _stable_checksum(finding.raw_json)
            for finding in raw_findings
        },
        "normalized_findings": [
            {
                "id": finding.id,
                "raw_finding_id": finding.raw_finding_id,
                "scanner_name": finding.scanner_name,
                "finding_type": finding.finding_type,
                "resource_type": finding.resource_type,
                "resource_identifier": finding.resource_identifier,
                "severity": finding.severity,
                "title": finding.title,
                "timestamp": finding.timestamp,
            }
            for finding in normalized_findings
        ],
        "lineage": [_mapping_payload(mapping) for mapping in mappings],
    }
    path, digest = _write_artifact("audit-bundles", f"audit-bundle-scan-{scan_run_id}", payload)
    bundle = AuditBundle(
        scan_run_id=scan_run_id,
        bundle_path=path,
        checksum=digest,
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle
