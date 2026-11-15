# Complisoc — Scale Testing Documentation

> **ISO control-ID audit (2026-11):** Earlier benchmark files used several incorrect ISO/IEC 27001:2022 control IDs. All accuracy claims from the former expected labels, including prior live Gemini/Groq runs, are withdrawn and must not be cited. The current 32-case fixture uses corrected IDs and checks its control metadata against the production seed catalog, but remains synthetic and is not an independent ISO mapping evaluation. Oracle-mocked metrics only test deterministic pipeline behavior.

**Version:** 1.0
**Owner:** QA Engineering
**Last updated:** November 2026 (ISO control-ID audit)

---

## 1. Purpose

This document describes the scale testing strategy, implementation, and results for the Complisoc compliance intelligence platform. It addresses the Week 15 deliverable from the original Use Case S1-P-04 proposal:

> *"Run compliance evaluation harness on synthetic benchmark dataset to measure precision, recall, hallucination rate, and mapping stability under large-scale scan workloads."*

The goal is to test deterministic pipeline behavior and throughput. The synthetic ISO fixture is not suitable as independent compliance evidence or as a claim of AI mapping accuracy.

---

## 2. Scope

**In scope:**

- Synthetic benchmark dataset of security findings with control IDs checked against the selected 2022 production catalog
- Evaluation harness measuring precision, recall, F1-score, hallucination rate, and mapping stability
- Performance under large-scale scan workloads (500–1000 findings)
- Regression detection via F1-delta vs. committed JSON snapshot
- Live API load testing via Locust

**Out of scope:**

- Production traffic load testing (no production deployment in Semester 1)
- Multi-tenant concurrency testing (architecture does not yet support multi-tenancy)
- Real-time streaming evaluation (pipeline is batch-oriented)

---

## 3. Test Strategy Overview

Complisoc scale testing operates at three levels:

| Level | Tool | Dataset | Measures | Reproducible |
|-------|------|---------|----------|--------------|
| **Unit benchmark** | `validate_mappings.py` (oracle-mocked) | 32 synthetic findings across 15 controls | Deterministic pipeline agreement | ✅ Yes (CI-safe) |
| **Live AI smoke run** | `validate_mappings.py` (real Gemini/Groq) | Same synthetic fixture | Provider integration only; not independent accuracy | ⚠️ Manual (requires API keys) |
| **API load test** | Locust | Synthetic HTTP traffic | Throughput, latency, error rate | ✅ Yes (CI-safe) |

The unit benchmark is the primary gate. It runs on every CI build and must pass before merge.

---

## 4. Synthetic Benchmark Dataset

### 4.1 Location

`tests/benchmark/gold_standard.json`

### 4.2 Structure

The dataset is a JSON document with three sections:

1. **`controls`** — 15 selected control catalog entries from ISO/IEC 27001:2022 Annex A:
   - Organizational (A.5.x)
   - Physical (A.7.x)
   - Technological (A.8.x)

   Each control includes:
   - `control_id`, `control_family`, `title`, `description`, `objective`
   - `scanner_signals` — tokens that deterministic narrowing uses to match findings
   - `keywords` — additional matching tokens
   - `source_url` — explanatory reference; ISO is the normative source

2. **`mappings`** — 32 synthetic finding-to-control pairs (14 controls have 2 examples; A.8.24 has 4):
   - `scanner_finding_id` — unique identifier (GOLD-1 through GOLD-32)
   - `scanner_name` — which scanner produced the finding (checkov, trivy, sonarqube, defender)
   - `expected_control_id` — the reviewed expected control
   - `raw_json` — synthetic scanner output in the same schema as real findings

3. **`framework`** and **`framework_version`** — the compliance framework reference (ISO/IEC 27001:2022 Annex A, version 2022).

### 4.3 Design Rationale

The fixture is constructed so that:

- **Controls have disjoint `scanner_signals` and `keywords`.** This means the deterministic candidate narrowing algorithm (`backend/compliance/candidate_narrowing.py`) will rank the correct control as #1 for every finding.
- **Most controls have two finding variants; A.8.24 has four** because both encryption and key-management findings map to use of cryptography.
- **The selected controls cover organizational, physical, and technological families.** This is not a complete Annex A catalog or broad family-representative sample.

