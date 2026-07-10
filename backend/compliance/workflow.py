from sqlalchemy.orm import Session

from complisoc.backend.compliance.candidate_narrowing import narrow_candidates
from complisoc.backend.compliance.confidence import calculate_final_confidence, publication_status
from complisoc.backend.compliance.mapping import CandidateDecision, GeminiMapper
from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification
from complisoc.backend.core.config import PROMPT_VERSION
from complisoc.backend.models import CandidateControl, ControlMapping, NormalizedFinding, ReviewQueueItem, VerificationRecord
from complisoc.backend.normalization.normalizer import normalize_raw_finding
from complisoc.backend.scanners.ingestion import ingest_findings


MAX_CANDIDATES_PER_FINDING = 3


def _add_review_item(review_items: list[ReviewQueueItem], mapping: ControlMapping, code: str, comments: str) -> None:
    review_items.append(
        ReviewQueueItem(
            control_mapping_id=mapping.id,
            status="pending",
            review_reason_code=code,
            comments=comments,
        )
    )


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
    failures: list[dict] = []
    candidates_by_finding: dict[int, list[CandidateControl]] = {}
    batch_input: list[tuple[NormalizedFinding, list[CandidateControl]]] = []

    for raw_finding in raw_findings:
        try:
            normalized = normalize_raw_finding(db, raw_finding)
            normalized_findings.append(normalized)
            candidates = narrow_candidates(db, normalized, framework=framework)
            if not candidates:
                failures.append({"raw_finding_id": raw_finding.id, "error": "No candidate controls matched."})
                continue
            candidates_by_finding[normalized.id] = candidates
            top_candidates = [
                candidate for candidate in candidates[:MAX_CANDIDATES_PER_FINDING]
                if candidate.control_catalog is not None
            ]
            if top_candidates:
                batch_input.append((normalized, top_candidates))
        except Exception as exc:
            db.rollback()
            failures.append({"raw_finding_id": raw_finding.id, "error": str(exc)})

    try:
        mapper = GeminiMapper()
    except RuntimeError as exc:
        mapper = None
        gemini_batch_error = str(exc)
    else:
        gemini_batch_error = None

    batch_decisions: dict[int, list[CandidateDecision]] = {}
    gemini_failed = False
    if mapper is not None and batch_input:
        try:
            batch_decisions = mapper.map_batch(batch_input)
        except Exception as exc:
            gemini_batch_error = str(exc)
            gemini_failed = True

    findings_by_id = {finding.id: finding for finding in normalized_findings}
    pending_verifications: list[PendingVerification] = []
    ref_to_mapping: dict[int, ControlMapping] = {}
    ref = 0

    for finding_id, candidates in candidates_by_finding.items():
        finding = findings_by_id[finding_id]
        top_candidate = candidates[0]
        top_control = top_candidate.control_catalog
        if top_control is None:
            failures.append({"finding_id": finding_id, "error": "Top candidate missing control catalog."})
            continue

        if mapper is None:
            mapping = ControlMapping(
                normalized_finding_id=finding.id,
                candidate_control_id=top_candidate.id,
                control_catalog_id=top_control.id,
                rank=top_candidate.rank or 1,
                mapping_model="gemini-batch",
                prompt_version=PROMPT_VERSION,
                rationale=f"Gemini mapper unavailable; API failed: {gemini_batch_error}",
                gemini_confidence=None,
                verification_status=None,
                final_confidence=None,
                mapping_status="manual_review",
            )
            db.add(mapping)
            db.flush()
            mappings.append(mapping)
            _add_review_item(
                review_items,
                mapping,
                "AI_MAPPER_FAILURE",
                gemini_batch_error or "Gemini API key is not configured.",
            )
            continue

        if gemini_failed:
            mapping = ControlMapping(
                normalized_finding_id=finding.id,
                candidate_control_id=top_candidate.id,
                control_catalog_id=top_control.id,
                rank=top_candidate.rank or 1,
                mapping_model="gemini-batch",
                prompt_version=PROMPT_VERSION,
                rationale=f"Gemini batch mapping failed: {gemini_batch_error}",
                gemini_confidence=None,
                verification_status=None,
                final_confidence=None,
                mapping_status="manual_review",
            )
            db.add(mapping)
            db.flush()
            mappings.append(mapping)
            _add_review_item(
                review_items,
                mapping,
                "AI_MAPPER_FAILURE",
                gemini_batch_error or "Gemini batch mapping failed.",
            )
            continue

        decisions = batch_decisions.get(finding_id)
        if not decisions:
            mapping = ControlMapping(
                normalized_finding_id=finding.id,
                candidate_control_id=top_candidate.id,
                control_catalog_id=top_control.id,
                rank=top_candidate.rank or 1,
                mapping_model="gemini-batch",
                prompt_version=PROMPT_VERSION,
                rationale="Gemini batch mapping returned no result for this finding.",
                gemini_confidence=None,
                verification_status=None,
                final_confidence=None,
                mapping_status="manual_review",
            )
            db.add(mapping)
            db.flush()
            mappings.append(mapping)
            _add_review_item(
                review_items,
                mapping,
                "AI_MAPPER_FAILURE",
                "No result returned for this finding in the batch response.",
            )
            continue

        decision_by_control = {decision.control_id: decision for decision in decisions}
        chosen: tuple[CandidateControl, CandidateDecision] | None = None
        for candidate in candidates[:MAX_CANDIDATES_PER_FINDING]:
            control = candidate.control_catalog
            if control is None:
                continue
            decision = decision_by_control.get(control.control_id)
            if decision is not None and decision.maps:
                chosen = (candidate, decision)
                break

        if chosen is None:
            best_guess = decision_by_control.get(top_control.control_id)
            confidence = best_guess.confidence if best_guess else None
            rationale = "Gemini indicated this finding does not map to any evaluated candidate."
            if best_guess:
                rationale = f"Gemini rejected top candidate: {best_guess.rationale}"

            mapping = ControlMapping(
                normalized_finding_id=finding.id,
                candidate_control_id=top_candidate.id,
                control_catalog_id=top_control.id,
                rank=top_candidate.rank or 1,
                mapping_model="gemini-batch",
                prompt_version=PROMPT_VERSION,
                rationale=rationale,
                gemini_confidence=confidence,
                verification_status=None,
                final_confidence=confidence,
                mapping_status=publication_status(confidence or 0.0),
            )
            db.add(mapping)
            db.flush()
            mappings.append(mapping)
            _add_review_item(
                review_items,
                mapping,
                "AI_MAPPER_REJECTED",
                "Gemini indicated this finding does not map to any evaluated candidate.",
            )
            continue

        candidate, decision = chosen
        control = candidate.control_catalog
        if control is None:
            failures.append({"finding_id": finding_id, "error": "Chosen candidate missing control catalog."})
            continue
        mapping = ControlMapping(
            normalized_finding_id=finding.id,
            candidate_control_id=candidate.id,
            control_catalog_id=control.id,
            rank=candidate.rank or 1,
            mapping_model="gemini-batch",
            prompt_version=PROMPT_VERSION,
            rationale=decision.rationale,
            gemini_confidence=decision.confidence,
            verification_status="pending",
            mapping_status="validated",
        )
        db.add(mapping)
        db.flush()
        mappings.append(mapping)

        ref += 1
        ref_to_mapping[ref] = mapping
        pending_verifications.append(
            PendingVerification(
                ref=ref,
                finding=finding,
                control=control,
                confidence=decision.confidence,
                rationale=decision.rationale,
            )
        )

    try:
        verifier = GroqVerifier()
    except RuntimeError as exc:
        verifier = None
        verification_error = str(exc)
    else:
        verification_error = None

    verdicts = {}
    groq_failed = False
    if verifier is not None and pending_verifications:
        try:
            verdicts = verifier.verify_batch(pending_verifications)
        except Exception as exc:
            verification_error = str(exc)
            groq_failed = True

    for item in pending_verifications:
        mapping = ref_to_mapping[item.ref]
        verdict = verdicts.get(item.ref)

        if verifier is None or groq_failed:
            mapping.verification_status = "failed"
            mapping.final_confidence = mapping.gemini_confidence
            mapping.mapping_status = publication_status(mapping.gemini_confidence or 0.0)
            db.add(
                VerificationRecord(
                    control_mapping_id=mapping.id,
                    verification_model="groq",
                    prompt_version=PROMPT_VERSION,
                    result="disagree",
                    agreement_value=0.0,
                    explanation=f"Verification unavailable: {verification_error or 'Groq API failed or unavailable.'}",
                )
            )
            if mapping.mapping_status == "manual_review":
                _add_review_item(
                    review_items,
                    mapping,
                    "AI_VERIFIER_FAILURE",
                    verification_error or "Groq API failed or unavailable.",
                )
            continue

        if verdict is None:
            mapping.verification_status = "failed"
            mapping.final_confidence = mapping.gemini_confidence
            mapping.mapping_status = publication_status(mapping.gemini_confidence or 0.0)
            db.add(
                VerificationRecord(
                    control_mapping_id=mapping.id,
                    verification_model="groq",
                    prompt_version=PROMPT_VERSION,
                    result="disagree",
                    agreement_value=0.0,
                    explanation="No result returned for this mapping in the batch response.",
                )
            )
            if mapping.mapping_status == "manual_review":
                _add_review_item(
                    review_items,
                    mapping,
                    "AI_VERIFIER_FAILURE",
                    "No result returned for this mapping in the batch response.",
                )
            continue

        final_confidence = calculate_final_confidence(mapping.gemini_confidence or 0.0, verdict.agreement_value)
        mapping.verification_status = verdict.result
        mapping.final_confidence = final_confidence
        mapping.mapping_status = publication_status(final_confidence)
        db.add(
            VerificationRecord(
                control_mapping_id=mapping.id,
                verification_model=verdict.model,
                prompt_version=verdict.prompt_version,
                result=verdict.result,
                agreement_value=verdict.agreement_value,
                explanation=verdict.explanation,
            )
        )
        if mapping.mapping_status == "manual_review":
            _add_review_item(
                review_items,
                mapping,
                "LOW_CONFIDENCE",
                f"Final confidence {final_confidence:.2f} is below publication threshold.",
            )

    db.add_all(review_items)
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    db.refresh(scan_run)

    return {
        "scan_run": scan_run,
        "raw_findings": raw_findings,
        "normalized_findings": normalized_findings,
        "mappings": mappings,
        "review_items": review_items,
        "failures": failures,
    }
