import json
from dataclasses import dataclass

from google import genai
from google.genai import types

from complisoc.backend.core.config import GEMINI_API_KEY, GEMINI_MODEL, PROMPT_VERSION
from complisoc.backend.models import CandidateControl, ControlCatalog, NormalizedFinding


@dataclass(frozen=True)
class MappingDecision:
    confidence: float
    rationale: str
    model: str = GEMINI_MODEL
    prompt_version: str = PROMPT_VERSION


_SYSTEM = (
    "You are a compliance mapping engine. You are given a single security "
    "finding produced by a scanner and exactly one candidate compliance "
    "control from an authoritative framework catalog. Your job is to judge "
    "how strongly the finding maps to that control and explain the reasoning. "
    "Consider the finding's resource, severity, and description against the "
    "control's objective, description, evidence examples, keywords, and "
    "scanner signals. Respond ONLY with a JSON object of the form "
    '{"confidence": <number between 0 and 1>, "rationale": "<concise explanation>", '
    '"maps": <true|false>}. Do not include markdown fences.'
)


def _control_block(control: ControlCatalog) -> str:
    lines = [
        f"Framework: {control.framework_name}",
        f"Control: {control.control_id} ({control.title})",
        f"Family: {control.control_family}",
        f"Description: {control.description}",
    ]
    if control.objective:
        lines.append(f"Objective: {control.objective}")
    if control.evidence_examples:
        lines.append(f"Evidence examples: {control.evidence_examples}")
    if control.keywords:
        lines.append(f"Keywords: {control.keywords}")
    if control.scanner_signals:
        lines.append(f"Scanner signals: {control.scanner_signals}")
    return "\n".join(lines)


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


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return json.loads(text)


class GeminiMapper:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured; cannot perform AI mapping.")
        self._client = genai.Client(api_key=GEMINI_API_KEY)

    def map(
        self,
        finding: NormalizedFinding,
        candidate: CandidateControl,
        control: ControlCatalog,
    ) -> MappingDecision:
        response = self._client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"CONTROL:\n{_control_block(control)}\n\nFINDING:\n{_finding_block(finding)}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        data = _parse_json(response.text)
        confidence = float(data.get("confidence", 0.0))
        confidence = min(0.99, max(0.01, confidence))
        rationale = str(data.get("rationale") or "No rationale provided by model.").strip()
        return MappingDecision(confidence=round(confidence, 4), rationale=rationale)
