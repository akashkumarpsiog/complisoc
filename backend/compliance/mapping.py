import hashlib
import json
import logging
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass

from google import genai
from google.genai import types

from complisoc.backend.core.config import GEMINI_API_KEY, GEMINI_MODEL, PROMPT_VERSION
from complisoc.backend.core.json_extract import extract_json
from complisoc.backend.core.retry import call_with_retry
from complisoc.backend.models import CandidateControl, ControlCatalog, NormalizedFinding


logger = logging.getLogger(__name__)

DELAY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)

# Number of findings sent per Gemini mapping request. Chunks run in parallel.
MAPPING_CHUNK_SIZE = 25

# Cap concurrency to stay under free-tier rate limits (10 RPM).
MAPPING_MAX_WORKERS = 1

# A daily-quota retryDelay is measured in hours (e.g. 77945s ≈ 21.5h).
# Retrying it is pointless: fail fast instead. Per-minute limits have much
# smaller retryDelay values and are safe to retry.
DAILY_QUOTA_RETRY_SECONDS = 300.0


def is_per_day_quota_exhausted(exc: Exception) -> bool:
    """True when the error is a per-day quota that will not recover in this session."""
    text = str(exc)
    if "RESOURCE_EXHAUSTED" not in text and "quota" not in text.lower():
        return False
    delay = extract_retry_delay(exc)
    return delay is not None and delay > DAILY_QUOTA_RETRY_SECONDS


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
    '"maps": true|false, "confidence": <number 0-1>, "rationale": "<concise explanation of at most 20 words>"}]}]}\n'
    "Keep each rationale to about 20 words. Do not include markdown fences."
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


