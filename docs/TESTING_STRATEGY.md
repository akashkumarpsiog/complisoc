# Complisoc Testing Strategy and Evidence

**Status:** Authoritative QA description
**Last updated:** September 2026

## 1. Purpose

This document describes what Complisoc tests, what the current tests prove, and what they do not prove. It is the source of truth for QA claims. Test counts and coverage percentages are intentionally not hard-coded here because they change with the test run and environment.

Complisoc testing is organized around the pipeline:

```text
scanner output -> raw finding -> normalized finding -> candidate narrowing
-> AI mapping -> validation -> verification -> confidence -> published/review
-> reporting and audit evidence
```

A passing test is evidence only for the behavior it exercises. A deterministic test is not an AI accuracy measurement, and a synthetic load test is not a production capacity guarantee.

## 2. Test layers

| Layer | Primary location | What it validates | Evidence strength |
|---|---|---|---|
| Unit and schema | `tests/test_schema.py`, `tests/test_scanners.py`, `tests/test_utils.py` | Pydantic/database constraints, scanner parsing shapes, utilities and error paths | Valid unit evidence for covered branches |
| Scanner to database integration | `tests/test_scanners_db.py` | Trivy, Checkov, SonarQube and Defender-shaped input persistence/normalization | Valid integration evidence; Defender-shaped input is not a live Defender integration |
| Workflow integration | `tests/test_mvp_workflow.py`, `tests/test_ai_models.py`, `tests/test_integrity.py`, `tests/test_data_quality.py` | Lineage, threshold routing, mocked model orchestration, data integrity and audit-bundle behavior | Valid mocked integration evidence; does not establish live model quality |
| API integration | `tests/test_api_endpoints.py` | REST endpoints, database mutations, filtering and report/audit responses | Valid endpoint evidence for tested paths |
| Frontend | `frontend/src/**/*.test.ts`, `frontend/src/**/*.test.tsx` | API client, components and selected page behavior | Valid component/client evidence; not browser-wide E2E coverage |
| Scenario E2E | `tests/e2e/`, `tests/test_scenario_reports.py` | End-to-end scenario and report flows where fixtures/tools are available | Conditional evidence; scanner binaries, fixtures and environment must be recorded |
| Deterministic benchmark | `tests/benchmark/validate_mappings.py`, `tests/test_scale_testing.py` | Candidate narrowing, workflow persistence, throughput and deterministic regression snapshots | Valid deterministic pipeline/throughput evidence, not AI accuracy |
| Live AI benchmark | `validate_mappings.py --live` | One manually executed real Gemini/Groq run against the gold set | Useful smoke evidence, not a statistically reliable accuracy study |
| Load testing | `tests/load/` and Locust artifacts | HTTP behavior under a chosen local workload | Environment-specific performance evidence, not production capacity |
| Planned/scaffolded QA | Great Expectations, Selenium and Locust setup | Future data-quality, browser and load coverage | Scaffolding is not executed test evidence |

## 3. Synthetic benchmark data

`tests/benchmark/gold_standard.json` contains 15 ISO/IEC 27001:2022 Annex A controls and 30 hand-curated finding-to-control pairs. Each control has two variants. The expected control ID is manually supplied in the file, and the finding text was designed to make the expected control rank first under deterministic keyword narrowing.

`gold_standard_100.json` and `gold_standard_500.json` are generated expansions of the 30 seeds. They are valid workload fixtures, but they are not 100 or 500 independently curated cases. They repeat the same semantic templates with altered severity, resource suffixes and wording. They are appropriate for throughput, persistence, duplicate-ID and deterministic regression checks.

The generator must remain reproducible and must reject ambiguous top-candidate ties. A generated dataset must be validated for:

- unique `scanner_finding_id` values;
- complete expected-control and framework fields;
- expected controls present in the control catalog;
- valid severity and scanner fields;
- an unambiguous top candidate with a documented score margin.

## 4. Benchmark interpretation

The default harness patches Gemini with an oracle that accepts the deterministic top-ranked candidate and patches Groq to agree. Therefore a result such as precision=1.000, recall=1.000 and F1=1.000 proves that the deterministic narrowing and workflow plumbing reproduce the labels in this curated fixture. It does not measure Gemini or Groq accuracy.

The 500-finding run proves that the same deterministic path can process a generated batch and preserve the expected mapping invariant. It does not prove generalization, production throughput or semantic hallucination performance.

The evaluator correctly counts a missing prediction, an incorrect expected-control prediction and an extra finding ID as errors for the benchmark. However, the meaning of hallucination must be stated narrowly: the current benchmark measures invalid/incorrect benchmark outputs, not all semantic hallucinations. A valid catalog control can still be the wrong control for a finding.

The current stability test repeats the deterministic oracle path. It proves repeatability of deterministic processing. It does not prove stochastic live-model stability, confidence calibration or model-version stability.

## 5. Live AI evidence

A live run is valuable because it exercises real provider calls, but one 30-case run is a small smoke test. Its output should record, at minimum:

- run timestamp and environment;
- dataset path and SHA-256 hash;
- prompt version/hash;
- provider and model identifiers;
- per-finding predicted control, confidence, verification result and final status;
- errors, retries and abstentions;
- aggregate precision, recall, F1 and explicitly defined error counts.

The JSON output is evidence of the recorded result, not independent proof of the provider responses unless the raw structured responses or an auditable provider trace are retained separately. Secrets must never be stored in the artifact.

## 6. What is currently accomplished

The repository currently supports and tests:

- scanner-shaped input normalization and SQLite persistence;
- API and workflow status transitions, confidence threshold routing and lineage;
- report generation, audit-bundle creation and integrity checks;
- selected frontend components and API client behavior;
- deterministic 30/100/500-finding benchmark execution;
- deterministic F1 snapshot comparison and batch throughput guards;
- a manually runnable live Gemini/Groq smoke benchmark;
- Locust and browser/data-quality scaffolding.

These are separate achievements. They must not be combined into a claim of organizational compliance, live AI accuracy, or production-scale capacity.

## 7. Gaps and required improvements

1. Add an independently curated AI evaluation set containing ambiguous, unmappable, missing-context and cross-control findings.
2. Call one shared production evaluator from tests instead of reimplementing precision/recall/hallucination arithmetic in test fixtures.
3. Run repeated live evaluations and measure control agreement, confidence variance, abstention quality and publication-status drift.
4. Store provenance metadata and raw structured model decisions for live evidence.
5. Fix generator seed usage, token normalization and tie/margin validation; regenerate expanded fixtures with recorded generator version and seed.
6. Separate deterministic benchmark tests from AI-quality tests and remove duplicate 30-case assertions where they add no new coverage.
7. Mark scanner-binary, Selenium, Great Expectations and Locust assets as executed or scaffolded for each run.
8. Resolve or formally quarantine failing/unsupported tests before reporting the complete suite as green.

## 8. Recommended reporting language

Use:

> The deterministic benchmark reproduced all curated labels on the 30-finding set and its generated 500-finding workload. This validates candidate narrowing, workflow integration and deterministic batch processing. A manually executed live run provides smoke evidence for the configured Gemini/Groq path. Independent AI accuracy, semantic hallucination rate, calibration, stochastic stability and production capacity require additional controlled evaluation.

Do not use:

> The system achieved 100% AI accuracy, zero hallucinations, proven AI stability or verified organizational compliance.
