import re
from dataclasses import dataclass

from google import genai
from google.genai import types

from complisoc.backend.core.config import GEMINI_API_KEY, GEMINI_MODEL, PROMPT_VERSION
from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.core.retry import call_with_retry
from complisoc.backend.models import CandidateControl, ControlCatalog, NormalizedFinding


DELAY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def is_quota_exhausted(exc: Exception) -> bool:
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def extract_retry_delay(exc: Exception) -> float | None:
    details = getattr(exc, "details", None)
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict) and str(item.get("@type", "")).endswith("RetryInfo"):
                value = str(item.get("retryDelay") or "")
                match = DELAY_RE.search(value)
                if match:
                    return float(match.group(1))
    text = str(exc)
    match = re.search(r"retry[_ ]?after\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = DELAY_RE.search(text)
    return float(match.group(1)) if match else None


@dataclass(frozen=True)
class MappingDecision:
    confidence: float
    rationale: str
    model: str = GEMINI_MODEL
    prompt_version: str = PROMPT_VERSION
    maps: bool = True


@dataclass(frozen=True)
class CandidateDecision:
    control_id: str
    maps: bool
    confidence: float
    rationale: str


_SYSTEM_ONE = (
    "You are a compliance mapping engine. You are given a single security "
    "finding produced by a scanner and exactly one candidate compliance "
    "control from an authoritative framework catalog. Judge how strongly the "
    "finding maps to that control. Respond ONLY with a JSON object of the form "
    '{"maps": true|false, "confidence": <number between 0 and 1>, "rationale": "<concise explanation>"}. '
    "Do not include markdown fences."
)

_SYSTEM_BATCH = (
    "You are a compliance mapping engine. You will receive a batch of security "
    "findings. Each finding lists candidate compliance controls that a deterministic "
    "pre-filter already narrowed down. For EVERY finding and EVERY candidate control, "
    "judge whether the finding maps to that control. Return every input pair and do "
    "not invent findings or controls.\n\n"
    "Respond ONLY with JSON in this shape:\n"
    '{"results": [{"finding_id": <int>, "candidates": [{"control_id": "<string>", '
    '"maps": true|false, "confidence": <number 0-1>, "rationale": "<concise explanation>"}]}]}\n'
    "Do not include markdown fences."
)


def _control_block(control: ControlCatalog, match_score: float | None = None) -> str:
    lines = [
        f"Control: {control.control_id} ({control.title}) [{control.framework_name}]",
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
    if match_score is not None:
        lines.append(f"Deterministic pre-filter match score: {match_score}")
    return "\n".join(lines)


def _finding_header(finding: NormalizedFinding) -> str:
    lines = [
        f"FINDING finding_id={finding.id}",
        f"Scanner: {finding.scanner_name}",
        f"Type: {finding.finding_type}",
        f"Resource type: {finding.resource_type}",
        f"Resource: {finding.resource_identifier}",
        f"Severity: {finding.severity}",
        f"Title: {finding.title}",
    ]
    if finding.description:
        lines.append(f"Description: {finding.description}")
    if finding.metadata_json:
        lines.append(f"Metadata: {finding.metadata_json}")
    return "\n".join(lines)


def _clean_decision(data: dict) -> tuple[bool, float, str]:
    maps = bool(data.get("maps", False))
    confidence = float(data.get("confidence", 0.0))
    confidence = min(0.99, max(0.01, confidence))
    if not maps:
        confidence = min(confidence, 0.30)
    rationale = str(data.get("rationale") or "No rationale provided by model.").strip()
    return maps, round(confidence, 4), rationale


class GeminiMapper:
    def __init__(self, timeout: float = 60.0) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured; cannot perform AI mapping.")
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._timeout = timeout

    def map_batch(
        self,
        items: list[tuple[NormalizedFinding, list[CandidateControl]]],
    ) -> dict[int, list[CandidateDecision]]:
        if not items:
            return {}

        blocks: list[str] = []
        expected: dict[int, list[str]] = {}
        for finding, candidates in items:
            expected[finding.id] = [candidate.control_catalog.control_id for candidate in candidates]
            candidate_text = "\n\n".join(
                f"CANDIDATE:\n{_control_block(candidate.control_catalog, match_score=candidate.match_score)}"
                for candidate in candidates
            )
            blocks.append(f"{_finding_header(finding)}\n\n{candidate_text}")
        prompt = "\n\n---\n\n".join(blocks)

        def _attempt() -> dict[int, list[CandidateDecision]]:
            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_BATCH,
                    response_mime_type="application/json",
                ),
            )
            data = extract_json(response.text)
            out: dict[int, list[CandidateDecision]] = {}
            for entry in data.get("results", []):
                finding_id = int(entry.get("finding_id"))
                if finding_id not in expected:
                    continue
                valid_ids = set(expected[finding_id])
                decisions: list[CandidateDecision] = []
                for candidate in entry.get("candidates", []):
                    control_id = str(candidate.get("control_id", ""))
                    if control_id not in valid_ids:
                        continue
                    maps, confidence, rationale = _clean_decision(candidate)
                    decisions.append(CandidateDecision(control_id, maps, confidence, rationale))
                out[finding_id] = decisions
            if not out:
                raise ValueError("Gemini batch response contained no usable results.")
            return out

        return call_with_retry(
            _attempt,
            attempts=3,
            backoff=2.0,
            delay_for=extract_retry_delay,
            give_up_on=is_quota_exhausted,
            max_delay=30.0,
        )

    def map_one(self, finding: NormalizedFinding, control: ControlCatalog) -> MappingDecision:
        prompt = f"CONTROL:\n{_control_block(control)}\n\nFINDING:\n{_finding_header(finding)}"

        def _attempt() -> MappingDecision:
            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_ONE,
                    response_mime_type="application/json",
                ),
            )
            maps, confidence, rationale = _clean_decision(extract_json(response.text))
            return MappingDecision(confidence=confidence, rationale=rationale, maps=maps)

        return call_with_retry(_attempt, attempts=3, backoff=1.0, delay_for=extract_retry_delay, give_up_on=is_quota_exhausted, max_delay=20.0)
