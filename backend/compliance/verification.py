import logging
import re
from dataclasses import dataclass
from typing import Any

from groq import Groq

from complisoc.backend.core.config import GROQ_API_KEY, GROQ_MODEL, GROQ_MODEL_FALLBACKS, PROMPT_VERSION

logger = logging.getLogger(__name__)
from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.core.retry import call_with_retry
from complisoc.backend.models import ControlCatalog, NormalizedFinding


DELAY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def is_unavailable_model_error(exc: Exception) -> bool:
    """Return whether Groq rejected the requested model, so a fallback is safe."""
    text = str(exc).lower()
    markers = (
        "model_not_found",
        "does not exist",
        "not found",
        "decommissioned",
        "retired",
        "deprecated",
        "no longer supported",
        "not available",
    )
    return "model" in text and any(marker in text for marker in markers)


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

_STRICT_STRUCTURED_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}
_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "integer"},
                    "result": {"type": "string", "enum": ["agree", "disagree"]},
                    "explanation": {"type": "string"},
                },
                "required": ["ref", "result", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}
_ONE_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {"type": "string", "enum": ["agree", "disagree"]},
        "explanation": {"type": "string"},
    },
    "required": ["result", "explanation"],
    "additionalProperties": False,
}


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
        # Try the configured model first, then known-good fallbacks. Groq
        # retires models (e.g. llama-3.3-70b-versatile on 2026-08-16), so a
        # fallback avoids a hard failure when the primary is no longer served.
        self._models: list[str] = list(dict.fromkeys([GROQ_MODEL, *GROQ_MODEL_FALLBACKS]))
        self._cache: dict[str, dict[int, VerificationDecision]] = {}
        logger.info("Groq verifier initialized: models=%s, key_configured=%s", self._models, bool(GROQ_API_KEY))

    def _cache_key(self, items: list[PendingVerification]) -> str:
        """Generate a cache key from finding IDs and control IDs."""
        parts = []
        for item in sorted(items, key=lambda x: x.ref):
            parts.append(f"{item.ref}:{item.finding.id}:{item.control.id}")
        return "|".join(parts)

    def _completion(self, messages: list[dict[str, str]], timeout: float, schema_name: str, schema: dict[str, Any]) -> tuple[str, Any]:
        last_exc: Exception | None = None
        for model in self._models:
            try:
                request = {
                    "model": model,
                    "messages": messages,
                    # Groq recommends strict JSON Schema mode for GPT-OSS. It
                    # eliminates json_validate_failed responses that JSON mode
                    # can return even when the prompt requests JSON. Keep JSON
                    # object mode for the non-GPT fallback model.
                    "response_format": (
                        {
                            "type": "json_schema",
                            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
                        }
                        if model in _STRICT_STRUCTURED_MODELS
                        else {"type": "json_object"}
                    ),
                    "temperature": 0.0,
                    "timeout": timeout,
                }
                if model in _STRICT_STRUCTURED_MODELS:
                    # GPT-OSS spends completion tokens on reasoning. A low
                    # budget leaves none for the schema-constrained answer and
                    # yields Groq's json_validate_failed error.
                    request.update({"reasoning_effort": "low", "max_completion_tokens": 768})
                response = self._client.chat.completions.create(**request)
                return model, response
            except Exception as exc:
                text = str(exc)
                # Groq can describe a disabled model as unknown, decommissioned,
                # retired, or no longer supported. Only these model-specific
                # errors warrant changing models; authentication and request
                # errors must remain visible to the caller.
                if is_unavailable_model_error(exc):
                    last_exc = exc
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def verify_batch(self, items: list[PendingVerification]) -> dict[int, VerificationDecision]:
        if not items:
            return {}

        cache_key = self._cache_key(items)
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = "\n\n---\n\n".join(_entry_block(item) for item in items)
        expected_refs = {item.ref for item in items}

        def _attempt() -> dict[int, VerificationDecision]:
            model_used, response = self._completion(
                [
                    {"role": "system", "content": _SYSTEM_BATCH},
                    {"role": "user", "content": prompt},
                ],
                self._timeout,
                "verification_batch",
                _BATCH_SCHEMA,
            )
            data = extract_json(response.choices[0].message.content)
            out: dict[int, VerificationDecision] = {}
            for entry in data.get("results", []):
                ref = entry.get("ref")
                if ref is None:
                    continue
                ref = int(ref)
                if ref not in expected_refs:
                    continue
                result_raw = entry.get("result", "")
                if isinstance(result_raw, bool):
                    result = "agree" if result_raw else "disagree"
                else:
                    result = str(result_raw).strip().lower()
                if result not in {"agree", "disagree"}:
                    continue
                explanation = str(entry.get("explanation") or "No explanation provided by model.").strip()
                out[ref] = VerificationDecision(
                    result=result,
                    agreement_value=1.0 if result == "agree" else 0.0,
                    explanation=explanation,
                    model=model_used,
                )
            if not out:
                raise ValueError("Groq batch response contained no usable results.")
            self._cache[cache_key] = out
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

        def _attempt() -> VerificationDecision:
            model_used, response = self._completion(
                [
                    {"role": "system", "content": _SYSTEM_ONE},
                    {"role": "user", "content": _entry_block(item)},
                ],
                self._timeout,
                "verification_result",
                _ONE_SCHEMA,
            )
            data = extract_json(response.choices[0].message.content)
            result_raw = data.get("result", "")
            if isinstance(result_raw, bool):
                result = "agree" if result_raw else "disagree"
            else:
                result = str(result_raw).strip().lower()
            if result not in {"agree", "disagree"}:
                raise ValueError(f"Groq verification returned an invalid result: {result!r}")
            return VerificationDecision(
                result=result,
                agreement_value=1.0 if result == "agree" else 0.0,
                explanation=str(data.get("explanation") or "No explanation provided by model.").strip(),
                model=model_used,
            )

        return call_with_retry(
            _attempt,
            attempts=3,
            backoff=2.0,
            delay_for=extract_retry_delay,
            give_up_on=is_quota_exhausted,
            max_delay=30.0,
        )

    def clear_cache(self) -> None:
        """Clear the AI result cache."""
        self._cache.clear()