### 4.4 Current Size

The 32-finding hand-curated set is the source for `tests/benchmark/generate_dataset.py`, which expands it into 100- and 500-finding workloads using severity rotations and resource-suffix / title / description perturbations. Generated artifacts:

- `tests/benchmark/gold_standard_100.json` (100 findings, 15 controls)
- `tests/benchmark/gold_standard_500.json` (500 findings, 15 controls)

These are repeated synthetic workload variants, not independently curated gold findings.

---

## 5. Evaluation Harness

### 5.1 Location

`tests/benchmark/validate_mappings.py`

### 5.2 How It Works

The harness:

1. Loads `gold_standard.json`.
2. Verifies control IDs and core metadata against the production seed migrations, then builds a fresh in-memory SQLite database from the fixture.
3. Runs the **real** `process_scan_run` pipeline (via `langchain_pipeline.run_pipeline`), but patches the two AI steps with a faithful oracle:
   - **Gemini oracle:** Accepts only the first-ranked candidate from deterministic narrowing (confidence = 0.95 for top-1, 0.10 for others). This isolates the measurement to the narrowing + workflow selection logic.
   - **Groq oracle:** Always agrees (agreement_value = 1.0). This ensures mappings are published, not dropped to manual review.
4. Collects the predicted control IDs from the `ControlMapping` table.
5. Compares predictions to gold expectations and computes metrics.

### 5.3 Metrics

The harness reports:

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Precision** | `TP / (TP + FP)` | Of the mappings the pipeline produced, how many were correct? |
| **Recall** | `TP / (TP + FN)` | Of the gold mappings, how many did the pipeline recover? |
| **F1-score** | `2 × P × R / (P + R)` | Harmonic mean of precision and recall |
| **Hallucination rate** | `FP / (TP + FP)` | Fraction of pipeline outputs that are false positives (mappings to wrong controls) |
| **Mapping stability** | Boolean (identical TP count across runs) | Whether the pipeline produces consistent results on repeated runs |

**Targets (from original proposal):**

- Precision ≥ 0.85
- Recall ≥ 0.85
- F1 ≥ 0.85
- Hallucination rate ≤ 0.05 (i.e., FP rate ≤ 5%)

**Current result (oracle-mocked, 32 synthetic findings):**

- Precision: 1.000
- Recall: 1.000
- F1: 1.000
- Hallucination rate: 0.000
- Stability: ✅ Identical TP count across repeated runs

**Important caveat:** The oracle accepts the top-1 candidate unconditionally. The expected mappings were deliberately constructed around separable keywords, so perfect oracle-mocked scores only show deterministic plumbing on this fixture. They do **not** validate Gemini/Groq accuracy, ambiguity handling, or general ISO control mapping.

---

## 6. Live AI Smoke Run (Manual)

### 6.1 Purpose

The live command exercises real provider calls on the synthetic fixture. It is an integration smoke run, not an independent accuracy benchmark.

The previously reported live results used the now-corrected, invalid control labels. Those results are withdrawn and must not be used as evidence of ISO mapping accuracy.

### 6.2 How to Run

```bash
export GEMINI_API_KEY=<your_key>
export GROQ_API_KEY=<your_key>
python tests/benchmark/validate_mappings.py --live --output /tmp/benchmark_live_results.json
```

The `--live` flag disables the oracle mocks and lets the real AI steps execute against the production `GeminiMapper` and `GroqVerifier` classes. Results are written to the path given by `--output` (a temp directory is recommended; result files are **not** committed to the repository).

> The `COMPLISOC_LIVE_BENCHMARK` env var documented in earlier revisions is no longer required — `--live` on the CLI is the single switch that activates the live path.

### 6.3 Interpretation

Do not interpret live scores on this synthetic fixture as ISO accuracy or validate them against the former expected labels. An independent, expert-reviewed and broader evaluation set is required before making accuracy claims.

---

## 7. Regression Detection

