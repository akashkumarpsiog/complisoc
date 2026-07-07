import json
from dataclasses import dataclass

from groq import Groq

from complisoc.backend.core.config import GROQ_API_KEY, GROQ_MODEL, PROMPT_VERSION
from complisoc.backend.models import ControlCatalog, ControlMapping, NormalizedFinding


@dataclass(frozen=True)
class VerificationDecision:
    result: str
    agreement_value: float
    explanation: str
    model: str = GROQ_MODEL
    prompt_version: str = PROMPT_VERSION


_SYSTEM = (
    "You are an independent compliance verification engine. You are given a "
    "security finding, the compliance control it was mapped to, and the "
    "proposed mapping's confidence and rationale. Assess whether the mapping "
    "is correct and defensible. Respond ONLY with a JSON object of the form "
    '{"result": "agree"|"disagree", "explanation": "<concise reason>"}. '
    "Do not include markdown fences."
)


def _finding_block(finding: NormalizedFinding) -> str:
    lines = [
        f"Scanner: {finding.scanner_name}",
        f"Type: {finding.finding_type}",
        f"Resource: {finding.resource_identifier}",
        f"Severity: {finding.severity}",
        f"Title: {finding.title}",
    ]
    if finding.description:
        lines.append(f"Description: {finding.description}")
    return "\n".join(lines)


def _control_block(control: ControlCatalog) -> str:
    lines = [
        f"Framework: {control.framework_name}",
        f"Control: {control.control_id} ({control.title})",
        f"Family: {control.control_family}",
        f"Description: {control.description}",
    ]
    if control.objective:
        lines.append(f"Objective: {control.objective}")
    return "\n".join(lines)


def _verification_prompt(finding: NormalizedFinding, mapping: ControlMapping, control: ControlCatalog) -> str:
    return (
        f"FINDING:\n{_finding_block(finding)}\n\n"
        f"CONTROL:\n{_control_block(control)}\n\n"
        f"PROPOSED MAPPING:\n"
        f"Confidence: {mapping.final_confidence if mapping.final_confidence is not None else mapping.gemini_confidence}\n"
        f"Rationale: {mapping.rationale}\n\n"
        "Does this finding correctly map to this control?"
    )


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return json.loads(text)


class GroqVerifier:
    def __init__(self) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured; cannot perform AI verification.")
        self._client = Groq(api_key=GROQ_API_KEY)

    def verify(
        self,
        finding: NormalizedFinding,
        mapping: ControlMapping,
        control: ControlCatalog,
    ) -> VerificationDecision:
        response = self._client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _verification_prompt(finding, mapping, control)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = _parse_json(response.choices[0].message.content)
        result = str(data.get("result", "")).strip().lower()
        if result not in ("agree", "disagree"):
            raise ValueError(f"Groq verification returned an invalid result: {result!r}")
        explanation = str(data.get("explanation") or "No explanation provided by model.").strip()
        agreement = 1.0 if result == "agree" else 0.0
        return VerificationDecision(result=result, agreement_value=agreement, explanation=explanation)
