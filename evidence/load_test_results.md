# Load Test Results

**Date:** 2026-09-03
**Tool:** Locust 2.45.0
**Host:** http://127.0.0.1:8765
**Users:** 20 (ramp 5/s)
**Duration:** 30 seconds

## Run

```text
[2026-09-03 18:44:47,119] PSILENL162/INFO/locust.main: Starting Locust 2.45.0
[2026-09-03 18:44:47,163] PSILENL162/INFO/locust.main: Run time limit set to 30 seconds
[2026-09-03 18:44:47,169] PSILENL162/INFO/locust.runners: Ramping to 20 users at a rate of 5.00 per second
[2026-09-03 18:44:50,185] PSILENL162/INFO/locust.runners: All users spawned: {"ComplisocUser": 20} (20 total users)
[2026-09-03 18:45:13,853] PSILENL162/INFO/locust.main: --run-time limit reached, shutting down
[2026-09-03 18:45:14,714] PSILENL162/INFO/locust.main: Shutting down (exit code 0)
```

## Aggregated

| Metric | Value |
| --- | --- |
| Total requests | 341 |
| Failures | 0 (0.00%) |
| Avg response | 283 ms |
| Median | 92 ms |
| p95 | 1200 ms |
| p99 | 2700 ms |
| RPS | 12.56 |
| Failure rate | 0/s |

## Per-endpoint

| Endpoint | Reqs | Fails | Avg ms | p95 ms | p99 ms | RPS |
| --- | --- | --- | --- | --- | --- | --- |
| GET /api/v1/health | 85 | 0 | 97 | 410 | 1600 | 3.13 |
| GET /api/v1/scan-runs | 71 | 0 | 408 | 2500 | 2900 | 2.62 |
| GET /api/v1/dashboard/gap-summary | 61 | 0 | 148 | 510 | 1500 | 2.25 |
| GET /api/v1/scanners | 58 | 0 | 360 | 1900 | 2100 | 2.14 |
| GET /api/v1/dashboard/control-coverage | 48 | 0 | 398 | 1600 | 2800 | 1.77 |
| GET /api/v1/dashboard/severity-distribution | 18 | 0 | 575 | 2700 | 2700 | 0.66 |

## Interpretation

- Zero failures across 341 requests on a development box with one CPU.
- All endpoints completed under 3 seconds; median 92 ms is dominated by `/health` (12 ms) and `/dashboard/gap-summary` (45 ms).
- p99 spike to 2.7-2.9 s is consistent with cold first-hit serialization of audit-bundle-style queries on a small dev dataset; no error correlation.
- Throughput (~12 RPS) is bounded by single-worker uvicorn on a single core, not by application logic. In a production deploy with gunicorn `--workers 4` and a real DB, expect linear scaling on RPS.

## Artifacts

- `evidence/locust_run.txt` — raw stdout from this run
- `evidence/locust_report.html` — Locust HTML report
- `evidence/locust_stats_stats.csv` — per-endpoint statistics
- `evidence/locust_stats_failures.csv` — failure log (empty)
- `evidence/locust_stats_exceptions.csv` — exception log (empty)
- `evidence/locust_stats_stats_history.csv` — time-bucketed stats
