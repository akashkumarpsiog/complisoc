from dataclasses import dataclass

from complisoc.backend.models import CandidateControl, ControlCatalog, NormalizedFinding


@dataclass(frozen=True)
class MappingDecision:
    confidence: float
    rationale: str
    model: str = "gemini-2.5-flash-local-deterministic"
    prompt_version: str = "mvp-v1"


class DeterministicGeminiMapper:
    def map(
        self,
        finding: NormalizedFinding,
        candidate: CandidateControl,
        control: ControlCatalog,
    ) -> MappingDecision:
        confidence = min(0.99, max(0.05, candidate.match_score or 0.05))
        rationale = (
            f"{finding.scanner_name} finding '{finding.title}' maps to "
            f"{control.framework_name} {control.control_id} because the deterministic "
            f"candidate narrowing matched scanner evidence to '{control.title}'."
        )
        return MappingDecision(confidence=round(confidence, 4), rationale=rationale)

