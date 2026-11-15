import logging
import re
from concurrent.futures import ThreadPoolExecutor, Future
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


def is_tpm_limit_exceeded(exc: Exception) -> bool:
    text = str(exc).lower()
    return "tokens per minute" in text or ("tpm" in text and ("limit" in text or "exceed" in text))


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

_STRICT_STRUCTURED_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"}
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


def _run_with_timeout(fn, timeout: float):
    """Run fn in a thread with a real per-call timeout that cancels on expiry.

    ``future.result(timeout=...)`` alone does not cancel the underlying call:
    exiting a ``with ThreadPoolExecutor`` block calls ``shutdown(wait=True)``
    and defeats the timeout. We keep the executor alive, cancel on timeout, and
    shut down without waiting.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    future: Future = pool.submit(fn)
    try:
        return future.result(timeout=timeout)
    except TimeoutError:
        future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError(f"Call timed out after {timeout}s")
    else:
        pool.shutdown(wait=True)


class GroqVerifier:
    def __init__(self, timeout: float = 30.0, max_batch_size: int = 10) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured; cannot perform AI verification.")
        self._client = Groq(api_key=GROQ_API_KEY)
        self._timeout = timeout
        self._max_batch_size = max_batch_size
        # Try the configured model first, then known-good fallbacks. Groq
        # retires models (e.g. llama-3.3-70b-versatile on 2026-08-16), so a
        # fallback avoids a hard failure when the primary is no longer served.
        self._models: list[str] = list(dict.fromkeys([GROQ_MODEL, *GROQ_MODEL_FALLBACKS]))
        self._cache: dict[str, dict[int, VerificationDecision]] = {}
        logger.info("Groq verifier initialized: models=%s, key_configured=%s, max_batch_size=%s", self._models, bool(GROQ_API_KEY), self._max_batch_size)

    def _cache_key_from_prompt(self, prompt: str, expected_refs: set[int]) -> str:
        """Cache key from the serialized prompt payload (not ORM objects)."""
        parts = [prompt]
        for ref in sorted(expected_refs):
            parts.append(str(ref))
        return "|".join(parts)

    def _build_chunk_prompt(
        self, chunk: list[PendingVerification]
    ) -> tuple[str, set[int]]:
        """Serialize ORM objects to plain text in the calling thread.

        All lazy attribute access happens here so worker threads never touch
        the request-scoped SQLAlchemy session.
        """
        prompt = "\n\n---\n\n".join(_entry_block(item) for item in chunk)
        expected_refs = {item.ref for item in chunk}
        return prompt, expected_refs

    def _completion(
        self, messages: list[dict[str, str]], timeout: float, schema_name: str, schema: dict[str, Any]
    ) -> tuple[str, Any]:
        last_exc: Exception | None = None
        for model in self._models:
            try:
                request = {
                    "model": model,
                    "messages": messages,
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
                    # GPT-OSS and Qwen spend completion tokens on reasoning. A low
                    # budget leaves none for the schema-constrained answer and
                    # yields Groq's json_validate_failed error.
                    request.update({"reasoning_effort": "low", "max_completion_tokens": 4096})
                response = self._client.chat.completions.create(**request)
                return model, response
            except Exception as exc:
                text = str(exc)
                if is_unavailable_model_error(exc):
                    last_exc = exc
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def _verify_one_chunk(
        self, prompt: str, expected_refs: set[int]
    ) -> dict[int, VerificationDecision]:
        cache_key = self._cache_key_from_prompt(prompt, expected_refs)
        if cache_key in self._cache:
            return self._cache[cache_key]

        def _attempt() -> dict[int, VerificationDecision]:
            def _call():
                return self._completion(
                    [
                        {"role": "system", "content": _SYSTEM_BATCH},
                        {"role": "user", "content": prompt},
                    ],
                    self._timeout,
                    "verification_batch",
                    _BATCH_SCHEMA,
                )

            model_used, response = _run_with_timeout(_call, self._timeout)
            choice = response.choices[0]
            usage = getattr(response, "usage", None)
            content = choice.message.content
            logger.info(
                "Groq verification batch response: expected_refs=%d finish_reason=%s "
                "prompt_tokens=%s completion_tokens=%s",
                len(expected_refs),
                getattr(choice, "finish_reason", None),
                getattr(usage, "prompt_tokens", None),
                getattr(usage, "completion_tokens", None),
            )
            logger.debug("Groq verification raw response content: %s", content[:4000])
            data = extract_json(content)
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
            missing_refs = expected_refs - set(out)
            if missing_refs:
                logger.warning(
                    "Groq omitted refs from batch response: expected=%s returned=%s missing=%s",
                    sorted(expected_refs), sorted(out), sorted(missing_refs),
                )
            logger.info("Groq verification batch parsed: expected_refs=%d returned_refs=%d", len(expected_refs), len(out))
            return out

        result = call_with_retry(
            _attempt,
            attempts=2,
            backoff=2.0,
            delay_for=extract_retry_delay,
            give_up_on=is_quota_exhausted,
            max_delay=15.0,
        )
        self._cache[cache_key] = result
        return result

    def verify_batch(self, items: list[PendingVerification]) -> dict[int, VerificationDecision]:
        if not items:
            return {}

        # Build all prompt payloads in the main thread (ORM access here only).
        chunks: list[list[PendingVerification]] = []
        for i in range(0, len(items), self._max_batch_size):
            chunks.append(items[i:i + self._max_batch_size])

        def verify_chunk(chunk: list[PendingVerification]) -> dict[int, VerificationDecision]:
            prompt, expected_refs = self._build_chunk_prompt(chunk)
            try:
                return self._verify_one_chunk(prompt, expected_refs)
            except Exception as exc:
                if len(chunk) <= 1 or not is_tpm_limit_exceeded(exc):
                    raise
                midpoint = len(chunk) // 2
                logger.warning("Groq batch exceeded its TPM limit; retrying as %d smaller batches", 2)
                return verify_chunk(chunk[:midpoint]) | verify_chunk(chunk[midpoint:])

        # Run chunks in parallel. One failing chunk must not take down the
        # whole run: partial verdicts are returned and missing refs are handled
        # by a single retry of only those refs in smaller batches.
        merged: dict[int, VerificationDecision] = {}
        last_error: Exception | None = None
        failed_chunks = 0
        workers = min(4, len(chunks))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(verify_chunk, chunk)
                for chunk in chunks
            ]
            for future in futures:
                try:
                    merged.update(future.result())
                except Exception as exc:
                    logger.warning("Groq verification chunk failed: %s", exc)
                    last_error = exc
                    failed_chunks += 1
        verified_refs = set(merged)
        missing_items = [item for item in items if item.ref not in verified_refs]
        if missing_items:
            retry_size = max(1, min(5, self._max_batch_size // 2))
            logger.warning(
                "Retrying %d missing Groq verdicts once in batches of at most %d",
                len(missing_items), retry_size,
            )
            for i in range(0, len(missing_items), retry_size):
                retry_chunk = missing_items[i:i + retry_size]
                try:
                    merged.update(verify_chunk(retry_chunk))
                except Exception as exc:
                    logger.warning(
                        "Groq retry failed for refs %s: %s",
                        [item.ref for item in retry_chunk], exc,
                    )
        if not merged and failed_chunks == len(chunks):
            raise RuntimeError(f"Groq verification failed for all {len(chunks)} chunks: {last_error}") from last_error
        return merged

    def verify_one(
        self,
        finding: NormalizedFinding,
        control: ControlCatalog,
        confidence: float,
        rationale: str,
    ) -> VerificationDecision:
        item = PendingVerification(ref=1, finding=finding, control=control, confidence=confidence, rationale=rationale)
        prompt = _entry_block(item)
        expected_refs = {1}

        def _attempt() -> VerificationDecision:
            def _call():
                return self._completion(
                    [
                        {"role": "system", "content": _SYSTEM_ONE},
                        {"role": "user", "content": prompt},
                    ],
                    self._timeout,
                    "verification_result",
                    _ONE_SCHEMA,
                )

            model_used, response = _run_with_timeout(_call, self._timeout)
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
            attempts=2,
            backoff=2.0,
            delay_for=extract_retry_delay,
            give_up_on=is_quota_exhausted,
            max_delay=15.0,
        )

    def clear_cache(self) -> None:
        """Clear the AI result cache."""
        self._cache.clear()
