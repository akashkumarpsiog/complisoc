"""LangChain / LCEL compliance orchestration (single source of truth).

This module implements the *only* compliance orchestration in Complisoc,
expressed with LangChain Expression Language (LCEL):

    scan results → Gemini mapping → Groq gap analysis → structured report

Each pipeline stage is a ``RunnableLambda`` and the stages are composed with
the pipe operator (``|``) in ``_build_chain``. The chain is executed by
``run_pipeline``, which is the canonical workflow entry point consumed by
the API, the benchmark/script, and the tests.

``complisoc.backend.compliance.workflow.process_scan_run`` is kept as a thin
alias to ``run_pipeline`` so existing callers keep working without changes.
There is intentionally no second, parallel implementation to drift apart.

The chain reuses the shared deterministic and AI building blocks
(``ingest_findings``, ``normalize_raw_finding``, ``narrow_candidates``,
``GeminiMapper``, ``GroqVerifier``, ``calculate_final_confidence``,
``publication_status``). ``langchain_core`` is imported lazily inside
``_build_chain`` so an import failure surfaces only when the pipeline runs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from complisoc.backend.compliance.candidate_narrowing import narrow_candidates
from complisoc.backend.compliance.confidence import calculate_final_confidence, publication_status
from complisoc.backend.compliance.mapping import CandidateDecision, GeminiMapper
from complisoc.backend.compliance.verification import GroqVerifier, PendingVerification
from complisoc.backend.core.config import PROMPT_VERSION

logger = logging.getLogger(__name__)
from complisoc.backend.models import (
    ControlMapping,
    NormalizedFinding,
    ReviewQueueItem,
    VerificationRecord,
)
from complisoc.backend.normalization.normalizer import normalize_raw_finding
from complisoc.backend.scanners.ingestion import ingest_findings


MAX_CANDIDATES_PER_FINDING = 3


@dataclass
class _ChainState:
    """Mutable carrier threaded through the LCEL chain stages."""

    db: Session
    target_environment: str
    findings: list[dict]
    scanner_failures: list[dict] | None = None
    framework: str | None = None

    scan_run: Any = None
    raw_findings: list = field(default_factory=list)
    normalized_findings: list = field(default_factory=list)
    mappings: list = field(default_factory=list)
    review_items: list = field(default_factory=list)
    failures: list = field(default_factory=list)

    candidates_by_finding: dict = field(default_factory=dict)
    batch_input: list = field(default_factory=list)
    batch_decisions: dict = field(default_factory=dict)

    pending_verifications: list = field(default_factory=list)
    ref_to_mapping: dict = field(default_factory=dict)
    verdicts: dict = field(default_factory=dict)

    gemini_error: str | None = None
    groq_error: str | None = None

    gemini_unavailable: bool = False
    gemini_failed: bool = False
    groq_unavailable: bool = False
    groq_failed: bool = False


def _add_review_item(review_items: list[ReviewQueueItem], mapping: ControlMapping, code: str, comments: str) -> None:
    review_items.append(
        ReviewQueueItem(
            control_mapping_id=mapping.id,
            status="pending",
            review_reason_code=code,
            comments=comments,
        )
    )


# ---------------------------------------------------------------------------
# Stage 1: ingest findings + normalize + deterministic candidate narrowing
# ---------------------------------------------------------------------------
def stage_ingest(state: _ChainState) -> _ChainState:
    scan_run, raw_findings = ingest_findings(
        state.db,
        target_environment=state.target_environment,
        findings=state.findings,
        scanner_failures=state.scanner_failures,
    )
    state.scan_run = scan_run
    state.raw_findings = raw_findings

    for raw_finding in raw_findings:
        try:
            normalized = normalize_raw_finding(state.db, raw_finding)
            state.normalized_findings.append(normalized)
            candidates = narrow_candidates(state.db, normalized, framework=state.framework)
            if not candidates:
                state.failures.append({"raw_finding_id": raw_finding.id, "error": "No candidate controls matched."})
                continue
            state.candidates_by_finding[normalized.id] = candidates
            top_candidates = [
                candidate for candidate in candidates[:MAX_CANDIDATES_PER_FINDING]
                if candidate.control_catalog is not None
            ]
            if top_candidates:
                state.batch_input.append((normalized, top_candidates))
        except Exception as exc:
            state.db.rollback()
            state.failures.append({"raw_finding_id": raw_finding.id, "error": str(exc)})
    return state


# ---------------------------------------------------------------------------
# Stage 2: Gemini mapping (AI) — same GeminiMapper used by the direct path
# ---------------------------------------------------------------------------
def stage_map(state: _ChainState) -> _ChainState:
    try:
        mapper = GeminiMapper()
    except RuntimeError as exc:
        mapper = None
        state.gemini_error = str(exc)
        state.gemini_unavailable = True
        logger.warning("Gemini mapper unavailable; findings will be queued for manual review: %s", state.gemini_error)
    else:
        state.gemini_error = None
        state.gemini_unavailable = False

    if mapper is not None and state.batch_input:
        try:
            state.batch_decisions = mapper.map_batch(state.batch_input)
        except Exception as exc:
            state.gemini_error = str(exc)
            state.gemini_failed = True
            logger.warning("Gemini batch mapping failed; findings will be queued for manual review: %s", state.gemini_error)
    return state


# ---------------------------------------------------------------------------
# Stage 3: build ControlMapping rows from mapping decisions
# ---------------------------------------------------------------------------
def stage_build_mappings(state: _ChainState) -> _ChainState:
    findings_by_id = {finding.id: finding for finding in state.normalized_findings}
    ref = 0

    for finding_id, candidates in state.candidates_by_finding.items():
        finding = findings_by_id[finding_id]
        top_candidate = candidates[0]
        top_control = top_candidate.control_catalog
        if top_control is None:
            state.failures.append({"finding_id": finding_id, "error": "Top candidate missing control catalog."})
            continue

        if state.gemini_unavailable or state.gemini_failed:
            if state.gemini_unavailable:
                rationale = f"Gemini mapper unavailable; API failed: {state.gemini_error}"
                comment = state.gemini_error or "Gemini API key is not configured."
            else:
                rationale = f"Gemini batch mapping failed: {state.gemini_error}"
                comment = state.gemini_error or "Gemini batch mapping failed."
            mapping = ControlMapping(
                normalized_finding_id=finding.id,
                candidate_control_id=top_candidate.id,
                control_catalog_id=top_control.id,
                rank=top_candidate.rank or 1,
                mapping_model="gemini-batch",
                prompt_version=PROMPT_VERSION,
                rationale=rationale,
                gemini_confidence=None,
                verification_status=None,
                final_confidence=None,
                groq_agreement_value=None,
                mapping_status="manual_review",
            )
            state.db.add(mapping)
            state.db.flush()
            state.mappings.append(mapping)
            _add_review_item(
                state.review_items,
                mapping,
                "AI_MAPPER_FAILURE",
                comment,
            )
            continue

        decisions = state.batch_decisions.get(finding_id)
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
                groq_agreement_value=None,
                mapping_status="manual_review",
            )
            state.db.add(mapping)
            state.db.flush()
            state.mappings.append(mapping)
            _add_review_item(
                state.review_items,
                mapping,
                "AI_MAPPER_FAILURE",
                "No result returned for this finding in the batch response.",
            )
            continue

        decision_by_control = {decision.control_id: decision for decision in decisions}
        chosen: tuple | None = None
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
                groq_agreement_value=None,
                mapping_status=publication_status(confidence or 0.0),
            )
            state.db.add(mapping)
            state.db.flush()
            state.mappings.append(mapping)
            _add_review_item(
                state.review_items,
                mapping,
                "AI_MAPPER_REJECTED",
                "Gemini indicated this finding does not map to any evaluated candidate.",
            )
            continue

        candidate, decision = chosen
        control = candidate.control_catalog
        if control is None:
            state.failures.append({"finding_id": finding_id, "error": "Chosen candidate missing control catalog."})
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
            final_confidence=None,
            groq_agreement_value=None,
            mapping_status="validated",
        )
        state.db.add(mapping)
        state.db.flush()
        state.mappings.append(mapping)

        ref += 1
        state.ref_to_mapping[ref] = mapping
        state.pending_verifications.append(
            PendingVerification(
                ref=ref,
                finding=finding,
                control=control,
                confidence=decision.confidence,
                rationale=decision.rationale,
            )
        )
    return state


# ---------------------------------------------------------------------------
# Stage 4: Groq gap analysis (AI) — same GroqVerifier used by direct path
# ---------------------------------------------------------------------------
def stage_verify(state: _ChainState) -> _ChainState:
    try:
        verifier = GroqVerifier()
    except RuntimeError as exc:
        verifier = None
        state.groq_error = str(exc)
        state.groq_unavailable = True
        logger.warning("Groq verifier unavailable; mappings will be queued for manual review: %s", state.groq_error)
    else:
        state.groq_error = None
        state.groq_unavailable = False

    verdicts = {}
    if verifier is not None and state.pending_verifications:
        try:
            verdicts = verifier.verify_batch(state.pending_verifications)
        except Exception as exc:
            state.groq_error = str(exc)
            state.groq_failed = True
            logger.warning("Groq verification failed; mappings will be queued for manual review: %s", state.groq_error)
    state.verdicts = verdicts
    return state


# ---------------------------------------------------------------------------
# Stage 5: finalize confidence + VerificationRecord rows + review items
# ---------------------------------------------------------------------------
def stage_finalize(state: _ChainState) -> _ChainState:
    verdicts = state.verdicts

    for item in state.pending_verifications:
        mapping = state.ref_to_mapping[item.ref]
        verdict = verdicts.get(item.ref)

        if state.groq_unavailable or state.groq_failed:
            mapping.verification_status = "failed"
            mapping.final_confidence = mapping.gemini_confidence
            mapping.groq_agreement_value = 0.0
            mapping.mapping_status = publication_status(mapping.gemini_confidence or 0.0)
            state.db.add(
                VerificationRecord(
                    control_mapping_id=mapping.id,
                    verification_model="groq",
                    prompt_version=PROMPT_VERSION,
                    result="disagree",
                    agreement_value=0.0,
                    explanation=f"Verification unavailable: {state.groq_error or 'Groq API failed or unavailable.'}",
                )
            )
            if mapping.mapping_status == "manual_review":
                _add_review_item(
                    state.review_items,
                    mapping,
                    "AI_VERIFIER_FAILURE",
                    state.groq_error or "Groq API failed or unavailable.",
                )
            continue

        if verdict is None:
            mapping.verification_status = "failed"
            mapping.final_confidence = mapping.gemini_confidence
            mapping.groq_agreement_value = 0.0
            mapping.mapping_status = publication_status(mapping.gemini_confidence or 0.0)
            state.db.add(
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
                    state.review_items,
                    mapping,
                    "AI_VERIFIER_FAILURE",
                    "No result returned for this mapping in the batch response.",
                )
            continue

        final_confidence = calculate_final_confidence(mapping.gemini_confidence or 0.0, verdict.agreement_value)
        mapping.verification_status = verdict.result
        mapping.final_confidence = final_confidence
        mapping.groq_agreement_value = verdict.agreement_value
        mapping.mapping_status = publication_status(final_confidence)
        state.db.add(
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
                state.review_items,
                mapping,
                "LOW_CONFIDENCE",
                f"Final confidence {final_confidence:.2f} is below publication threshold.",
            )

    state.db.add_all(state.review_items)
    state.db.commit()
    for mapping in state.mappings:
        state.db.refresh(mapping)
    state.db.refresh(state.scan_run)
    return state


def _build_chain():
    """Compose the LCEL chain from the five pipeline stages."""
    from langchain_core.runnables import RunnableLambda

    return (
        RunnableLambda(stage_ingest)
        | RunnableLambda(stage_map)
        | RunnableLambda(stage_build_mappings)
        | RunnableLambda(stage_verify)
        | RunnableLambda(stage_finalize)
    )


def run_pipeline(
    db: Session,
    *,
    target_environment: str,
    findings: list[dict],
    scanner_failures: list[dict] | None = None,
    framework: str | None = None,
) -> dict:
    """Run the compliance pipeline through the LangChain/LCEL path.

    Returns the same dict shape as ``process_scan_run`` so callers (the API)
    can use either path interchangeably.
    """
    state = _ChainState(
        db=db,
        target_environment=target_environment,
        findings=findings,
        scanner_failures=scanner_failures,
        framework=framework,
    )
    chain = _build_chain()
    final: _ChainState = chain.invoke(state)
    result = {
        "scan_run": final.scan_run,
        "raw_findings": final.raw_findings,
        "normalized_findings": final.normalized_findings,
        "mappings": final.mappings,
        "review_items": final.review_items,
        "failures": final.failures,
    }
    if final.gemini_error:
        result["failures"].append(
            {"scanner_name": "gemini", "error_message": f"AI mapping failed: {final.gemini_error}"}
        )
    if final.groq_error:
        result["failures"].append(
            {"scanner_name": "groq", "error_message": f"AI verification failed: {final.groq_error}"}
        )
    return result


def is_langchain_available() -> bool:
    try:
        import langchain_core  # noqa: F401

        return True
    except ImportError:
        return False


__all__ = ["run_pipeline", "is_langchain_available"]
