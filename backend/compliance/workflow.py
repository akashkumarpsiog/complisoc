from sqlalchemy.orm import Session

from complisoc.backend.compliance.candidate_narrowing import narrow_candidates
from complisoc.backend.compliance.confidence import calculate_final_confidence, publication_status
from complisoc.backend.compliance.mapping import GeminiMapper
from complisoc.backend.compliance.verification import GroqVerifier
from complisoc.backend.models import ControlMapping, NormalizedFinding, ReviewQueueItem, VerificationRecord
from complisoc.backend.normalization.normalizer import normalize_raw_finding
from complisoc.backend.scanners.ingestion import ingest_findings


def process_scan_run(
    db: Session,
    *,
    target_environment: str,
    findings: list[dict],
    scanner_failures: list[dict] | None = None,
    framework: str | None = None,
) -> dict:
    scan_run, raw_findings = ingest_findings(
        db,
        target_environment=target_environment,
        findings=findings,
        scanner_failures=scanner_failures,
    )

    normalized_findings: list[NormalizedFinding] = []
    mappings: list[ControlMapping] = []
    review_items: list[ReviewQueueItem] = []

    mapper = GeminiMapper()
    verifier = GroqVerifier()

    for raw_finding in raw_findings:
        normalized = normalize_raw_finding(db, raw_finding)
        normalized_findings.append(normalized)
        candidates = narrow_candidates(db, normalized, framework=framework)
        if not candidates:
            continue

        candidate = candidates[0]
        control = candidate.control_catalog
        if control is None:
            raise ValueError("Candidate control must reference ControlCatalog")

        mapping_decision = mapper.map(normalized, candidate, control)
        mapping = ControlMapping(
            normalized_finding_id=normalized.id,
            candidate_control_id=candidate.id,
            control_catalog_id=control.id,
            rank=1,
            mapping_model=mapping_decision.model,
            prompt_version=mapping_decision.prompt_version,
            rationale=mapping_decision.rationale,
            gemini_confidence=mapping_decision.confidence,
            mapping_status="validated",
        )
        db.add(mapping)
        db.commit()
        db.refresh(mapping)

        verification = verifier.verify(normalized, mapping, control)
        final_confidence = calculate_final_confidence(
            mapping.gemini_confidence or 0,
            verification.agreement_value,
        )
        mapping.verification_status = verification.result
        mapping.final_confidence = final_confidence
        mapping.mapping_status = publication_status(final_confidence)

        record = VerificationRecord(
            control_mapping_id=mapping.id,
            verification_model=verification.model,
            prompt_version=verification.prompt_version,
            result=verification.result,
            explanation=verification.explanation,
        )
        db.add(record)

        if mapping.mapping_status == "manual_review":
            review_item = ReviewQueueItem(
                control_mapping_id=mapping.id,
                status="pending",
                review_reason_code="LOW_CONFIDENCE",
                comments=f"Final confidence {final_confidence:.2f} is below publication threshold.",
            )
            db.add(review_item)
            review_items.append(review_item)

        db.commit()
        db.refresh(mapping)
        mappings.append(mapping)

    return {
        "scan_run": scan_run,
        "raw_findings": raw_findings,
        "normalized_findings": normalized_findings,
        "mappings": mappings,
        "review_items": review_items,
    }