def _finding_fingerprint(finding: NormalizedFinding) -> str:
    """Content-based fingerprint for a finding, stable across scan runs.

    Uses the full normalized evidence payload except database identifiers
    — all content-derived properties that don't change when the same target is
    rescanned. The database finding_id and raw_finding_id change on every scan
    (raw findings are re-ingested), so they must not be used as a cache key.
    """
    raw = json.dumps(
        {
            "scanner_name": finding.scanner_name,
            "resource_type": finding.resource_type,
            "resource_identifier": finding.resource_identifier,
            "finding_type": finding.finding_type,
            "title": finding.title,
            "severity": finding.severity,
            "description": finding.description,
            "metadata_json": finding.metadata_json,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _finding_header(finding: NormalizedFinding) -> str:
    lines = [
        f"FINDING fingerprint={_finding_fingerprint(finding)}",
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
    maps_raw = data.get("maps", False)
    if isinstance(maps_raw, str):
        maps = maps_raw.strip().lower() in ("true", "1", "yes")
    else:
        maps = bool(maps_raw)
    confidence = float(data.get("confidence", 0.0))
    confidence = min(0.99, max(0.01, confidence))
    if not maps:
        confidence = min(confidence, 0.30)
    rationale = str(data.get("rationale") or "No rationale provided by model.").strip()
    return maps, round(confidence, 4), rationale


class GeminiMapper:
    def __init__(self, timeout: float = 60.0, cache_path: pathlib.Path | None = None) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured; cannot perform AI mapping.")
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._timeout = timeout
        self._cache: dict[str, dict[str, list[CandidateDecision]]] = {}
        self._cache_path = cache_path or pathlib.Path(".cache") / "gemini_mapping_cache.json"
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_persistent_cache()

    def _load_persistent_cache(self) -> None:
        if not self._cache_path.exists():
            return
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            for key, finding_decisions in data.items():
                inner = {}
                for fid_str, decisions_list in finding_decisions.items():
                    decisions = [
                        CandidateDecision(
                            control_id=d["control_id"],
                            maps=d["maps"],
                            confidence=d["confidence"],
                            rationale=d["rationale"],
                        )
                        for d in decisions_list
                    ]
                    inner[str(fid_str)] = decisions
                self._cache[key] = inner
        except (json.JSONDecodeError, KeyError, OSError, TypeError):
            self._cache = {}

    def _persist_cache(self) -> None:
        try:
            serializable = {
                key: {
                    str(fid): [
                        {
                            "control_id": d.control_id,
                            "maps": d.maps,
                            "confidence": d.confidence,
                            "rationale": d.rationale,
                        }
                        for d in decisions
                    ]
                    for fid, decisions in inner.items()
                }
                for key, inner in self._cache.items()
            }
            self._cache_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _generate_with_timeout(
        self, contents: str, config: types.GenerateContentConfig
    ):
        """Run a generate_content call with a real per-call timeout.

        ``future.result(timeout=...)`` alone does not cancel the underlying
        call: exiting a ``with ThreadPoolExecutor`` block calls
        ``shutdown(wait=True)`` and defeats the timeout. Instead we keep the
        executor alive, cancel the future on timeout, and shut down without
        waiting so the slow call does not block the request.
        """

        def _call():
            return self._client.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config
            )

        pool = ThreadPoolExecutor(max_workers=1)
        future: Future = pool.submit(_call)
        try:
            return future.result(timeout=self._timeout)
        except TimeoutError:
            future.cancel()
            pool.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError(f"Gemini call timed out after {self._timeout}s")
        else:
            pool.shutdown(wait=True)

    def _cache_key_from_prompt(self, prompt: str, expected: dict[str, list[str]]) -> str:
        """Versioned key for the exact model, candidate set, and prompt."""
        payload = {
            "model": GEMINI_MODEL,
            "prompt_version": PROMPT_VERSION,
            "candidate_ids": {
                fingerprint: sorted(set(control_ids))
                for fingerprint, control_ids in sorted(expected.items())
            },
            "prompt": prompt,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _build_chunk_prompt(
        self, chunk: list[tuple[NormalizedFinding, list[CandidateControl]]]
    ) -> tuple[str, dict[str, list[str]]]:
        """Serialize ORM objects to plain text in the calling thread.

        All lazy attribute access happens here so worker threads never touch
        the request-scoped SQLAlchemy session.
        """
        blocks: list[str] = []
        expected: dict[str, list[str]] = {}
        for finding, candidates in chunk:
            fingerprint = _finding_fingerprint(finding)
            candidate_ids = [candidate.control_catalog.control_id for candidate in candidates]
            # Preserve every candidate list when distinct finding rows share
            # one evidence fingerprint. The caller maps this shared result to
            # each matching finding row independently.
            expected.setdefault(fingerprint, [])
            expected[fingerprint] = sorted(set(expected[fingerprint]) | set(candidate_ids))
            candidate_text = "\n\n".join(
                f"CANDIDATE:\n{_control_block(candidate.control_catalog, match_score=candidate.match_score)}"
                for candidate in candidates
            )
            blocks.append(f"{_finding_header(finding)}\n\n{candidate_text}")
        return "\n\n---\n\n".join(blocks), expected

    def _map_one_chunk(
        self, prompt: str, expected: dict[str, list[str]]
    ) -> dict[str, list[CandidateDecision]]:
        cache_key = self._cache_key_from_prompt(prompt, expected)
        if cache_key in self._cache:
            return self._cache[cache_key]

        def _attempt() -> dict[str, list[CandidateDecision]]:
            config = types.GenerateContentConfig(
                system_instruction=_SYSTEM_BATCH,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = self._generate_with_timeout(prompt, config)
            data = extract_json(response.text)
            out: dict[str, list[CandidateDecision]] = {}
            for entry in data.get("results", []):
                finding_id = entry.get("finding_id")
                if finding_id is None:
                    continue
                fingerprint = str(finding_id)
                if fingerprint not in expected:
                    continue
                valid_ids = set(expected[fingerprint])
                decisions: list[CandidateDecision] = []
                for candidate in entry.get("candidates", []):
                    control_id = str(candidate.get("control_id", ""))
                    if control_id not in valid_ids:
                        continue
                    maps, confidence, rationale = _clean_decision(candidate)
                    decisions.append(CandidateDecision(control_id, maps, confidence, rationale))
                merged = {decision.control_id: decision for decision in out.get(fingerprint, [])}
                merged.update({decision.control_id: decision for decision in decisions})
                out[fingerprint] = list(merged.values())
            if not out:
                raise ValueError("Gemini batch response contained no usable results.")
            return out

        result = call_with_retry(
            _attempt,
            attempts=2,
            backoff=2.0,
            delay_for=extract_retry_delay,
            give_up_on=is_per_day_quota_exhausted,
            max_delay=15.0,
        )
        self._cache[cache_key] = result
        self._persist_cache()
        return result

    def map_batch(
        self,
        items: list[tuple[NormalizedFinding, list[CandidateControl]]],
    ) -> dict[str, list[CandidateDecision]]:
        if not items:
            return {}

        # Build all prompt payloads in the main thread (ORM access here only).
        chunk_payloads: list[tuple[str, dict[str, list[str]]]] = []
        for i in range(0, len(items), MAPPING_CHUNK_SIZE):
            chunk = items[i:i + MAPPING_CHUNK_SIZE]
            prompt, expected = self._build_chunk_prompt(chunk)
            chunk_payloads.append((prompt, expected))

        if len(chunk_payloads) == 1:
            return self._map_one_chunk(chunk_payloads[0][0], chunk_payloads[0][1])

        # Run chunks in parallel, capped by MAPPING_MAX_WORKERS for rate limits.
        # One failing chunk must not take down the whole run: partial verdicts
        # are returned and missing findings are handled by the caller.
        # If every chunk fails, raise so the caller can record a real error.
        merged: dict[str, list[CandidateDecision]] = {}
        last_error: Exception | None = None
        failed_chunks = 0
        workers = min(MAPPING_MAX_WORKERS, len(chunk_payloads))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(self._map_one_chunk, prompt, expected)
                for prompt, expected in chunk_payloads
            ]
            for future in futures:
                try:
                    merged.update(future.result())
                except Exception as exc:
                    # Log the real failure instead of swallowing it silently.
                    logger.warning("Gemini mapping chunk failed: %s", exc)
                    last_error = exc
                    failed_chunks += 1
        if failed_chunks == len(chunk_payloads):
            # Every chunk failed; surface the real error so the pipeline can
            # mark the scan as AI_MAPPER_FAILURE instead of silently returning nothing.
            raise RuntimeError(f"Gemini mapping failed for all {len(chunk_payloads)} chunks: {last_error}") from last_error
        return merged

    def clear_cache(self) -> None:
        """Clear the AI result cache."""
        self._cache.clear()

    def map_one(self, finding: NormalizedFinding, control: ControlCatalog) -> MappingDecision:
        # Serialize ORM attributes to plain text before any threading.
        prompt = f"CONTROL:\n{_control_block(control)}\n\nFINDING:\n{_finding_header(finding)}"

        def _attempt() -> MappingDecision:
            config = types.GenerateContentConfig(
                system_instruction=_SYSTEM_ONE,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = self._generate_with_timeout(prompt, config)
            maps, confidence, rationale = _clean_decision(extract_json(response.text))
            return MappingDecision(confidence=confidence, rationale=rationale, maps=maps)

        return call_with_retry(_attempt, attempts=2, backoff=1.0, delay_for=extract_retry_delay, give_up_on=None, max_delay=15.0)
