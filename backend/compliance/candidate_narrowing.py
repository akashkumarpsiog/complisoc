import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from complisoc.backend.models import CandidateControl, ControlCatalog, NormalizedFinding


TOKEN_RE = re.compile(r"[a-z0-9_./-]+")


@dataclass(frozen=True)
class CandidateScore:
    control: ControlCatalog
    score: float
    rationale: str


def _tokens(*values: object) -> set[str]:
    text = " ".join(str(value or "") for value in values)
    return set(TOKEN_RE.findall(text.lower()))


def _control_tokens(control: ControlCatalog) -> set[str]:
    return _tokens(
        control.framework_name,
        control.control_id,
        control.control_family,
        control.title,
        control.description,
        control.objective,
        " ".join(control.keywords or []),
        " ".join(control.scanner_signals or []),
    )


def narrow_candidates(
    db: Session,
    finding: NormalizedFinding,
    *,
    framework: str | None = None,
    limit: int = 5,
) -> list[CandidateControl]:
    query = db.query(ControlCatalog).filter(ControlCatalog.active_status.is_(True))
    if framework:
        query = query.filter(ControlCatalog.framework_name == framework)

    finding_tokens = _tokens(
        finding.scanner_name,
        finding.finding_type,
        finding.resource_type,
        finding.resource_identifier,
        finding.severity,
        finding.title,
        finding.description,
        finding.metadata_json,
    )

    scored: list[CandidateScore] = []
    for control in query.all():
        overlap = finding_tokens & _control_tokens(control)
        keyword_hits = overlap & set(control.keywords or [])
        signal_hits = overlap & set(control.scanner_signals or [])
        score = min(1.0, (len(overlap) * 0.08) + (len(keyword_hits) * 0.12) + (len(signal_hits) * 0.18))
        if score > 0:
            rationale = "Matched deterministic tokens: " + ", ".join(sorted(overlap)[:12])
            scored.append(CandidateScore(control=control, score=round(score, 4), rationale=rationale))

    scored.sort(key=lambda item: (-item.score, item.control.framework_name, item.control.control_id))
    selected = scored[:limit]

    candidates: list[CandidateControl] = []
    for rank, item in enumerate(selected, start=1):
        candidate = CandidateControl(
            normalized_finding_id=finding.id,
            control_catalog_id=item.control.id,
            source="deterministic_keyword_signal",
            match_score=item.score,
            rank=rank,
        )
        db.add(candidate)
        candidates.append(candidate)

    db.commit()
    for candidate in candidates:
        db.refresh(candidate)
    return candidates

