from sqlalchemy.orm import Session

from complisoc.backend.compliance.candidate_narrowing import narrow_candidates
from complisoc.backend.compliance.confidence import calculate_final_confidence, publication_status
from complisoc.backend.compliance.mapping import GeminiMapper, MappingDecision
from complisoc.backend.compliance.verification import GroqVerifier, VerificationDecision
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

    try:
        mapper = GeminiMapper()
    except RuntimeError:
        mapper = None

    try:
        verifier = GroqVerifier()
    except RuntimeError:
        verifier = None

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

        if mapper is None:
            mapping = ControlMapping(
                normalized_finding_id=normalized.id,
                candidate_control_id=candidate.id,
                control_catalog_id=control.id,
                rank=1,
                mapping_model="deterministic-fallback",
                prompt_version="n/a",
                rationale="Gemini mapper unavailable; mapping deferred to manual review.",
                gemini_confidence=None,
                mapping_status="manual_review",
            )
            db.add(mapping)
            db.commit()
            db.refresh(mapping)

            review_item = ReviewQueueItem(
                control_mapping_id=mapping.id,
                status="pending",
                review_reason_code="AI_MAPPER_UNAVAILABLE",
                comments="Gemini API key is not configured.",
            )
            db.add(review_item)
            review_items.append(review_item)
            mappings.append(mapping)
            continue

        try:
            mapping_decision = mapper.map(normalized, candidate, control)
        except Exception as exc:
            mapping = ControlMapping(
                normalized_finding_id=normalized.id,
                candidate_control_id=candidate.id,
                control_catalog_id=control.id,
                rank=1,
                mapping_model="gemini-2.5-flash",
                prompt_version="mvp-v1",
                rationale=f"Gemini mapping failed: {exc}",
                gemini_confidence=None,
                mapping_status="manual_review",
            )
            db.add(mapping)
            db.commit()
            db.refresh(mapping)

            review_item = ReviewQueueItem(
                control_mapping_id=mapping.id,
                status="pending",
                review_reason_code="AI_MAPPER_FAILURE",
                comments=str(exc),
            )
            db.add(review_item)
            review_items.append(review_item)
            mappings.append(mapping)
            continue

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

        if verifier is None:
            mapping.verification_status = None
            mapping.final_confidence = mapping.gemini_confidence * 0.6
            mapping.mapping_status = publication_status(mapping.final_confidence)
            if mapping.mapping_status == "manual_review":
                review_item = ReviewQueueItem(
                    control_mapping_id=mapping.id,
                    status="pending",
                    review_reason_code="AI_VERIFIER_UNAVAILABLE",
                    comments="Groq API key is not configured; confidence degraded.",
                )
                db.add(review_item)
                review_items.append(review_item)
            db.commit()
            db.refresh(mapping)
            mappings.append(mapping)
            continue

        try:
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
            db.flush()

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
        except Exception as exc:
            mapping.verification_status = "failed"
            mapping.final_confidence = mapping.gemini_confidence * 0.6 if mapping.gemini_confidence is not None else None
            mapping.mapping_status = publication_status(mapping.final_confidence) if mapping.final_confidence is not None else "manual_review"
            record = VerificationRecord(
                control_mapping_id=mapping.id,
                verification_model=getattr(verification, "model", "groq") if 'verification' in locals() else "groq",
                prompt_version=getattr(verification, "prompt_version", "mvp-v1") if 'verification' in locals() else "mvp-v1",
                result="disagree",
                explanation=f"Verification failed: {exc}",
            )
            db.add(record)
            if mapping.mapping_status == "manual_review":
                review_item = ReviewQueueItem(
                    control_mapping_id=mapping.id,
                    status="pending",
                    review_reason_code="AI_VERIFIER_FAILURE",
                    comments=str(exc),
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