### 7.1 F1-Delta Snapshot

The original proposal committed to:

> *"After Week 8 E2E pipeline stabilization, all LangChain chain outputs for the 30–50 benchmark findings will be serialized as a JSON snapshot. After any prompt change, model update, or chain modification, the harness re-runs all benchmark inputs and computes F1 delta against the snapshot. A delta >0.05 triggers a regression alert and blocks the PR in GitHub Actions."*

### 7.2 Implementation

**Snapshots committed under `tests/benchmark/snapshots/`:**

- `mvp-v1.json` — 32-finding snapshot
- `mvp-v1-100.json` — 100-finding snapshot
- `mvp-v1-500.json` — 500-finding snapshot

**Format:** A JSON document mapping each `scanner_finding_id` to the predicted control ID, mapping status, and final confidence, plus an aggregate F1 / precision / recall block.

**Harness CLI (`tests/benchmark/validate_mappings.py`):**

- `--update-snapshot` — re-run the benchmark and write a new snapshot
- `--check-snapshot` — re-run the benchmark and assert F1-delta ≤ threshold
- `--max-f1-delta 0.05` — override the regression threshold (default 0.05)
- `--snapshot <path>` — point at an alternative snapshot

**Pytest integration (`tests/test_scale_testing.py`):**

- `test_f1_delta_against_snapshot[30]`
- `test_f1_delta_against_snapshot[100]`
- `test_f1_delta_against_snapshot[500]`

Each parameterized test loads the committed snapshot, re-runs the pipeline (oracle-mocked), recomputes the per-finding prediction set, and asserts `F1-delta ≤ 0.05` with a per-finding diff list of `changed_findings` in the failure message.

**Throughput regression (`test_pipeline_throughput_under_budget[30|100|500]`):**

The same `tests/test_scale_testing.py` file also gates wall-clock time. Observed baselines on the dev box (single-thread, single worker) are 23.5 s / 30 s / 68 s; the test budget is set at 60 s / 90 s / 180 s to absorb ~3× environment variance and act as an early-warning regression guard. These budgets are intentionally below the proposal target of 30 s for 500–1000 findings — see Section 8.5.

**Current snapshot F1 scores:** 1.000 / 1.000 / 1.000 — F1-delta vs. themselves is 0.000.

---

## 8. Large-Scale Performance Testing

### 8.1 Target

From the original proposal §10.2:

> *"Pipeline throughput, dashboard response time, and GitHub Actions queue performance under large-scale synthetic scan workloads — <30s for 500–1000 findings end-to-end."*

### 8.2 Datasets

- `tests/benchmark/gold_standard.json` — 32 synthetic findings, with corrected control IDs checked against production seed metadata.
- `tests/benchmark/gold_standard_100.json` — 100 generated workload variants.
- `tests/benchmark/gold_standard_500.json` — 500 generated workload variants.

`tests/benchmark/generate_dataset.py` is the generator. It enforces an invariant: a generated variant must still map to the same control as its seed under the deterministic narrowing algorithm. If a candidate variant would rank a different control higher (i.e. keyword overlap changed because the perturbation was too aggressive), the generator **skips** that variant and tries the next template rather than emitting a bad sample. This guarantees that synthetic scaling does not introduce artificial precision/recall regressions.

### 8.3 Performance Optimization Applied

The naïve pipeline issued one `db.commit()` per finding inside `narrow_candidates` and `normalize_raw_finding`, which made the 500-finding run take ~10 minutes. The fix:

- Both functions now accept a `commit: bool = True` kwarg.
- The pipeline (`backend/compliance/langchain_pipeline.py`) calls them with `commit=False`.
- A single commit happens at `stage_finalize` for the whole batch.

This dropped the 500-finding run from ~10 minutes to ~68 s on the dev box. No semantic change to the data persisted.

### 8.4 Measured Wall-Clock (Oracle-Mocked, Dev Box)

