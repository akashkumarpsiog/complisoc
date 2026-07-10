import re
from dataclasses import dataclass

from groq import Groq

from complisoc.backend.core.config import GROQ_API_KEY, GROQ_MODEL, PROMPT_VERSION
from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.core.retry import call_with_retry
from complisoc.backend.models import ControlCatalog, NormalizedFinding


DELAY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def is_quota_exhausted(exc: Exception) -> bool:
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text or "rate_limit" in text.lower() or "quota" in text.lower()


def extract_retry_delay(exc: Exception) -> float | None:
    text = str(exc)
    match = re.search(r"retry[_ ]?after\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = DELAY_RE.search(text)
    return float(match.group(1)) if match else None


@dataclass(frozen=True)
class VerificationDecision:
    result: str
    agreement_value: float
    explanation: str
    model: str = GROQ_MODEL
    prompt_version: str = PROMPT_VERSION


@dataclass(frozen=True)
class PendingVerification:
    ref: int
    finding: NormalizedFinding
    control: ControlCatalog
    confidence: float
    rationale: str


_SYSTEM_BATCH = (
    "You are an independent compliance verification engine. You will receive a "
    "batch of proposed control mappings. Each entry has a ref number, a security "
    "finding, the compliance control it was mapped to, and the proposed confidence "
    "and rationale. For every ref, independently decide whether the mapping is "
    "correct and defensible.\n\n"
    'Respond ONLY with JSON in this shape: {"results": [{"ref": <int>, '
    '"result": "agree"|"disagree", "explanation": "<concise reason>"}]}. '
    "Do not include markdown fences."
)

_SYSTEM_ONE = (
    "You are an independent compliance verification engine. You are given a "
    "security finding, the compliance control it was mapped to, and the proposed "
    "mapping's confidence and rationale. Respond ONLY with JSON of the form "
    '{"result": "agree"|"disagree", "explanation": "<concise reason>"}.'
)


def _finding_block(finding: NormalizedFinding) -> str:
    lines = [
        f"Scanner: {finding.scanner_name}",
        f"Type: {finding.finding_type}",
        f"Resource type: {finding.resource_type}",
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


def _entry_block(item: PendingVerification) -> str:
    return (
        f"REF {item.ref}\n"
        f"FINDING:\n{_finding_block(item.finding)}\n\n"
        f"CONTROL:\n{_control_block(item.control)}\n\n"
        f"Confidence: {item.confidence}\n"
        f"Rationale: {item.rationale}"
    )


class GroqVerifier:
    def __init__(self, timeout: float = 60.0) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured; cannot perform AI verification.")
        self._client = Groq(api_key=GROQ_API_KEY)
        self._timeout = timeout

    def verify_batch(self, items: list[PendingVerification]) -> dict[int, VerificationDecision]:
        if not items:
            return {}

        prompt = "\n\n---\n\n".join(_entry_block(item) for item in items)
        expected_refs = {item.ref for item in items}

        def _attempt() -> dict[int, VerificationDecision]:
            response = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_BATCH},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=self._timeout,
            )
            data = extract_json(response.choices[0].message.content)
            out: dict[int, VerificationDecision] = {}
            for entry in data.get("results", []):
                ref = int(entry.get("ref"))
                if ref not in expected_refs:
                    continue
                result = str(entry.get("result", "")).strip().lower()
                if result not in {"agree", "disagree"}:
                    continue
                explanation = str(entry.get("explanation") or "No explanation provided by model.").strip()
                out[ref] = VerificationDecision(
                    result=result,
                    agreement_value=1.0 if result == "agree" else 0.0,
                    explanation=explanation,
                )
            if not out:
                raise ValueError("Groq batch response contained no usable results.")
            return out

        return call_with_retry(
            _attempt,
            attempts=3,
            backoff=2.0,
            delay_for=extract_retry_delay,
            give_up_on=is_quota_exhausted,
            max_delay=30.0,
        )

    def verify_one(
        self,
        finding: NormalizedFinding,
        control: ControlCatalog,
        confidence: float,
        rationale: str,
    ) -> VerificationDecision:
        item = PendingVerification(ref=1, finding=finding, control=control, confidence=confidence, rationale=rationale)
        response = self._client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_ONE},
                {"role": "user", "content": _entry_block(item)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=self._timeout,
        )
        data = extract_json(response.choices[0].message.content)
        result = str(data.get("result", "")).strip().lower()
        if result not in {"agree", "disagree"}:
            raise ValueError(f"Groq verification returned an invalid result: {result!r}")
        return VerificationDecision(
            result=result,
            agreement_value=1.0 if result == "agree" else 0.0,
            explanation=str(data.get("explanation") or "No explanation provided by model.").strip(),
        )
