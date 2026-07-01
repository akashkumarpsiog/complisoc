from dataclasses import dataclass

from complisoc.backend.models import ControlCatalog, ControlMapping, NormalizedFinding


@dataclass(frozen=True)
class VerificationDecision:
    result: str
    agreement_value: float
    explanation: str
    model: str = "llama-3.3-70b-local-deterministic"
    prompt_version: str = "mvp-v1"


class DeterministicGroqVerifier:
    def verify(
        self,
        finding: NormalizedFinding,
        mapping: ControlMapping,
        control: ControlCatalog,
    ) -> VerificationDecision:
        confidence = mapping.gemini_confidence or 0
        if confidence >= 0.45:
            return VerificationDecision(
                result="agree",
                agreement_value=1.0,
                explanation=f"Finding evidence is consistent with {control.control_id} at deterministic confidence {confidence:.2f}.",
            )
        return VerificationDecision(
            result="disagree",
            agreement_value=0.0,
            explanation=f"Finding evidence is too weak for {control.control_id} at deterministic confidence {confidence:.2f}.",
        )