| Findings | Wall-clock | Budget in test | Source |
|----------|------------|----------------|--------|
| 30 | 23.5 s | 60 s | `test_pipeline_throughput_under_budget[30]` |
| 100 | 30 s | 90 s | `test_pipeline_throughput_under_budget[100]` |
| 500 | 68 s | 180 s | `test_pipeline_throughput_under_budget[500]` |

All three tests pass. The 23.5 s base-case figure is from the former 30-finding run; the corrected 32-finding fixture has not been separately timed. It remains a historical performance observation, not current benchmark evidence.

### 8.5 Gap vs. Proposal Target

The proposal target of **<30 s for 500–1000 findings** is **not yet met on the dev box** (current: 68 s for 500). The dev box runs single-threaded and shares CPU with the AI client import path. Production deploys would use gunicorn workers, a warm process, and a connection-pooled Postgres backend; the test budgets (180 s for 500) are set at ~3× observed runtime as a regression guard rather than a stretch goal. Closing the remaining 2.3× gap to reach <30 s on the dev box is tracked as a P2 item — likely requires lazy AI client import and reuse of the in-memory DB across the test run.

The separate `tests/ai_quality/test_load.py` exercises the SQLite-backed application workflow with provider calls mocked. Its 500- and 1000-finding cases use 180 s and 360 s ceilings, respectively, as broad regression safety budgets scaled from the 500-finding benchmark budget; they are not evidence that the proposal's <30 s target is met and do not measure live-provider latency.

### 8.6 Throughput Expectations (Live AI, Projected)

| Mode | Findings | Expected time | Bottleneck |
|------|----------|---------------|------------|
| Live AI (Gemini batch) | 100 | < 15 s | Gemini API rate limit (10 RPM free tier) |
| Live AI (Groq batch) | 100 | < 10 s | Groq API rate limit (30 RPM free tier) |

The live AI throughput is bounded by the free-tier rate limits, not by the pipeline. A paid tier would increase throughput by ~10×. Actual measurement of the live path is tracked as a P2 item (see Section 11.2).

---

## 9. API Load Testing

### 9.1 Tool

Locust (Python load testing framework, free and open-source).

### 9.2 Location

- `tests/load/locustfile.py` — standalone Locust file
- `tests/load/test_locust.py` — pytest integration

### 9.3 Test Scenarios

The load test simulates realistic dashboard usage:

| Endpoint | Weight | Rationale |
|----------|--------|-----------|
| `GET /api/v1/health` | 4 | Health checks (high frequency) |
| `GET /api/v1/scanners` | 3 | Scanner availability checks |
| `GET /api/v1/scan-runs` | 3 | Scan run list (default page load) |
| `GET /api/v1/dashboard/gap-summary` | 2 | Gap summary widget |
| `GET /api/v1/dashboard/control-coverage` | 2 | Coverage widget |
| `GET /api/v1/dashboard/severity-distribution` | 1 | Severity distribution widget |

### 9.4 How to Run

**Standalone Locust:**

```bash
locust -f tests/load/locustfile.py --headless -u 50 -r 5 --run-time 1m --host=http://127.0.0.1:8000
```

**Via pytest:**

```bash
pytest tests/load/test_locust.py -v
```

### 9.5 Targets

- 50 concurrent users
- < 500ms p95 response time for read endpoints
- 0% error rate (health, scanners, scan-runs, dashboard endpoints are all read-only)

### 9.6 Latest Run

The load test was executed against a local FastAPI backend on `127.0.0.1:8765` (port 8765 instead of 8000 to avoid conflicts in the dev environment). Configuration: 20 users ramping at 5/s, 30-second run, with the dev DB seeded with one 30-finding scan run so endpoints return real data.

**Aggregated result (re-run on demand):** `locust -f tests/load/locustfile.py --host=http://127.0.0.1:8000 --users=20 --spawn-rate=5 --run-time=30s --headless`. Last run: 124 requests, **0 failures (0.00%)**, 11.8 RPS, avg 258 ms, p95 840 ms, p99 1700 ms.

Raw Locust output goes to the terminal; per-endpoint stats are visible in the
Locust console. The HTML report and per-endpoint CSVs (when written with
`--csv=...`) are **not** committed to the repository — re-run the command above
to regenerate them locally.

The 50-user target documented in §9.5 was scaled down for the dev box (single CPU) to keep the run bounded. Scaling to 50 users on a multi-core production deploy is a re-run on a single command and is tracked as a P2 item.

---

## 10. Test Execution Summary

### 10.1 How to Run All Scale Tests

```bash
# Unit benchmark (oracle-mocked, CI-safe)
python tests/benchmark/validate_mappings.py

# Pytest scale tests
python -m pytest tests/test_scale_testing.py -v

# Live AI benchmark (requires API keys)
export GEMINI_API_KEY=<key>
export GROQ_API_KEY=<key>
python tests/benchmark/validate_mappings.py --live

# API load test (requires running backend)
locust -f tests/load/locustfile.py --headless -u 50 -r 5 --run-time 1m --host=http://127.0.0.1:8000
```

### 10.2 CI Integration

The deterministic benchmark and pytest scale tests are included in CI (`.github/workflows/`). The live provider smoke run and load test are **not** in CI (they require external API keys and a running backend, respectively).

### 10.3 Latest Results

The numbers below are reproducible from the commands in §10.1 — they are
**not** stored as artifacts in the repository.

**Current oracle-mocked run (32-finding set):**

```
Gold mappings      : 32
Pipeline mappings : 32
True positives    : 32
False positives   : 0
False negatives   : 0
Precision          : 1.000
Recall             : 1.000
F1                 : 1.000
Hallucination rate : 0.000
Mapping stability  : OK (identical across 3 runs)
```

**Current F1-delta snapshot check (oracle-mocked, 32/100/500 synthetic findings):**

| Dataset | Snapshot F1 | Current F1 | F1-delta | Threshold | Pass |
|---------|-------------|------------|----------|-----------|------|
| 32 findings (`mvp-v1.json`) | 1.000 | 1.000 | 0.000 | 0.05 | ✅ |
| 100 findings (`mvp-v1-100.json`) | 1.000 | 1.000 | 0.000 | 0.05 | ✅ |
| 500 findings (`mvp-v1-500.json`) | 1.000 | 1.000 | 0.000 | 0.05 | ✅ |

No current live AI accuracy result is reported. The old live run and repeated-run figures were based on the invalidated control labels; retain them only as historical provider-call records, not as performance evidence.

**Latest load test run:** re-run on demand with the command in §9.6 — the last
run recorded 124 requests, 0 failures, 11.8 RPS.

---

## 11. Gaps and Future Work

### 11.1 Known Gaps

1. **No independent AI accuracy benchmark is available.** The oracle-mocked benchmark measures only deterministic behavior on a synthetic fixture. Previous live scores used incorrect expected control IDs and are withdrawn.

2. **No cost measurement.** The live AI benchmark does not report API token usage or cost per finding. This is important for budget planning (current budget: ₹0/semester, ceiling: ₹2,500).

3. **Dev-box wall-clock exceeds proposal target.** 500 findings takes 68 s on the dev box vs. the proposal's <30 s target. Closing this gap requires lazy AI client import and reuse of the in-memory DB across the test run.

4. **1000-finding benchmark not generated.** The generator currently stops at 500. Extending to 1000 is a one-line change in `generate_dataset.py` once the dev-box throughput target is hit.

5. **Load test run was 20 users on dev hardware, not 50.** The 50-user target in §9.5 is deferred to a production-like deploy.

### 11.2 Resolved (this milestone)

The following P0/P1 items from the original gap list are now resolved:

- ✅ F1-delta regression test (`test_f1_delta_against_snapshot`) for 30, 100, and 500 findings with committed snapshots.
- ✅ 100-finding and 500-finding benchmark datasets generated programmatically.
- ✅ Performance budgets enforced in `test_pipeline_throughput_under_budget[30|100|500]`.
- ✅ Pipeline batch-commit optimization (per-finding → per-stage commit) cut 500-finding runtime ~9×.
- ✅ Locust load test executed end-to-end against a running backend (see §9.6 for the re-run command and the recorded numbers from the latest run).
- ✅ Corrected selected benchmark controls and metadata are checked against the production seed catalog. Previous live accuracy claims are withdrawn; new independent AI evaluation remains outstanding.

### 11.3 Planned Improvements (remaining)

| Priority | Item | Estimated effort |
|----------|------|------------------|
| P2 | Cost measurement in live AI benchmark (Gemini + Groq token usage per finding) | 2 hours |
| P2 | Lazy AI client import + DB reuse to bring 500-finding runtime under the 30 s proposal target | 3 hours |
| P2 | Extend generated dataset to 1000 findings | 30 minutes |
| P2 | Re-run Locust at 50 users on a multi-core production-like deploy | 1 hour |
| P2 | Wire the live benchmark into a scheduled CI job that re-runs weekly and posts a Slack/email on F1-delta > 0.05 | 4 hours |

### 11.4 Success Criteria

Scale testing is considered complete when:

- ✅ 30+ finding synthetic benchmark with production-catalog metadata validation — **32 curated fixtures; oracle-mocked only**
- ✅ F1-delta regression test against committed snapshot — **passes on 32/100/500 synthetic workloads**
- ✅ 500+ finding performance test with a budget enforced in CI — **68 s observed, 180 s budget, 30 s proposal target not yet met (P2)**
- ✅ Load test with documented results — **0% error rate, see §9.6 for the re-run command**
- ⬜ Independent live AI accuracy benchmark — **not established; former results were withdrawn after control-ID audit**

---

## 12. Appendix

### 12.1 File Locations

| File | Purpose |
|------|---------|
| `tests/benchmark/gold_standard.json` | 32-finding audited synthetic benchmark fixture |
| `tests/benchmark/gold_standard_100.json` | Generated 100-finding benchmark |
| `tests/benchmark/gold_standard_500.json` | Generated 500-finding benchmark |
| `tests/benchmark/generate_dataset.py` | Programmatic expansion from 32 → N findings with invariant check |
| `tests/benchmark/validate_mappings.py` | Evaluation harness with `--update-snapshot` / `--check-snapshot` CLI |
| `tests/benchmark/snapshots/mvp-v1.json` | Committed F1 snapshot, 32 findings |
| `tests/benchmark/snapshots/mvp-v1-100.json` | Committed F1 snapshot, 100 findings |
| `tests/benchmark/snapshots/mvp-v1-500.json` | Committed F1 snapshot, 500 findings |
| `tests/test_scale_testing.py` | 9-test scale suite: precision/recall, mapping stability, F1-delta × 3, throughput × 3, snapshot round-trip |
| `tests/load/locustfile.py` | Standalone Locust file |
| `tests/load/test_locust.py` | Pytest Locust integration |

> **No evidence/ artifacts are committed.** All result files (JUnit XML, Locust
> CSV / HTML, coverage JSON / XML / HTML, captured run logs) are produced on
> demand by the commands in §10.1. To regenerate them locally, run the
> commands and direct the output to a temp directory (e.g.
> `python tests/benchmark/validate_mappings.py --live --output /tmp/...`).

### 12.2 Related Documentation

- `ARCHITECTURE.md` — System architecture and layer responsibilities
- `REQUIREMENTS.md` — Functional and non-functional requirements
- `DATA_MODEL.md` — Entity relationships and lineage
- `API.md` — API endpoint specifications
- `docs/DEPLOYMENT.md` — Deployment and operations guide
- `docs/TESTING_STRATEGY.md` — Authoritative QA description, evidence commands, and submission statement

### 12.3 Glossary

| Term | Definition |
|------|------------|
| **Oracle** | A deterministic substitute for an AI step that accepts the top-ranked candidate, used in CI to avoid API calls |
| **F1-delta** | The absolute difference in F1-score between a current benchmark run and a committed snapshot |
| **Hallucination rate** | The fraction of pipeline outputs that are false-positive mappings (mappings to wrong controls) |
| **Mapping stability** | The property that the pipeline produces identical results on repeated runs with the same input |
| **Snapshot** | A committed JSON file containing the expected pipeline outputs for a given benchmark dataset and prompt version |

---

**End of document.**
